"""FM-Bench (Solo track) -> a Harbor task.

The dataset is one task: one agent manages a club for a fixed number of in-game
seasons against 15 scripted clubs, in one fixed world. The engine goes into a
`game` sidecar; the agent container gets the rulebook, the tool schemas and an
HTTP client.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "task-template"
ORACLE_DATA = HERE / "oracle_data"
YEARS = 20
# The world the task is played in. Seed 1 is FM-Bench's public reference world.
# The score subtracts each world's starting endowment, so another seed is a
# replicate of the same task, not a different task: repeated attempts
# (`harbor run -k N`) take the place of more seeds. The seed must stay fixed,
# because the oracle log and the reference score belong to one world.
SEED = 1
TASK_ID = f"fm-bench-solo-{YEARS}y"
# 20 in-game years is several hundred stops; a model run takes hours
AGENT_TIMEOUT_SEC = 43200.0
# engine pieces the sidecar needs (nothing from runner/, baselines/, results/)
ENGINE_PARTS = ("engine", "score", "params.yaml")
# what a directory must hold to count as an FM-Bench checkout
CHECKOUT_PARTS = (*ENGINE_PARTS, "rules.md")
# The public FM-Bench repository, and the commit the oracle action logs in
# oracle_data/ were recorded on (the replay is only exact on that engine).
# Empty until the repository is public: until then the source comes from
# --fmbench-root, --fmbench-repo, or a checkout around the working directory.
UPSTREAM_REPO = ""
UPSTREAM_REF = ""


class AdapterError(Exception):
    """A problem the user can fix from the command line."""


def references() -> dict:
    """The oracle's recorded score and the reward reference for the task's seed.

    Written by harbor_adapter/record_oracle.py in the FM-Bench repository,
    together with the action log.
    """
    return json.loads((ORACLE_DATA / "reference_scores.json").read_text(encoding="utf-8"))


def is_checkout(path: Path) -> bool:
    """Whether `path` holds the engine, the scorer, the parameters and the rulebook."""
    return all((path / part).exists() for part in CHECKOUT_PARTS)


def find_checkout() -> Path | None:
    """An FM-Bench checkout that contains the working directory or this adapter."""
    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents, *HERE.parents):
        if is_checkout(path):
            return path
    return None


def clone_checkout(repo: str, ref: str | None, dest: Path) -> Path:
    """Clone `repo` into `dest`; check out `ref` (a commit, tag or branch) if given."""
    # a commit id cannot be fetched shallowly from every server, so a pinned
    # ref costs a full clone
    depth = [] if ref else ["--depth", "1"]
    steps = [["git", "clone", "--quiet", *depth, repo, str(dest)]]
    if ref:
        steps.append(["git", "-C", str(dest), "checkout", "--quiet", ref])
    for cmd in steps:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError as e:
            raise AdapterError("git is needed to clone the FM-Bench source") from e
        except subprocess.CalledProcessError as e:
            raise AdapterError(
                f"{' '.join(cmd)} failed: {(e.stderr or '').strip()[-400:]}") from e
    if not is_checkout(dest):
        raise AdapterError(f"{repo} is not an FM-Bench repository "
                           f"(missing one of {', '.join(CHECKOUT_PARTS)})")
    return dest


def _token(tid: str) -> str:
    """The token the verifier shows the sidecar to read the settled result.

    It keeps an agent from settling the game by accident; it is not a secret,
    the dataset is public.
    """
    # deterministic, so regenerating the dataset does not churn registry digests
    return hashlib.sha256(f"fm-bench-result:{tid}".encode()).hexdigest()


def _fill(path: Path, values: dict) -> None:
    """Replace each {name} placeholder in a template file with its value.

    Plain replacement, not str.format: the files hold other braces (TOML
    inline tables, JSON examples) that must stay as they are.
    """
    text = path.read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{" + k + "}", str(v))
    path.write_text(text, encoding="utf-8", newline="\n")


def _tool_schemas(fmbench_root: Path) -> list[dict]:
    """The tool schemas the original harness gives the model, from the engine."""
    sys.path.insert(0, str(fmbench_root))
    try:
        from engine.actions.commands import tool_schemas
        return tool_schemas()
    finally:
        sys.path.remove(str(fmbench_root))


def generate(output_dir: Path, fmbench_root: Path, overwrite: bool) -> Path:
    """Write the task directory under `output_dir` and return its path.

    The template is copied as it is. The engine goes into the sidecar's build
    context only; the agent's build context gets the rulebook and the tool
    schemas. The recorded oracle log goes into solution/.
    """
    dest = output_dir / TASK_ID
    if dest.exists():
        if not overwrite:
            raise FileExistsError(f"{dest} exists (use --overwrite)")
        shutil.rmtree(dest)
    log = ORACLE_DATA / f"actions_s{SEED}.jsonl.gz"
    if not log.exists():
        raise FileNotFoundError(f"no oracle action log for seed {SEED}: {log}")
    for part in ENGINE_PARTS:
        if not (fmbench_root / part).exists():
            raise FileNotFoundError(
                f"{fmbench_root} is not an FM-Bench checkout (missing {part})")

    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns("__pycache__"))
    env = dest / "environment"
    # sidecar build context: the engine, the scorer and the parameters
    game = env / "game" / "fmbench"
    game.mkdir(parents=True)
    for part in ENGINE_PARTS:
        src = fmbench_root / part
        if src.is_dir():
            shutil.copytree(src, game / part,
                            ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, game / part)
    # agent build context: what the original harness shows the model
    shutil.copy2(fmbench_root / "rules.md", env / "rules.md")
    (env / "tools.json").write_text(
        json.dumps(_tool_schemas(fmbench_root), indent=1, sort_keys=True),
        encoding="utf-8", newline="\n")
    shutil.copy2(log, dest / "solution" / "actions.jsonl.gz")

    # the reference is the oracle's own score in this world: reward = S_final / reference
    values = {"task_id": TASK_ID, "seed_id": SEED, "seed": SEED, "years": YEARS,
              "reference": references()["reference"][str(SEED)],
              "result_token": _token(TASK_ID), "agent_timeout": AGENT_TIMEOUT_SEC}
    for rel in ("task.toml", "instruction.md", "environment/docker-compose.yaml"):
        _fill(dest / rel, values)
    return dest


class FMBenchAdapter:
    """Writes the one Harbor task of the FM-Bench Solo track."""

    def __init__(self, output_dir: Path, limit: int | None = None,
                 overwrite: bool = False, task_ids: list[str] | None = None,
                 split: str = "full", fmbench_root: Path | None = None,
                 fmbench_repo: str | None = None, fmbench_ref: str | None = None,
                 **kwargs):
        """
        Args:
            output_dir: directory the task directories are written to.
            limit: generate only the first N tasks.
            overwrite: replace task directories that already exist.
            task_ids: generate only these task ids.
            split: "full" or "parity"; both are the one task.
            fmbench_root: a local FM-Bench checkout to read the engine from.
            fmbench_repo: a git URL to clone the engine from instead.
            fmbench_ref: the commit, tag or branch to check out after cloning.
        """
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.split = split
        self.fmbench_root = Path(fmbench_root) if fmbench_root else None
        self.fmbench_repo = fmbench_repo
        self.fmbench_ref = fmbench_ref

    def selected(self) -> bool:
        """Whether this run writes the task, after --task-ids and --limit."""
        if self.task_ids:
            unknown = set(self.task_ids) - {TASK_ID}
            if unknown:
                raise AdapterError(f"unknown task ids: {sorted(unknown)} "
                                   f"(the only task is {TASK_ID})")
        return self.limit is None or self.limit > 0

    def _source(self, scratch: Path) -> Path:
        """Where the engine comes from: an explicit checkout, an explicit
        repository, a checkout around the working directory or this adapter,
        then the pinned upstream repository."""
        if self.fmbench_root is not None:
            root = self.fmbench_root.resolve()
            if not is_checkout(root):
                raise AdapterError(f"{root} is not an FM-Bench checkout "
                                   f"(it needs {', '.join(CHECKOUT_PARTS)})")
            return root
        if self.fmbench_repo:
            return clone_checkout(self.fmbench_repo, self.fmbench_ref, scratch / "FM-Bench")
        found = find_checkout()
        if found is not None:
            return found
        if UPSTREAM_REPO:
            return clone_checkout(UPSTREAM_REPO, self.fmbench_ref or UPSTREAM_REF,
                                  scratch / "FM-Bench")
        raise AdapterError(
            "no FM-Bench source found: pass --fmbench-root <checkout> (or set "
            "FMBENCH_ROOT), or --fmbench-repo <git url> (or set FMBENCH_REPO)")

    def run(self) -> list[Path]:
        """Generate the task under self.output_dir; return the directories written."""
        if not self.selected():
            return []
        dest = self.output_dir / TASK_ID
        if dest.exists() and not self.overwrite:
            raise AdapterError(f"{dest} exists (use --overwrite)")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="fm_bench_src_") as scratch:
            root = self._source(Path(scratch))
            print(f"FM-Bench source: {root}")
            return [generate(self.output_dir, root, self.overwrite)]
