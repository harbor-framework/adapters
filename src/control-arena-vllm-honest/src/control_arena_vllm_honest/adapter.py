import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from . import sources

TEMPLATE = Path(__file__).with_name("task-template")


def write(path, value):
    path.write_text(value, encoding="utf-8", newline="\n")


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
        if path.exists() and not self.overwrite:
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
            if path.exists():
                path.rename(previous)
            try:
                staging.rename(path)
            except OSError:
                if previous.exists():
                    previous.rename(path)
                raise
        return [path]
