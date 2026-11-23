"""Generate the frozen 50-episode BALROG BabyAI subset."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile


PACKAGE_DIR = Path(__file__).resolve().parent
TASK_ID = "babyai-goto-seed-0"
TASK_TYPES = ("goto", "pickup", "open", "putnext", "pick_up_seq_go_to")
ACTION_STRINGS = {"turn left", "turn right", "go forward", "pick up", "drop", "toggle"}
BALROG_COMMIT = "b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5"
MINIGRID_COMMIT = "cf73dd148e51276bd675a37e3bfb0bf2b42329b2"
SOURCE_PATHS = {
    BALROG_COMMIT: ("balrog", "LICENSE", "README.md", "pyproject.toml", "setup.py"),
    MINIGRID_COMMIT: ("minigrid", "LICENSE", "README.md", "pyproject.toml", "setup.py"),
}
EXCLUDED_COMPONENTS = {
    "secrets", ".git", "__pycache__", ".venv", ".env",
    ".github", "docs", "examples", "media", "tests",
}


def default_source_directory(name: str) -> Path:
    """Find the documented sibling-checkout layout when running from source."""
    for parent in PACKAGE_DIR.parents:
        candidate = parent / name
        if (candidate / ".git").exists():
            return candidate
    return Path.cwd() / name


def _is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _check_plain_tree(path: Path) -> None:
    """Reject links and Windows junctions before copying or removing a tree."""
    if _is_link(path):
        raise ValueError(f"Refusing symlink or junction: {path}")
    if not path.is_dir():
        raise ValueError(f"Expected a directory: {path}")
    for root, directories, files in os.walk(path, followlinks=False):
        for name in directories + files:
            entry = Path(root) / name
            if _is_link(entry):
                raise ValueError(f"Refusing symlink or junction: {entry}")


def _git(source: Path, *arguments: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(source), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except FileNotFoundError as exc:
        raise ValueError("Git is required to archive the pinned benchmark sources") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Cannot read source checkout {source}: {detail}") from exc


def _source_archive(source: Path, commit: str) -> bytes:
    """Archive committed files only; never include credentials or local changes."""
    actual = _git(source, "rev-parse", "HEAD").decode("ascii").strip()
    if actual != commit:
        raise ValueError(f"Wrong source commit in {source}: expected {commit}, got {actual}")
    # Both setup.py files read README.md; Minigrid reads its package __init__.py
    # for the version. Keep whole runtime packages, including package assets.
    included = SOURCE_PATHS[commit]
    raw = _git(source, "-c", "core.autocrlf=false", "archive", "--format=tar", commit, *included)
    result = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        with tarfile.open(fileobj=result, mode="w:", format=tarfile.PAX_FORMAT) as filtered:
            for member in archive:
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError(f"Unsafe source archive member: {member.name}")
                if not path.parts or path.parts[0] not in included:
                    continue
                if any(
                    part.lower() in EXCLUDED_COMPONENTS
                    or part.lower().startswith(".env.")
                    for part in path.parts
                ):
                    continue
                if not (member.isfile() or member.isdir()):
                    raise ValueError(f"Unsupported source archive link or device: {member.name}")
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                member.mtime = 0
                member.pax_headers = {}
                filtered.addfile(member, archive.extractfile(member) if member.isfile() else None)
    # GzipFile also fixes the OS header byte across host platforms (unlike the
    # Python 3.12 gzip.compress(mtime=0) shortcut through the system zlib).
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=compressed, mode="wb", mtime=0) as stream:
        stream.write(result.getvalue())
    return compressed.getvalue()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def load_manifest() -> dict:
    """Validate the complete preselected scope, rather than filtering successful cases."""
    path = PACKAGE_DIR / "fixtures" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("source_commits") != {
        "balrog": BALROG_COMMIT, "minigrid": MINIGRID_COMMIT,
    }:
        raise ValueError("Fixture manifest schema or source commits do not match this adapter")
    if manifest.get("task_types") != list(TASK_TYPES) or manifest.get("seeds") != list(range(10)):
        raise ValueError("Fixture scope must contain all five task types and seeds 0..9")
    expected = [
        (f"BabyAI-MixedTrainLocal-v0/{kind}", seed)
        for seed in range(10) for kind in TASK_TYPES
    ]
    cases = manifest.get("cases", [])
    if len(cases) != len(expected):
        raise ValueError("Fixture manifest must contain exactly 50 episodes")
    ids = []
    for case, (task, seed) in zip(cases, expected):
        episode, oracle = case["episode"], case["oracle"]
        kind = task.split("/")[1]
        task_id = f"babyai-{kind.replace('_', '-')}-seed-{seed}"
        if (episode["task"], episode["seed"], episode["task_id"]) != (task, seed, task_id):
            raise ValueError(f"Fixture ordering, task, or seed differs for {task_id}")
        ids.append(task_id)
        expected_budget = 64 if kind in ("goto", "pickup") else 128
        if episode["babyai_kwargs"] != {"num_dists": 0} or episode["expected_max_steps"] != expected_budget:
            raise ValueError(f"Fixture environment settings differ for {task_id}")
        initial_hash = episode["expected_initial_observation_sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", initial_hash):
            raise ValueError(f"Invalid initial observation checksum for {task_id}")
        if oracle["expected_initial_observation_sha256"] != initial_hash:
            raise ValueError(f"Oracle and episode initial checksums differ for {task_id}")
        actions, transitions = oracle["actions"], oracle["expected_transitions"]
        if not 0 < len(actions) == len(transitions) <= expected_budget:
            raise ValueError(f"Invalid oracle trajectory length for {task_id}")
        for index, (action, transition) in enumerate(zip(actions, transitions)):
            if action not in ACTION_STRINGS or transition["executed_action"] != action:
                raise ValueError(f"Invalid oracle action at {task_id}:{index}")
            if not re.fullmatch(r"[0-9a-f]{64}", transition["observation"]):
                raise ValueError(f"Invalid oracle observation checksum at {task_id}:{index}")
            if transition["truncated"] or transition["terminated"] != (index == len(actions) - 1):
                raise ValueError(f"Unexpected oracle termination at {task_id}:{index}")
            if (transition["reward"] > 0) != (index == len(actions) - 1):
                raise ValueError(f"Unexpected oracle reward at {task_id}:{index}")
        if oracle["expected_progression"] != 1.0:
            raise ValueError(f"Oracle fixture has not passed validation: {task_id}")
    expected_splits = {"full": ids, "parity": ids, "sanity": ids[:len(TASK_TYPES)]}
    if manifest.get("splits") != expected_splits:
        raise ValueError("Fixture splits must be full/parity=50 and sanity=seed 0 for each type")
    return manifest


def select_cases(split: str, task_ids: list[str] | None, limit: int | None) -> list[dict]:
    if limit is not None and limit < 0:
        raise ValueError("--limit must be nonnegative")
    manifest = load_manifest()
    if split not in manifest["splits"]:
        raise ValueError(f"Unknown split: {split}; choose full, sanity, or parity")
    available = set(manifest["splits"]["full"])
    selected = set(manifest["splits"][split])
    if task_ids:
        unknown = set(task_ids) - available
        if unknown:
            raise ValueError(f"Unknown task IDs: {', '.join(sorted(unknown))}")
        outside_split = set(task_ids) - selected
        if outside_split:
            raise ValueError(f"Task IDs are outside split {split}: {', '.join(sorted(outside_split))}")
        selected.intersection_update(task_ids)
    cases = [case for case in manifest["cases"] if case["episode"]["task_id"] in selected]
    return cases if limit is None else cases[:limit]


class BALROGAdapter:
    """Convert the fixed BabyAI manifest into self-contained Harbor task directories."""

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        benchmark_source: Path | None = None,
        minigrid_source: Path | None = None,
        split: str = "full",
        environments: list[str] | None = None,
        assets_dir: Path | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.benchmark_source = benchmark_source or default_source_directory("BALROG")
        self.minigrid_source = minigrid_source or default_source_directory("minigrid-source")
        self.split = split
        self.environments = environments or ["babyai"]
        self.assets_dir = assets_dir

    def _check_destination(self, output: Path, task_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", task_id):
            raise ValueError(f"Unsafe task ID: {task_id}")
        destination = output / task_id
        if destination.parent != output or destination.resolve().parent != output:
            raise ValueError(f"Task destination escapes the output directory: {destination}")
        if destination.exists() or _is_link(destination):
            _check_plain_tree(destination)
            if not self.overwrite:
                raise FileExistsError(f"Task already exists: {destination}; pass --overwrite to replace it")
        return destination

    def run(self) -> list[Path]:
        if self.environments != ["babyai"]:
            from .suite import generate_suite
            return generate_suite(self)
        cases = select_cases(self.split, self.task_ids, self.limit)
        if not cases:
            return []
        # Resolve the caller's output root once, then operate only on manifest IDs.
        output = self.output_dir.expanduser().absolute()
        for ancestor in (output, *output.parents):
            if _is_link(ancestor):
                raise ValueError(f"Refusing output directory through a symlink or junction: {ancestor}")
        output = output.resolve()
        # Preflight every selected destination before creating or replacing any task.
        destinations = [self._check_destination(output, case["episode"]["task_id"]) for case in cases]
        template = PACKAGE_DIR / "task-template"
        _check_plain_tree(template)
        # Each source archive is computed once per invocation and reused in memory.
        # Every emitted task still receives independent files, with no shared mounts.
        archives = {
            "balrog": _source_archive(Path(self.benchmark_source), BALROG_COMMIT),
            "minigrid": _source_archive(Path(self.minigrid_source), MINIGRID_COMMIT),
        }
        source_manifest = {
            name: {
                "commit": BALROG_COMMIT if name == "balrog" else MINIGRID_COMMIT,
                "archive": f"{name}.tar.gz",
                "sha256": hashlib.sha256(archive).hexdigest(),
                "included": list(SOURCE_PATHS[BALROG_COMMIT if name == "balrog" else MINIGRID_COMMIT]),
                "excluded_path_components_case_insensitive": sorted(EXCLUDED_COMPONENTS),
                "excluded_name_prefixes_case_insensitive": [".env."],
            }
            for name, archive in archives.items()
        }
        output.mkdir(parents=True, exist_ok=True)
        for case, destination in zip(cases, destinations):
            episode, oracle = case["episode"], case["oracle"]
            task_id = episode["task_id"]
            replacements = {"__TASK_ID__": task_id, "__RESULT_TOKEN__": secrets.token_hex(32)}
            with tempfile.TemporaryDirectory(prefix=f".{task_id}-", dir=output) as temporary:
                staged = Path(temporary) / task_id
                shutil.copytree(template, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                for path in staged.rglob("*"):
                    if path.is_file():
                        # Literal replacement leaves Python braces alone.
                        content = path.read_text(encoding="utf-8")
                        for placeholder, value in replacements.items():
                            content = content.replace(placeholder, value)
                        path.write_text(content, encoding="utf-8", newline="\n")
                from .runtime_locks import stage_runtime_lock
                stage_runtime_lock(PACKAGE_DIR, "babyai", staged / "environment")
                (staged / "environment" / "vendor").mkdir(parents=True, exist_ok=True)
                _write_json(staged / "environment" / "episode.json", episode)
                _write_json(staged / "tests" / "task_config.json", episode)
                _write_json(staged / "solution" / "oracle_actions.json", oracle)
                for name, archive in archives.items():
                    (staged / "environment" / "vendor" / f"{name}.tar.gz").write_bytes(archive)
                _write_json(staged / "environment" / "vendor" / "manifest.json", source_manifest)
                # Revalidate immediately before deleting exactly this manifest task.
                self._check_destination(output, task_id)
                if destination.exists():
                    shutil.rmtree(destination)
                staged.rename(destination)
        return destinations
