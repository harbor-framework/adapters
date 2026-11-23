"""SREGym -> Harbor task generation.

Each SREGym problem becomes one Harbor task. Two containers run it:

* ``main`` (unprivileged): Harbor's agent and verifier. It gets kubectl/helm,
  a kubeconfig for SREGym's filtering Kubernetes API proxy, and the SREGym
  conductor API. These are the same interfaces SREGym's own agent containers
  get.
* ``sregym`` (privileged sidecar): SREGym's upstream Docker-in-Docker runtime
  at a pinned commit, plus ``sidecar/bridge.py``. It runs the unmodified SREGym
  campaign for the problem, then serves the conductor's result row to the
  verifier.

Per-problem metadata (app info, stages, and the agent prompt built by SREGym's
own Claude Code driver) comes from ``extract_metadata.py``, run inside an
SREGym checkout. A snapshot for the pinned commit ships as
``problems_metadata.json``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "task-template"
DEFAULT_METADATA = PACKAGE_DIR / "problems_metadata.json"

# SREGym commit the bundled metadata and the sidecar image are built from.
SREGYM_COMMIT = "ac60c642"
SREGYM_REPO = "https://github.com/SREGym/SREGym.git"
DEFAULT_SIDECAR_IMAGE = f"sregym-harbor-sidecar:{SREGYM_COMMIT}"
# Dated judge model ID (upstream defaults the judge to the agent model; pin
# one judge for both sides of a comparison).
DEFAULT_JUDGE_MODEL = "gpt-5-2025-08-07"

# Problems that cannot run on SREGym's emulated (KIND-in-DinD) cluster. The
# reasons are taken from upstream (environment_ports.NOT_PORTED,
# ProblemRegistry.non_emulated_cluster_problems, and SREGym-Lite's exclusions).
EXCLUDED_PROBLEMS = {
    # Host-kernel-global clock: on KIND/DinD it would shift the host and every
    # parallel environment. Upstream rejects it on emulated clusters.
    "node_clock_drift_hotel_reservation": "requires a non-emulated cluster",
    # Stops worker kubelets. The agent cannot repair a stopped node through the
    # Kubernetes API, and the workload cannot grade recovery on it.
    "kubelet_crash": "requires node-level access to repair",
    # khaos storage faults (dm-dust / dm-flakey) need real block devices.
    "latent_sector_error": "hardware fault (khaos)",
    "latent_sector_error_saleor": "hardware fault (khaos)",
    "silent_data_corruption": "hardware fault (khaos)",
    "silent_data_corruption_frappe": "hardware fault (khaos)",
    "read_error": "hardware fault (khaos)",
}

# Agent-phase egress, mirroring upstream's filtered mode: the SREGym backend
# (conductor API and filtering Kubernetes proxy behind host.docker.internal)
# plus model provider APIs. Upstream also blocks web search and fetch.
DEFAULT_ALLOWED_HOSTS = ("host.docker.internal", "api.anthropic.com", "api.openai.com")

# Sidecar (DinD + KIND) resources. Upstream recommends 8 CPUs / 16 GiB per
# environment and more for larger problems (docker/dind/README.md). The
# Incident Arena and other large applications fail their own health and
# latency checks, or time out deploying, at 8 CPUs even with SREGym's recovery
# applied (validated with the oracle), so they get 16 CPUs / 32 GiB.
DEFAULT_SIDECAR_RESOURCES = (8, "16g")
LARGE_APP_SIDECAR_RESOURCES = (16, "32g")
LARGE_APP_CLASSES = frozenset(
    {
        "Saleor",
        "SlackSpine",
        "Frappe",
        "WorkspaceApplication",
        "GiteaMySQLApplication",
        "GitLabNotificationApplication",
        "GitLabNotificationDelayedAuditApplication",
        "GitLabNotificationIntermittentApplication",
        # Train Ticket's deploy saturates the KIND API server at 8 CPUs; the
        # Blueprint rpc-retry-storm problems inject CPU stress across nodes.
        "TrainTicket",
        "BlueprintHotelReservation",
    }
)


def sidecar_resources(app_class: str) -> tuple[int, str]:
    return LARGE_APP_SIDECAR_RESOURCES if app_class in LARGE_APP_CLASSES else DEFAULT_SIDECAR_RESOURCES


# How long the reference solution waits after recover_fault() and pod
# readiness before submitting mitigation. It changes only when the oracle
# submits, never how a submission is graded.
DEFAULT_ORACLE_SETTLE_SEC = 180
ORACLE_SETTLE_OVERRIDES = {
    # After recover_fault() and with all pods Ready, requests still fail
    # (30-60% errors) for about 4 minutes, so a 180 s wait fails the
    # LoadgenHealthOracle window; 480 s passes.
    "consul_stale_snapshot_restore_hotel_reservation": 480,
    # The eviction stall leaves mongodb-profile reads timing out for a few
    # minutes after recovery. Under host load, a 180 s wait failed with ~17%
    # errors in every round; about 440 s passed with no errors.
    "profile_mongodb_eviction_unit_mismatch_hotel_reservation": 480,
}


# Splits. "lite" is upstream's SREGym-Lite suite (sregym/conductor/problem_sets.py).
SPLITS = ("lite", "lite-ia", "full")


@dataclass(frozen=True)
class Timeouts:
    # Upstream's default --agent-timeout.
    agent_sec: int = 1800
    build_sec: int = 5400
    verifier_sec: int = 1800

    @property
    def conductor_agent_sec(self) -> int:
        # The conductor's own agent deadline starts when the passive agent is
        # launched, which is before Harbor installs and starts its agent.
        # Harbor's agent timeout (followed by /harbor/finish) is what ends an
        # attempt, so this only needs headroom for the agent install. Regenerate
        # with a larger --agent-timeout rather than using Harbor's agent timeout
        # multiplier.
        return self.agent_sec + 900


def sanitize(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ValueError(f"cannot derive a task name from {name!r}")
    return slug


def oracle_token(problem_id: str, secret: str) -> str:
    """Per-task oracle token: HMAC of a private generation secret.

    The secret is random unless the caller supplies one (for reproducible
    regeneration). It is never committed, so the token cannot be derived from
    public information. The token ends up only in the task's ``solution/``,
    which Harbor uploads for the oracle agent alone, and in the sidecar's
    environment.
    """
    return hmac.new(secret.encode(), f"sregym-oracle:{problem_id}".encode(), hashlib.sha256).hexdigest()


def _toml_list(values: list[str]) -> str:
    return json.dumps(list(values))


def _render(text: str, values: dict[str, str]) -> str:
    # Plain token replacement: templates also contain shell/compose braces.
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


class SregymAdapter:
    def __init__(
        self,
        output_dir: Path,
        *,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "lite",
        metadata_path: Path | None = None,
        sidecar_image: str = DEFAULT_SIDECAR_IMAGE,
        sidecar_pull_policy: str = "never",
        sidecar_cpus: int | None = None,
        sidecar_memory: str | None = None,
        judge_model: str = DEFAULT_JUDGE_MODEL,
        timeouts: Timeouts | None = None,
        oracle_secret: str | None = None,
        network: str = "allowlist",
        allowed_hosts: tuple[str, ...] = DEFAULT_ALLOWED_HOSTS,
    ) -> None:
        if split not in SPLITS:
            raise ValueError(f"unknown split {split!r}; choose from {SPLITS}")
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.split = split
        self.metadata_path = Path(metadata_path or DEFAULT_METADATA)
        self.sidecar_image = sidecar_image
        self.sidecar_pull_policy = sidecar_pull_policy
        # None: choose per application (sidecar_resources); set to override for all tasks.
        self.sidecar_cpus = sidecar_cpus
        self.sidecar_memory = sidecar_memory
        self.judge_model = judge_model
        self.timeouts = timeouts or Timeouts()
        self.oracle_secret = oracle_secret or secrets.token_hex(32)
        if network not in {"allowlist", "public"}:
            raise ValueError("network must be 'allowlist' or 'public'")
        self.network = network
        self.allowed_hosts = tuple(allowed_hosts)

    # ------------------------------------------------------------------
    def load_problems(self) -> list[dict]:
        data = json.loads(self.metadata_path.read_text())
        problems = {p["problem_id"]: p for p in data["problems"]}
        unknown = set(ORACLE_SETTLE_OVERRIDES) - set(problems)
        if unknown:
            raise ValueError(f"ORACLE_SETTLE_OVERRIDES names unknown problems: {sorted(unknown)}")
        for pid, err in sorted(data.get("failures", {}).items()):
            logger.warning("skipping %s: metadata extraction failed (%s)", pid, err.splitlines()[0])

        if self.split == "lite":
            selected = [p for p in problems.values() if "sregym-lite" in p["suites"]]
        elif self.split == "lite-ia":
            selected = [p for p in problems.values() if "sregym-lite-ia" in p["suites"]]
        else:
            selected = list(problems.values())
        selected = [p for p in selected if p["problem_id"] not in EXCLUDED_PROBLEMS]
        selected.sort(key=lambda p: p["problem_id"])

        if self.task_ids:
            # Explicit IDs select from all problems, regardless of split.
            by_name = {sanitize(pid): p for pid, p in problems.items()}
            selected = []
            for tid in self.task_ids:
                problem = problems.get(tid) or by_name.get(sanitize(tid))
                if problem is None:
                    logger.warning("unknown task id: %s", tid)
                elif problem not in selected:
                    selected.append(problem)
        if self.limit is not None:
            selected = selected[: self.limit]
        return selected

    # ------------------------------------------------------------------
    def run(self) -> list[Path]:
        problems = self.load_problems()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for problem in problems:
            path = self.generate_task(problem)
            if path is not None:
                written.append(path)
        logger.info("wrote %d SREGym tasks to %s", len(written), self.output_dir)
        return written

    def generate_task(self, problem: dict) -> Path | None:
        pid = problem["problem_id"]
        task_name = sanitize(pid)
        task_dir = self.output_dir / task_name
        if task_dir.exists():
            if not self.overwrite:
                logger.info("exists, skipping: %s", task_dir)
                return None
            shutil.rmtree(task_dir)
        shutil.copytree(TEMPLATE_DIR, task_dir)

        app_info = problem["app_info"]
        token = oracle_token(pid, self.oracle_secret)
        t = self.timeouts
        default_cpus, default_memory = sidecar_resources(problem["app_class"])
        values = {
            "task_name": task_name,
            "problem_id": pid,
            "app_name": app_info["app_name"],
            "oracle_settle_sec": str(ORACLE_SETTLE_OVERRIDES.get(problem["problem_id"], DEFAULT_ORACLE_SETTLE_SEC)),
            "app_namespaces": " ".join(app_info.get("namespaces") or [app_info["namespace"]]),
            "app_class": problem["app_class"],
            "sregym_commit": SREGYM_COMMIT,
            "keywords": _toml_list(["sre", "kubernetes", "incident-response", sanitize(problem["app_class"])]),
            "suites": _toml_list(problem["suites"]),
            "agent_timeout": f"{float(t.agent_sec)}",
            "verifier_timeout": f"{float(t.verifier_sec)}",
            "build_timeout": f"{float(t.build_sec)}",
            "conductor_agent_timeout": str(t.conductor_agent_sec),
            "sidecar_image": self.sidecar_image,
            "sidecar_pull_policy": self.sidecar_pull_policy,
            "sidecar_cpus": str(self.sidecar_cpus or default_cpus),
            "sidecar_memory": self.sidecar_memory or default_memory,
            "sidecar_start_period": str(t.build_sec),
            "judge_model": self.judge_model,
            "oracle_token": token,
            "verifier_poll_iterations": str(max(1, t.verifier_sec // 5 - 6)),
            "agent_network": (
                f'network_mode = "allowlist"\nallowed_hosts = {_toml_list(list(self.allowed_hosts))}'
                if self.network == "allowlist"
                else "# network: Harbor default (public)"
            ),
        }
        for rel in (
            "task.toml",
            "environment/docker-compose.yaml",
            "solution/solve.sh",
            "tests/test.sh",
        ):
            f = task_dir / rel
            f.write_text(_render(f.read_text(), values))
        # The instruction is SREGym's own Claude Code prompt, verbatim.
        (task_dir / "instruction.md").write_text(problem["instruction"].rstrip("\n") + "\n")
        for rel in ("solution/solve.sh", "tests/test.sh"):
            (task_dir / rel).chmod(0o755)
        return task_dir
