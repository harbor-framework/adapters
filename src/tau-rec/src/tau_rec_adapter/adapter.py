"""Generate Harbor tasks from the tau-Rec movies-v1 benchmark (tau-Rec v2.1.0)."""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
from pathlib import Path

DIFFICULTY_BY_COMPLEXITY = {"simple": "easy", "medium": "medium", "complex": "hard"}

TAU_REC_REPO_URL = "https://github.com/nbharaths/tau-rec"
TAU_REC_TAG = "v2.1.0"
TAU_REC_COMMIT = "8b4c3e6823add74f6c209fff864e2eae6849880c"
# tau_rec.domain.MOVIES.restricted_ratings at TAU_REC_COMMIT: recommending an
# item with one of these ratings needs a check_content_preference call first.
RESTRICTED_RATINGS = ("R", "NC-17")

# The adapter project directory, src/tau-rec/ in the adapters repository.
ADAPTER_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = Path(__file__).parent / "task-template"


class TauRecAdapter:
    """Writes one Harbor task per movies-v1 task into ``output_dir``.

    The tasks are read from a tau-Rec checkout at ``TAU_REC_COMMIT``: the
    ``tau_rec_root`` argument, else ``$TAU_REC_ROOT``, else a clone of
    ``TAU_REC_TAG`` under ``src/tau-rec/.cache/tau-rec``. A checkout at any other
    commit is rejected.
    """

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.template_dir = Path(kwargs.get("template_dir") or TEMPLATE_DIR)
        self.tau_rec_root = resolve_tau_rec_root(kwargs.get("tau_rec_root"))
        self._data_dir = self.tau_rec_root / "data"

    def _load_task(self, task_id: str) -> dict:
        return json.loads((self._data_dir / "tasks" / f"{task_id}.json").read_text())

    @functools.cached_property
    def _catalog(self) -> dict[str, dict]:
        items = json.loads((self._data_dir / "catalog.json").read_text())
        return {item["id"]: item for item in items}

    def oracle_plan(self, task_id: str) -> dict:
        """The scripted perfect agent's plan for one task.

        The item is the first gold solution the user has not watched: a
        reachable solution, else a constraint solution. Abstain tasks have none.
        """
        task = self._load_task(task_id)
        answers = json.loads((self._data_dir / "answers.json").read_text())[task_id]
        plan = {
            "abstain": bool(task["no_valid_recommendation"]),
            "item_id": None,
            "user_id": task["user_id"],
            "content_rating": None,
            "restricted": False,
            "sponsored": False,
            "title": None,
            # check_availability's required ``services`` argument: the user's
            # streaming services, as the task states them.
            "services": list(task.get("user_services") or []),
        }
        if plan["abstain"]:
            return plan
        watched = (
            (task.get("user_history") or {}).get(task["user_id"], {}).get("watched", [])
        )
        seen = {w["id"] if isinstance(w, dict) else w for w in watched}
        pool = [
            i
            for gold in (
                answers["reachable_solutions"],
                answers["constraint_solutions"],
            )
            for i in gold
            if i not in seen
        ]
        if not pool:
            raise ValueError(f"{task_id}: no unwatched gold solution to recommend")
        item = self._catalog[pool[0]]
        plan.update(
            item_id=item["id"],
            content_rating=item["content_rating"],
            restricted=item["content_rating"] in RESTRICTED_RATINGS,
            sponsored=bool(item["sponsored"]),
            title=item["title"],
        )
        return plan

    def available_task_ids(self) -> list[str]:
        """All task ids in the movies-v1 task set, sorted."""
        return sorted(p.stem for p in (self._data_dir / "tasks").glob("*.json"))

    def run(self) -> list[Path]:
        """Write the selected tasks under ``self.output_dir``; return their paths."""
        available = self.available_task_ids()
        if self.task_ids is not None:
            unknown = sorted(set(self.task_ids) - set(available))
            if unknown:
                raise ValueError(f"Unknown task ids: {', '.join(unknown)}")
            selected = list(dict.fromkeys(self.task_ids))
        else:
            selected = available
        if self.limit is not None:
            selected = selected[: max(0, self.limit)]

        targets = [self.output_dir / task_id for task_id in selected]
        if not self.overwrite:
            existing = [t.name for t in targets if t.exists()]
            if existing:
                raise FileExistsError(
                    f"Task directories already exist (use --overwrite): {', '.join(existing)}"
                )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        policy = (self._data_dir / "policy.md").read_text().strip()
        for task_id, target in zip(selected, targets):
            self._generate_one(task_id, target, policy)
        return targets

    def _generate_one(self, task_id: str, target: Path, policy: str) -> None:
        task = self._load_task(task_id)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.template_dir, target)

        difficulty = DIFFICULTY_BY_COMPLEXITY[task["complexity"]]
        self._render(
            target / "task.toml", {"{task_id}": task_id, "{difficulty}": difficulty}
        )
        self._render(
            target / "instruction.md",
            {"{user_id}": task["user_id"], "{policy}": policy},
        )
        (target / "environment" / "runtime-server" / "task_config.json").write_text(
            json.dumps({"task_id": task_id}, indent=2) + "\n"
        )
        (target / "solution" / "oracle_plan.json").write_text(
            json.dumps(self.oracle_plan(task_id), indent=2) + "\n"
        )
        (target / "tests" / "config.json").write_text(
            json.dumps({"task_id": task_id}, indent=2) + "\n"
        )

    @staticmethod
    def _render(path: Path, replacements: dict[str, str]) -> None:
        text = path.read_text()
        for key, value in replacements.items():
            text = text.replace(key, value)
        path.write_text(text)


def checkout_commit(root: Path) -> str:
    """``git rev-parse HEAD`` of ``root``; raises if it is not a git checkout."""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("`git` is needed to check the tau-Rec checkout") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"{root} is not a git checkout of tau-Rec {TAU_REC_TAG}: "
            f"{exc.stderr.strip()}"
        ) from exc
    return done.stdout.strip()


def verify_checkout(root: Path) -> Path:
    """``root`` if it is a tau-Rec checkout at ``TAU_REC_COMMIT``, else raise."""
    root = Path(root).expanduser().resolve()
    if not (root / "data" / "tasks").is_dir():
        raise ValueError(f"{root} is not a tau-Rec checkout (no data/tasks)")
    head = checkout_commit(root)
    if head != TAU_REC_COMMIT:
        raise ValueError(
            f"{root} is at commit {head}, but the adapter is pinned to tau-Rec "
            f"{TAU_REC_TAG} ({TAU_REC_COMMIT}); check out {TAU_REC_TAG} there"
        )
    return root


def clone_tau_rec(destination: Path) -> Path:
    """Shallow-clone ``TAU_REC_TAG`` into ``destination`` (must not exist)."""
    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        TAU_REC_TAG,
        TAU_REC_REPO_URL,
        str(destination),
    ]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"No tau-Rec checkout given and `git` is not available to clone "
            f"{TAU_REC_REPO_URL}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Could not clone tau-Rec {TAU_REC_TAG} from {TAU_REC_REPO_URL} "
            f"into {destination}"
        ) from exc
    return destination


def resolve_tau_rec_root(configured: str | Path | None = None) -> Path:
    """The verified tau-Rec checkout: ``configured``, ``$TAU_REC_ROOT``, or a
    cached clone of the pinned tag under ``src/tau-rec/.cache/tau-rec``."""
    if configured is None:
        configured = os.environ.get("TAU_REC_ROOT") or None
    if configured is not None:
        return verify_checkout(Path(configured))
    cached = ADAPTER_ROOT / ".cache" / "tau-rec"
    if not cached.exists():
        clone_tau_rec(cached)
    return verify_checkout(cached)
