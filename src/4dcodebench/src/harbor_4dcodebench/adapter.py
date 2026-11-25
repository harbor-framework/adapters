"""Generate Harbor tasks from 4DCodeBench: one task per case, synthetic and real.

Inputs, all local and read-only:

    repo            an upstream 4DCodeBench checkout, for the agent context
                    (`harness/agent_context/`) and the commit the tasks record
    cases root      <kind>/<case>/reference.mp4, as `scripts/download_data.py` writes it
    data root       <kind>/<case>/{world,annotation,estimates}/, the scorer's hidden inputs
                    (`download_data.py --estimates`)

Each task gives the agent what `harness/runtime/infer.py` gives it (the rendered
`TASK.md` as the instruction, `/task`, `/input/reference.mp4`) and scores the
delivered `/workspace/world` with the unmodified scorer in a separate verifier
container that alone holds the reference data (see `task-template/`).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "task-template"
REWARDS_MODULE = PACKAGE_DIR / "rewards.py"
METRIC_SCRIPT = PACKAGE_DIR / "metric.py"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "4dcodebench"

UPSTREAM_URL = "https://github.com/4DCodeBench/4DCodeBench"
# the commit this adapter was written against; tasks record the checkout's actual commit
UPSTREAM_COMMIT = "6c466be34107d7f388f30f97bf059b68ba1a21b0"

KINDS = ("synthetic", "real")
SPLITS = ("all", *KINDS)

# The upstream images (harness/base, harness/agent, harness/scorer) and the scorer image
# with its checkpoints added (docker/scorer-checkpoints.Dockerfile in this adapter).
DEFAULT_AGENT_IMAGE = "4dcb/agent:dev"
DEFAULT_SCORER_IMAGE = "4dcb/scorer-checkpoints:dev"

# harness/runtime/templates/runtime.example.toml and harness/runtime/score.py defaults
AGENT_TIMEOUT_SEC = 21600
VERIFIER_TIMEOUT_SEC = 3600
TASK_TIMEOUT_SEC = 1800
TASK_PREPARE_TIMEOUT_SEC = 600
BUILD_TIMEOUT_SEC = 3600

# The scorer's hidden inputs per kind, relative to data/<kind>/<case>/: the reference
# world (synthetic) or the dynamic mask (real), and the estimates that the released
# 4DCodeBench/Dataset-Model-Estimation holds for that kind (config/estimates.py).
REQUIRED_DATA = {
    "synthetic": (
        "world/camera.json",
        "world/render.mp4",
        "world/meshes",
        "world/dynamics",
        "estimates/semantic_dinov3.npz",
        "estimates/semantic_tips.npz",
        "estimates/geophys_dinov3.npz",
    ),
    "real": (
        "annotation/dynamic_mask.npz",
        "estimates/semantic_dinov3.npz",
        "estimates/semantic_tips.npz",
        "estimates/geophys_dinov3.npz",
        "estimates/flow.h5",
        "estimates/tracks.npz",
        "estimates/moge.npz",
        "estimates/depth.h5",
    ),
}
# what is copied into the verifier image from data/<kind>/<case>/
DATA_ENTRIES = {"synthetic": ("world", "estimates"), "real": ("annotation", "estimates")}


def required_data(kind: str, base: Path) -> tuple[str, ...]:
    """REQUIRED_DATA[kind] for the case whose reference data is under `base`.

    Some published synthetic worlds hold only an identity-less liquid: their packed
    world (Dataset-Synthetic worlds/<case>.h5) has a `solver/` and no `dynamics` group,
    so the upstream `unpack` writes no `dynamics/` directory (e.g. B_09). Such a case is
    not incomplete; its reference world is required as published, without `dynamics/`.
    """

    names = REQUIRED_DATA[kind]
    if kind == "synthetic" and (base / "world/solver").is_dir() and not (base / "world/dynamics").exists():
        names = tuple(name for name in names if name != "world/dynamics")
    return names

PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


class AdapterError(RuntimeError):
    """The inputs cannot produce the requested tasks."""


@dataclass(frozen=True)
class Case:
    kind: str
    name: str

    @property
    def key(self) -> str:
        """`<kind>/<case>`, the path cases/, data/ and the scorer manifests use."""
        return f"{self.kind}/{self.name}"

    @property
    def task_id(self) -> str:
        return task_id_for(self.kind, self.name)


def task_id_for(kind: str, name: str) -> str:
    """The registry-safe task name of a case: lowercase, other characters as hyphens."""
    slug = re.sub(r"[^a-z0-9]+", "-", f"{kind}-{name}".lower()).strip("-")
    if not slug:
        raise AdapterError(f"case {kind}/{name} has no usable task name")
    return slug


def render(template: str, values: dict[str, object]) -> str:
    """Replace every `{name}` placeholder; raise on a name `values` does not define."""

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in values:
            raise AdapterError(f"template placeholder {{{name}}} has no value")
        return str(values[name])

    return PLACEHOLDER.sub(replace, template)


def upstream_paths(repo: Path) -> dict[str, str]:
    """The agent-side container paths of the upstream harness, as POSIX strings.

    Read from `checker/paths.py` and `harness/runtime/common.py`, so they follow the
    checkout rather than a copy in this adapter.
    """

    source = (repo / "checker" / "paths.py").read_text(encoding="utf-8")
    common = (repo / "harness" / "runtime" / "common.py").read_text(encoding="utf-8")
    scope: dict[str, object] = {}
    exec(compile(source, str(repo / "checker" / "paths.py"), "exec"), scope)  # noqa: S102
    mount = re.search(r'^TASK_MOUNT = Path\("([^"]+)"\)', common, re.MULTILINE)
    entry = re.search(r'^TASK_ENTRYPOINT = "([^"]+)"', common, re.MULTILINE)
    if mount is None or entry is None:
        raise AdapterError("harness/runtime/common.py no longer defines TASK_MOUNT / TASK_ENTRYPOINT")
    return {
        "task": PurePosixPath(mount.group(1)).as_posix(),
        "entrypoint": entry.group(1),
        "video": scope["VIDEO_PATH"].as_posix(),
        "world": scope["WORLD_DIR"].as_posix(),
        "solution": scope["SOLUTION_DIR"].as_posix(),
    }


def render_agent_context(repo: Path, target: Path) -> str:
    """Copy `harness/agent_context/` to `target`, render its TASK.md, and return the text.

    Mirrors `prepare_agent_context` in `harness/runtime/infer.py`, with the container
    paths written as POSIX paths on every host.
    """

    paths = upstream_paths(repo)
    source = repo / "harness" / "agent_context"
    if not source.is_dir():
        raise AdapterError(f"not a 4DCodeBench checkout (no harness/agent_context/): {repo}")
    shutil.copytree(source, target)
    entrypoint = target / paths["entrypoint"]
    context = {"paths": {key: paths[key] for key in ("task", "video", "world", "solution")}}
    pattern = re.compile(r"{{([a-z_]+(?:\.[a-z_]+)*)}}")   # infer.py's PLACEHOLDER

    def replace(match: re.Match) -> str:
        value: object = context
        for key in match.group(1).split("."):
            value = value[key]   # type: ignore[index]
        if isinstance(value, (dict, list)):
            raise AdapterError(f"task placeholder {match.group(0)} is not scalar")
        return str(value)

    rendered = pattern.sub(replace, entrypoint.read_text(encoding="utf-8"))
    if "{{" in rendered or "}}" in rendered:
        raise AdapterError("TASK.md contains an invalid placeholder")
    entrypoint.write_text(rendered, encoding="utf-8", newline="\n")
    return rendered


def checkout_commit(repo: Path) -> str:
    """The commit of the upstream checkout, or the pinned one when git cannot tell."""

    try:
        found = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        logger.warning("cannot read the commit of %s; recording %s", repo, UPSTREAM_COMMIT)
        return UPSTREAM_COMMIT
    if found != UPSTREAM_COMMIT:
        logger.warning("4DCodeBench checkout is at %s, not the pinned %s", found, UPSTREAM_COMMIT)
    return found


def link_or_copy(source: str, target: str) -> None:
    """Hard-link `source` to `target`, copying when the two are on different devices."""
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def copy_entry(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, copy_function=link_or_copy, symlinks=False)
    else:
        link_or_copy(str(source), str(target))


class Harbor4DCodeBenchAdapter:
    """Write one Harbor task per 4DCodeBench case under `output_dir`."""

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        *,
        repo: Path,
        cases_root: Path | None = None,
        data_root: Path | None = None,
        split: str = "all",
        agent_image: str = DEFAULT_AGENT_IMAGE,
        scorer_image: str = DEFAULT_SCORER_IMAGE,
        agent_network: str = "public",
        agent_allowed_hosts: list[str] | None = None,
        skip_incomplete: bool = False,
        **kwargs,
    ):
        if split not in SPLITS:
            raise AdapterError(f"--split is one of {list(SPLITS)}, not {split!r}")
        if agent_network not in ("public", "allowlist"):
            raise AdapterError(f"--agent-network is public or allowlist, not {agent_network!r}")
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.repo = Path(repo)
        self.cases_root = Path(cases_root) if cases_root else self.repo / "cases"
        self.data_root = Path(data_root) if data_root else self.repo / "data"
        self.split = split
        self.agent_image = agent_image
        self.scorer_image = scorer_image
        self.agent_network = agent_network
        self.agent_allowed_hosts = list(agent_allowed_hosts or [])
        self.skip_incomplete = skip_incomplete

    # -- case selection ------------------------------------------------------------

    def discover(self) -> list[Case]:
        """Every case with a reference video under the cases root, in a stable order."""

        if not self.cases_root.is_dir():
            raise AdapterError(
                f"cases root does not exist: {self.cases_root} (run the upstream "
                "scripts/download_data.py, or pass --cases-root)")
        kinds = KINDS if self.split == "all" else (self.split,)
        found = [Case(kind, directory.name)
                 for kind in kinds if (self.cases_root / kind).is_dir()
                 for directory in sorted((self.cases_root / kind).iterdir())
                 if (directory / "reference.mp4").is_file()]
        if not found:
            raise AdapterError(f"no <kind>/<case>/reference.mp4 under {self.cases_root} for split {self.split!r}")
        ids = [case.task_id for case in found]
        clashes = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
        if clashes:
            raise AdapterError(f"cases map to the same task name: {clashes}")
        return found

    def select(self, cases: list[Case]) -> list[Case]:
        """Apply `task_ids` (task names, `<kind>/<case>` or bare case names) and `limit`."""

        if self.task_ids:
            wanted = set(self.task_ids)
            chosen = [case for case in cases
                      if wanted & {case.task_id, case.key, case.name, f"4dcodebench/{case.task_id}"}]
            matched = {name for case in chosen
                       for name in (case.task_id, case.key, case.name, f"4dcodebench/{case.task_id}")}
            unknown = sorted(wanted - matched)
            if unknown:
                raise AdapterError(f"unknown task ids: {unknown}")
            cases = chosen
        return cases[: self.limit] if self.limit is not None else cases

    def missing_data(self, case: Case) -> list[str]:
        base = self.data_root / case.key
        return [name for name in required_data(case.kind, base) if not (base / name).exists()]

    # -- generation ----------------------------------------------------------------

    def run(self) -> list[Path]:
        """Generate the selected tasks; return their directories."""

        cases = self.select(self.discover())
        # every selected case is checked before anything is written
        incomplete = {case.key: missing for case in cases if (missing := self.missing_data(case))}
        if incomplete and not self.skip_incomplete:
            listed = "; ".join(f"{key}: {missing}" for key, missing in incomplete.items())
            raise AdapterError(f"reference data missing under {self.data_root}: {listed} (download it with "
                               "the upstream scripts/download_data.py --estimates, or pass --skip-incomplete)")
        for key, missing in incomplete.items():
            logger.warning("skipping %s: reference data missing: %s", key, missing)
        commit = checkout_commit(self.repo)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for case in cases:
            if case.key in incomplete:
                continue
            target = self.output_dir / case.task_id
            if target.exists():
                if not self.overwrite:
                    logger.info("exists, kept (pass --overwrite to regenerate): %s", target)
                    continue
                shutil.rmtree(target)
            self.generate(case, target, commit)
            written.append(target)
            logger.info("wrote %s", target)
        (self.output_dir / METRIC_SCRIPT.name).write_text(
            METRIC_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        logger.info("%d task(s) written, %d skipped for missing data, under %s",
                    len(written), len(incomplete), self.output_dir)
        return written

    def generate(self, case: Case, target: Path, commit: str) -> None:
        partial = target.with_name(target.name + ".partial")
        shutil.rmtree(partial, ignore_errors=True)
        partial.mkdir(parents=True)
        try:
            self._write_task(case, partial, commit)
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise
        partial.rename(target)

    def _values(self, case: Case, commit: str) -> dict[str, object]:
        return {
            "case_key": case.key,
            "case_name": case.name,
            "kind": case.kind,
            "task_id": case.task_id,
            "upstream_url": UPSTREAM_URL,
            "upstream_commit": commit,
            "oracle": "reference-world" if case.kind == "synthetic" else "unresolved",
            "agent_image": self.agent_image,
            "scorer_image": self.scorer_image,
            "agent_timeout_sec": AGENT_TIMEOUT_SEC,
            "verifier_timeout_sec": VERIFIER_TIMEOUT_SEC,
            "build_timeout_sec": BUILD_TIMEOUT_SEC,
            "agent_network": self._agent_network_toml(),
        }

    def _agent_network_toml(self) -> str:
        """The `[agent]` network lines: none for the upstream default (public)."""
        if self.agent_network == "public":
            return ""
        hosts = ", ".join(json.dumps(host) for host in self.agent_allowed_hosts)
        return f'network_mode = "allowlist"\nallowed_hosts = [{hosts}]\n'

    def _render_file(self, name: str, target: Path, values: dict[str, object] | None,
                     executable: bool = False) -> None:
        """Write template file `name` to `target`, rendered unless `values` is None."""
        text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        if values is not None:
            text = render(text, values)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        if executable:
            target.chmod(0o755)

    def _write_task(self, case: Case, task: Path, commit: str) -> None:
        values = self._values(case, commit)
        video = self.cases_root / case.key / "reference.mp4"
        data = self.data_root / case.key

        # agent side: instruction, /task context and the reference video
        environment = task / "environment"
        environment.mkdir()
        task_md = render_agent_context(self.repo, environment / "task")
        values["task_md"] = task_md.rstrip("\n")
        copy_entry(video, environment / "input" / "reference.mp4")
        self._render_file("environment/Dockerfile", environment / "Dockerfile", values)
        self._render_file("environment/docker-compose.yaml", environment / "docker-compose.yaml", None)
        self._render_file("instruction.md", task / "instruction.md", values)
        self._render_file("task.toml", task / "task.toml", values)

        # verifier side: the scorer entry point and the case's reference data
        tests = task / "tests"
        self._render_file("tests/Dockerfile", tests / "Dockerfile", values)
        self._render_file("tests/docker-compose.yaml", tests / "docker-compose.yaml", None)
        self._render_file("tests/run_verifier.py", tests / "run_verifier.py", None)
        self._render_file("tests/test.sh", tests / "test.sh", None, executable=True)
        (tests / "rewards.py").write_text(REWARDS_MODULE.read_text(encoding="utf-8"),
                                          encoding="utf-8", newline="\n")
        (tests / "case.json").write_text(json.dumps({
            "case": case.key,
            "kind": case.kind,
            "upstream_commit": commit,
            "required_data": list(required_data(case.kind, data)),
            "task_timeout_sec": TASK_TIMEOUT_SEC,
            "task_prepare_timeout_sec": TASK_PREPARE_TIMEOUT_SEC,
        }, indent=2) + "\n", encoding="utf-8", newline="\n")
        copy_entry(video, tests / "bench" / "cases" / case.key / "reference.mp4")
        for name in DATA_ENTRIES[case.kind]:
            copy_entry(data / name, tests / "bench" / "data" / case.key / name)

        # oracle: the published reference world (synthetic), or explicitly unresolved (real)
        solution = task / "solution"
        if case.kind == "synthetic":
            self._render_file("solution/solve.sh", solution / "solve.sh", values, executable=True)
            self._render_file("solution/build.sh", solution / "build.sh", None, executable=True)
            copy_entry(data / "world", solution / "world")
        else:
            self._render_file("solution/solve_unresolved.sh", solution / "solve.sh", values, executable=True)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
