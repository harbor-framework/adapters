import json
import shutil
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

from . import sources

TEMPLATE = Path(__file__).with_name("task-template")


def write(path, value):
    path.write_text(value, encoding="utf-8", newline="\n")


def existing_task(path: Path, identity: dict) -> bool:
    """Recognize outputs from this adapter, including older markers with extra fields."""
    config = path / "task.toml"
    case = path / "tests" / "case.json"
    if path.is_symlink() or path.is_junction():
        raise ValueError(f"Existing path is a link: {path}")
    if not path.exists():
        return False
    if any(p.is_symlink() or p.is_junction() for p in (config, case.parent, case)):
        raise ValueError(f"Existing task metadata is a link: {path}")
    if not config.is_file() or not case.is_file():
        raise ValueError(f"Existing path is not the expected generated task: {path}")
    try:
        task = tomllib.loads(config.read_text(encoding="utf-8"))
        marker = json.loads(case.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"Existing path is not the expected generated task: {path}") from exc
    if (not isinstance(task.get("task"), dict)
            or task["task"].get("name") != f"control-arena/{path.name}"
            or not isinstance(marker, dict)
            or any(marker.get(key) != value for key, value in identity.items())):
        raise ValueError(f"Existing task identity differs: {path}")
    return True


class ControlArenaVllmHonestAdapter:
    def __init__(self, output_dir, source_cache=Path(".cache/control-arena-vllm-honest"), limit=None, task_ids=None, overwrite=False):
        self.output_dir = Path(output_dir)
        self.source_cache = Path(source_cache)
        self.limit = limit
        self.task_ids = task_ids
        self.overwrite = overwrite

    def run(self) -> list[Path]:
        if self.limit is not None and self.limit < 0:
            raise ValueError("--limit must be nonnegative")
        if self.task_ids is not None and any(s.removeprefix("control-arena/") != sources.SLUG for s in self.task_ids):
            raise ValueError("Only the pinned vLLM rolling metrics task is supported")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.limit == 0 or self.task_ids == []:
            return []
        path = self.output_dir / sources.SLUG
        identity = {"title": sources.TITLE, "parent_revision": sources.BASE, "prompt_sha256": sources.PROMPT_SHA}
        if existing_task(path, identity) and not self.overwrite:
            return [path]
        row = sources.materialize(self.source_cache)
        with TemporaryDirectory(dir=self.output_dir) as temp:
            staging = Path(temp) / "new"
            shutil.copytree(TEMPLATE, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            instructions = staging / "instruction.md"
            write(instructions, instructions.read_text("utf-8").replace("{prompt}", row["task_instructions"]))
            shutil.copyfile(self.source_cache / "baseline.py", staging / "environment" / "loggers.py")
            shutil.copyfile(self.source_cache / "LICENSE", staging / "environment" / "LICENSE")
            shutil.copyfile(self.source_cache / "baseline.py", staging / "tests" / "baseline.py")
            shutil.copyfile(self.source_cache / "reference.py", staging / "solution" / "loggers.py")
            write(staging / "tests" / "case.json", json.dumps({"title": sources.TITLE, "prompt": row["task_instructions"],
                  "prompt_sha256": sources.PROMPT_SHA, "baseline_sha256": sources.BASE_SHA, "reference_sha256": sources.GOLD_SHA,
                  "source": sources.SOURCE, "dataset_revision": sources.REVISION, "parent_revision": sources.BASE}))
            for script in staging.rglob("*.sh"):
                write(script, script.read_text("utf-8"))
                script.chmod(0o755)
            previous = Path(temp) / "previous"
            if existing_task(path, identity):
                if not self.overwrite:
                    return [path]
                path.rename(previous)
            try:
                staging.rename(path)
            except OSError:
                if previous.exists():
                    previous.rename(path)
                raise
        return [path]
