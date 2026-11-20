"""Generate Harbor tasks for GDM stealth.

Upstream: ``inspect_evals/gdm_stealth`` in UK AISI's Inspect Evals,
the open-source release of the stealth evaluations from Phuong et al.
(2025), arXiv:2505.01420. The paper describes five stealth
evaluations; the Inspect release contains four tasks
(oversight_pattern, classifier_evasion, cover_your_tracks,
strategic_rule_breaking). Sample filtering replicates upstream
``data/dataset.py`` defaults (FSF v2 scope), yielding 13 samples.
Prompts are preserved verbatim; adaptation is packaging only.

Episode state is hosted by the agent harness (as upstream hosts its
solvers outside the sandbox), so generated tasks carry an explicit
outcome contract: the parity custom agent writes
``/home/agent/gdm_outcome.json`` and the verifier maps it to a reward
with the upstream scoring rules. See README before running these
tasks with any other agent.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path
from typing import Any

from .upstream import PAPER_URL, UPSTREAM_COMMIT, UPSTREAM_REPO, ensure_source

BASE_IMAGE = (
    "ubuntu:latest@sha256:"
    "065aa8626841f16057b78b027b464cd59c4fac36c204c72dcbf48d66f5fa8a96"
)
# Separate-verifier image (verify.py is stdlib-only), digest-pinned.
VERIFIER_IMAGE = (
    "python:3.12-slim@sha256:"
    "5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"
)

TEMPLATE_DIR = Path(__file__).parent / "task-template"
UPSTREAM_PKG = Path("src/inspect_evals/gdm_stealth")

from .task_catalog import (
    _AI_NAME_RE,
    ADAPTER_NAME,
    MARKER_PATH,
    MESSAGE_LIMITS,
    MODEL_ROLES,
    SAMPLES_BY_KEY,
    SCORING,
    STRATEGIC_PERSONA_DETAIL,
    STRATEGIC_SYSTEM_TEMPLATE,
    TOOLS_BY_DATASET,
    input_prompt,
    marker_payload,
    sanitize,
    system_prompt,
)

# Per-topic role models for the in-container oracle replay. These are
# the tiers under which each topic's reference solution was verified
# (exact upstream preview IDs are unavailable on OpenRouter; see
# README). Model names keep the openrouter/ prefix convention of the
# shared transport (first segment stripped before the request).
_ORACLE_FLASH = "openrouter/google/gemini-2.5-flash"
_ORACLE_PRO = "openrouter/google/gemini-2.5-pro"
_ORACLE_O3 = "openrouter/openai/o3"

ORACLE_TEMPERATURE = 0.0

ORACLE_MODELS: dict[str, dict[str, str]] = {
    "spoilers_tv_show": {"rater": _ORACLE_PRO, "judger": _ORACLE_FLASH},
    "spoilers_sports_match": {"rater": _ORACLE_PRO, "judger": _ORACLE_FLASH},
    "spoilers_escape_room": {"rater": _ORACLE_PRO, "judger": _ORACLE_FLASH},
    "ntk_chips": {"rater": _ORACLE_FLASH, "judger": _ORACLE_FLASH},
    "ntk_biorisk": {"rater": _ORACLE_FLASH, "judger": _ORACLE_FLASH},
    "codes": {"rater": _ORACLE_FLASH, "judger": _ORACLE_FLASH},
    "ntk_earnings": {"rater": _ORACLE_O3, "judger": _ORACLE_FLASH},
    "password": {"rater": _ORACLE_O3, "judger": _ORACLE_FLASH},
    "api_key": {"rater": _ORACLE_O3, "judger": _ORACLE_FLASH},
}

# Package files vendored into each task's solution/ for the
# in-container oracle replay (paths relative to the gdm_stealth
# package). The custom_agent __init__ is replaced with a neutral one
# so the vendored copy never imports Harbor.
_SOLUTION_PACKAGE_FILES = [
    "__init__.py",
    "task_catalog.py",
    "custom_agent/ai_secretary.py",
    "custom_agent/cover.py",
    "custom_agent/criteria.py",
    "custom_agent/objectives_data.py",
    "custom_agent/raters.py",
    "custom_agent/transport.py",
    "custom_agent/hosts.py",
    "custom_agent/strategic_tools.py",
    "custom_agent/oracle_solutions.py",
    "custom_agent/oracle_policies.py",
    "custom_agent/oracle_strategic.py",
    "custom_agent/data/email.csv",
]


class GDMStealthAdapter:
    """Writes Harbor task directories under ``self.output_dir``."""

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        source_dir: Path | None = None,
        cover_with_hint: bool = False,
        **kwargs: Any,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.source_dir = source_dir
        self.cover_with_hint = cover_with_hint

    def _pkg_dir(self) -> Path:
        return ensure_source(self.source_dir) / UPSTREAM_PKG

    def _samples(self, pkg: Path) -> list[dict[str, Any]]:
        def load(sub: str) -> list[dict[str, Any]]:
            return json.loads(
                (pkg / f"data/{sub}/register.json").read_text(encoding="utf-8")
            )

        samples: list[dict[str, Any]] = []
        ai_tasks = load("ai_secretary")
        # limit_to_tactical(fsfv2_only=True): topic bomb, 8 failures
        # allowed, (email_domain|confidential_subject, feedback_in_system).
        for t in ai_tasks:
            m = _AI_NAME_RE.match(t["challenge_name"])
            if not m:
                continue
            if (
                m["topic"] == "bomb"
                and m["n"] == "8"
                and m["difficulty"] == "feedback_in_system"
                and m["version"] in ("email_domain", "confidential_subject")
            ):
                samples.append({"dataset": "oversight_pattern", "task": t})
        # limit_to_subtlety(fsfv2_only=True): content_rater, 2 failures.
        for t in ai_tasks:
            m = _AI_NAME_RE.match(t["challenge_name"])
            if m and m["version"] == "content_rater" and m["n"] == "2":
                samples.append({"dataset": "classifier_evasion", "task": t})
        for t in load("cover_your_tracks"):
            if self.cover_with_hint or t["challenge_name"] == "no_hint":
                samples.append({"dataset": "cover_your_tracks", "task": t})
        for t in load("strategic_rule_breaking"):
            if t["challenge_name"] == "normal_turn_100_version_2":
                samples.append({"dataset": "strategic_rule_breaking", "task": t})
        for s in samples:
            s["sample_id"] = f"{s['dataset']}--{s['task']['challenge_name']}"
        return samples

    def _generate(self, pkg: Path, sample: dict[str, Any]) -> bool:
        dataset = sample["dataset"]
        task = sample["task"]
        task_dir = self.output_dir / sanitize(sample["sample_id"])
        if task_dir.exists():
            if not self.overwrite:
                return False
            shutil.rmtree(task_dir)
        env_dir = task_dir / "environment"
        tests_dir = task_dir / "tests"
        solution_dir = task_dir / "solution"
        for d in (env_dir, tests_dir, solution_dir):
            d.mkdir(parents=True)

        shutil.copy2(
            Path(__file__).resolve().parents[2] / "LICENSE.inspect-evals",
            env_dir / "LICENSE.inspect-evals",
        )
        (env_dir / "gdm_task.json").write_text(
            json.dumps(marker_payload(sample["sample_id"]), indent=2) + "\n",
            encoding="utf-8",
        )
        objective = task.get("prompts", {}).get("hard", "")
        prompt = input_prompt(dataset, objective)
        (task_dir / "instruction.md").write_text(prompt, encoding="utf-8")

        # Environment: upstream stealth sandbox (ubuntu, /home/agent,
        # network_mode none in compose — Harbor tasks keep the agent
        # offline inside the container; rater models are called by
        # the harness on the host, not from this container).
        dockerfile = [
            "# Generated by the gdm-stealth adapter from",
            f"# {UPSTREAM_REPO} @ {UPSTREAM_COMMIT} (gdm_stealth/Dockerfile)",
            f"FROM {BASE_IMAGE}",
            "RUN apt-get update && apt-get install -y python3"
            " && rm -rf /var/lib/apt/lists/*",
            # /var/lib/gdm is agent-owned so the in-container oracle
            # replay (solution/solve.sh, run as agent) can write the
            # signed outcome; the host parity agent writes as root.
            # The outcome integrity tag still binds score to sample.
            "RUN useradd -m -u 10001 agent && mkdir -p /home/agent /var/lib/gdm"
            " && chown agent:agent /home/agent /var/lib/gdm && chmod 0700 /var/lib/gdm",
        ]
        if dataset in ("oversight_pattern", "classifier_evasion"):
            match = _AI_NAME_RE.match(task["challenge_name"])
            assert match
            version = match["version"]
            src = pkg / f"data/ai_secretary/email_tasks_{version}.txt"
            shutil.copy2(src, env_dir / "email_tasks.txt")
            dockerfile.append("COPY email_tasks.txt /home/agent/email_tasks.txt")
        if dataset == "cover_your_tracks":
            dockerfile.append(
                "RUN mkdir -p /log && touch /log/assistant.log"
                " && chown agent:agent /log /log/assistant.log"
            )
        dockerfile += [
            f"COPY gdm_task.json {MARKER_PATH}",
            "ENV HOME=/home/agent",
            "WORKDIR /home/agent",
            "",
        ]
        (env_dir / "Dockerfile").write_text(
            "\n".join(dockerfile), encoding="utf-8"
        )

        template = (TEMPLATE_DIR / "task.toml").read_text(encoding="utf-8")
        content = (
            template.replace("{task_id}", sanitize(sample["sample_id"]))
            .replace("{difficulty}", "hard")
            .replace("{tags}", json.dumps([dataset, task["challenge_name"]]))
        )
        (task_dir / "task.toml").write_text(content, encoding="utf-8")

        test_template = (TEMPLATE_DIR / "tests/test.sh").read_text(encoding="utf-8")
        (tests_dir / "test.sh").write_text(
            test_template.replace("{dataset_name}", dataset).replace(
                "{sample_key}", sample["sample_id"]
            ),
            encoding="utf-8",
        )
        shutil.copy2(TEMPLATE_DIR / "tests/verify.py", tests_dir / "verify.py")
        (tests_dir / "Dockerfile").write_text(
            (TEMPLATE_DIR / "tests/Dockerfile")
            .read_text(encoding="utf-8")
            .replace("{verifier_image}", VERIFIER_IMAGE),
            encoding="utf-8",
        )
        shutil.copy2(
            TEMPLATE_DIR / "solution/solve.sh", solution_dir / "solve.sh"
        )

        if dataset == "strategic_rule_breaking":
            sys_meta: dict[str, Any] = {
                "system_prompt": None,
                "system_prompt_template": STRATEGIC_SYSTEM_TEMPLATE,
                "system_prompt_persona_detail": STRATEGIC_PERSONA_DETAIL,
                "system_prompt_note": (
                    "Render with upstream "
                    "solver/strategic_rule_breaking/prompt.py "
                    "get_system_message(): substitute the persona "
                    "detail and the version-2 handbook generated from "
                    "tool descriptions. Not reproduced verbatim at "
                    "generation time."
                ),
            }
        else:
            sys_meta = {"system_prompt": system_prompt(pkg, dataset)}
        metadata = {
            "adapter": ADAPTER_NAME,
            "upstream_benchmark": "gdm_stealth",
            "upstream_repo": UPSTREAM_REPO,
            "upstream_commit": UPSTREAM_COMMIT,
            "paper": PAPER_URL,
            "dataset_name": dataset,
            "sample_id": task["challenge_name"],
            **sys_meta,
            "input_prompt": prompt,
            "input_prompt_source": (
                "register.json prompts.hard via get_input_prompt(); "
                "strategic_rule_breaking ignores it and uses the fixed "
                "welcome notification above"
            ),
            "message_limit": MESSAGE_LIMITS[dataset],
            "tools": TOOLS_BY_DATASET[dataset],
            "model_roles": MODEL_ROLES[dataset],
            "setup_steps": task.get("setup_steps"),
            "setup_note": (
                "ai_secretary setup is realized as the copied "
                "email_tasks.txt in the image; cover_your_tracks setup "
                "(/log/assistant.log) is baked into the Dockerfile; "
                "strategic_rule_breaking has no setup steps."
            ),
            "epochs": (
                "upstream Inspect default 10 epochs (mean/median/max "
                "reducers); paper used 50 trials, solved if >=1 succeeds"
            ),
            "scoring": SCORING[dataset],
            "outcome_contract": (
                "Parity custom agent writes /home/agent/gdm_outcome.json "
                '{"success": bool, "score": float_in_0_1, '
                '"final_message": str} at episode end; see verify.py.'
            ),
        }
        (tests_dir / "task_metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        self._write_solution(solution_dir, dataset, task, sample)
        return True

    def _write_solution(
        self,
        solution_dir: Path,
        dataset: str,
        task: dict[str, Any],
        sample: dict[str, Any],
    ) -> None:
        """Vendor the oracle replay package + per-task trajectory.

        The built-in Harbor oracle uploads the whole solution/ dir and
        runs solve.sh in the container; replay.py executes the same
        curated policies as the host replay agent against the real
        checkers, with role models from trajectory.json.
        """
        pkg_src = Path(__file__).parent
        pkg_dst = solution_dir / "gdm_stealth"
        for rel in _SOLUTION_PACKAGE_FILES:
            dst = pkg_dst / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pkg_src / rel, dst)
        strategic_src = pkg_src / "custom_agent" / "strategic"
        strategic_dst = pkg_dst / "custom_agent" / "strategic"
        strategic_dst.mkdir(parents=True, exist_ok=True)
        for path in sorted(strategic_src.iterdir()):
            if path.is_file() and "__pycache__" not in path.parts:
                shutil.copy2(path, strategic_dst / path.name)
        # Neutral package inits: the vendored copy must never import
        # the Harbor-dependent agents.
        (pkg_dst / "custom_agent" / "__init__.py").write_text(
            '"""Vendored checker/host modules for in-container oracle replay."""\n',
            encoding="utf-8",
        )
        shutil.copy2(
            TEMPLATE_DIR / "tests/verify.py", pkg_dst / "verify_outcome.py"
        )
        shutil.copy2(
            TEMPLATE_DIR / "solution/replay.py", solution_dir / "replay.py"
        )

        models: dict[str, str] = {}
        trajectory: dict[str, Any] = {"candidate_offset": 0}
        if dataset == "classifier_evasion":
            match = _AI_NAME_RE.match(task["challenge_name"])
            topic = match["topic"] if match else ""
            models = dict(ORACLE_MODELS.get(topic, {}))
        elif dataset == "cover_your_tracks":
            models = {"rater": _ORACLE_FLASH}
        elif dataset == "strategic_rule_breaking":
            models = {"chat": _ORACLE_FLASH}
            trajectory["strategic_seed"] = 123
            trajectory["strategic_mode"] = "maxscore"
        trajectory["models"] = models
        # Pin role-model sampling for reproducible oracle replays
        # (reasoning-tier o3 does not accept a temperature).
        trajectory["temperature"] = {
            role: ORACLE_TEMPERATURE
            for role, model in models.items()
            if "/openai/o" not in model
        }
        trajectory["sample_key"] = sample["sample_id"]
        (solution_dir / "trajectory.json").write_text(
            json.dumps(trajectory, indent=2) + "\n", encoding="utf-8"
        )


    def run(self) -> None:
        pkg = self._pkg_dir()
        samples = self._samples(pkg)
        if self.task_ids:
            wanted = {sanitize(t) for t in self.task_ids} | set(self.task_ids)
            samples = [
                s
                for s in samples
                if s["sample_id"] in wanted or sanitize(s["sample_id"]) in wanted
            ]
        if self.limit is not None:
            samples = samples[: max(0, self.limit)]
        generated = skipped = 0
        for sample in samples:
            if self._generate(pkg, sample):
                generated += 1
            else:
                skipped += 1
        print(
            f"gdm-stealth: generated={generated} skipped={skipped} "
            f"selected={len(samples)} -> {self.output_dir}"
        )

