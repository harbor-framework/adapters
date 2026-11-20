"""Generate Harbor tasks from the JobBench dataset on Hugging Face.

Each upstream task is a directory ``<split dir>/<occupation>/taskN/`` holding a
``task_folder/`` of inputs (with ``TASK_INSTRUCTIONS.txt``), a weighted
``RUBRICS.json`` and a ``task_card.md``. The agent only ever sees ``task_folder``;
the rubric goes to the verifier and the task card is left out, as upstream does.

The instruction text, Docker images and judge under ``task-template/`` are copied
from https://github.com/Job-Bench/job-bench-eval at ``UPSTREAM_EVAL_COMMIT`` and
are not modified here, so scores stay comparable with the original benchmark.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import snapshot_download

HF_REPO_ID = "JobBench/job-bench"
HF_REVISION = "d43a66575635da0d3f6cb9a20976dc1a60f3ffc9"
UPSTREAM_EVAL_COMMIT = "660b33a86ed032559df0b2fdc1ad38cf7ceb83f3"

# Harbor split name -> directory in the Hugging Face dataset.
SPLIT_DIRS = {"main": "dataset", "easy": "dataset_easy"}

TEMPLATE_DIR = Path(__file__).parent / "task-template"
ORACLE_DIR = Path(__file__).parent / "oracle-deliverables"

_OCCUPATION_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
_TASK_RE = re.compile(r"task([1-9][0-9]*)")


@dataclass(frozen=True)
class JobBenchTask:
    task_id: str
    split: str
    occupation: str
    task_number: int
    source_dir: Path


def _allow_patterns(splits: list[str]) -> list[str]:
    patterns = []
    for split in splits:
        root = SPLIT_DIRS[split]
        patterns += [
            f"{root}/*/task*/task_folder/**",
            f"{root}/*/task*/RUBRICS.json",
        ]
    return patterns


def _validate_rubric(path: Path) -> None:
    """Fail at generation time on a rubric the judge could not score."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rubrics = payload.get("rubrics") if isinstance(payload, dict) else None
    if not isinstance(rubrics, list) or not rubrics:
        raise ValueError(f"{path}: expected a non-empty 'rubrics' list")
    total = 0.0
    for index, entry in enumerate(rubrics):
        criteria = entry.get("criterion") if isinstance(entry, dict) else None
        weight = entry.get("weight") if isinstance(entry, dict) else None
        if not isinstance(criteria, list) or not criteria:
            raise ValueError(f"{path}: rubric {index} has no criteria")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
            raise ValueError(f"{path}: rubric {index} has an invalid weight")
        total += weight
    if total <= 0:
        raise ValueError(f"{path}: total rubric weight must be positive")


class JobBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "all",
        revision: str = HF_REVISION,
        source_dir: Path | None = None,
        **kwargs,
    ):
        """
        Args:
            output_dir: Directory the task directories are written to.
            limit: Generate only the first N selected tasks.
            overwrite: Replace task directories that already exist.
            task_ids: Generate only these task IDs (e.g. main--lawyers--task1).
            split: "main" (65 leaderboard tasks), "easy" (63 tasks) or "all".
            revision: Hugging Face dataset revision to generate from.
            source_dir: Use this local copy of the dataset instead of downloading.
        """
        if split != "all" and split not in SPLIT_DIRS:
            raise ValueError(f"Unknown split {split!r}; choose main, easy or all")
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.splits = list(SPLIT_DIRS) if split == "all" else [split]
        self.revision = revision
        self.source_dir = Path(source_dir) if source_dir else None

    def _fetch(self) -> Path:
        if self.source_dir is not None:
            return self.source_dir
        return Path(
            snapshot_download(
                HF_REPO_ID,
                repo_type="dataset",
                revision=self.revision,
                allow_patterns=_allow_patterns(self.splits),
            )
        )

    def _discover(self, snapshot: Path) -> list[JobBenchTask]:
        tasks = []
        for split in self.splits:
            split_root = snapshot / SPLIT_DIRS[split]
            if not split_root.is_dir():
                raise FileNotFoundError(f"Dataset has no {SPLIT_DIRS[split]}/ directory")
            for occupation_dir in sorted(p for p in split_root.iterdir() if p.is_dir()):
                if not _OCCUPATION_RE.fullmatch(occupation_dir.name):
                    raise ValueError(f"Unexpected occupation directory: {occupation_dir}")
                for task_dir in occupation_dir.iterdir():
                    match = _TASK_RE.fullmatch(task_dir.name)
                    if not task_dir.is_dir() or match is None:
                        raise ValueError(f"Unexpected task directory: {task_dir}")
                    number = int(match.group(1))
                    tasks.append(
                        JobBenchTask(
                            task_id=f"{split}--{occupation_dir.name}--task{number}",
                            split=split,
                            occupation=occupation_dir.name,
                            task_number=number,
                            source_dir=task_dir,
                        )
                    )
        return sorted(tasks, key=lambda t: (t.split, t.occupation, t.task_number))

    def _select(self, tasks: list[JobBenchTask]) -> list[JobBenchTask]:
        if self.task_ids:
            known = {task.task_id for task in tasks}
            unknown = sorted(set(self.task_ids) - known)
            if unknown:
                raise ValueError(f"Unknown task IDs: {', '.join(unknown)}")
            wanted = set(self.task_ids)
            tasks = [task for task in tasks if task.task_id in wanted]
        if self.limit is not None:
            tasks = tasks[: self.limit]
        return tasks

    def _render(self, task: JobBenchTask, destination: Path) -> None:
        task_folder = task.source_dir / "task_folder"
        rubric = task.source_dir / "RUBRICS.json"
        if not (task_folder / "TASK_INSTRUCTIONS.txt").is_file():
            raise FileNotFoundError(f"{task.task_id}: missing TASK_INSTRUCTIONS.txt")
        if not rubric.is_file():
            raise FileNotFoundError(f"{task.task_id}: missing RUBRICS.json")
        _validate_rubric(rubric)

        shutil.copytree(TEMPLATE_DIR, destination)
        # The Hugging Face cache stores files as symlinks; copy their contents.
        shutil.copytree(
            task_folder,
            destination / "environment" / "task_folder",
            copy_function=shutil.copyfile,
        )
        shutil.copyfile(rubric, destination / "tests" / "RUBRICS.json")

        deliverables = ORACLE_DIR / task.task_id
        if deliverables.is_dir():
            shutil.copytree(deliverables, destination / "solution" / "deliverables")

        (destination / "tests" / "test.sh").chmod(0o755)
        (destination / "solution" / "solve.sh").chmod(0o755)

        config = (destination / "task.toml").read_text(encoding="utf-8")
        for key, value in {
            "task_id": task.task_id,
            "split": task.split,
            "occupation": task.occupation,
            "task_number": f"task{task.task_number}",
            "repo_id": HF_REPO_ID,
            "revision": self.revision,
        }.items():
            config = config.replace("{" + key + "}", value)
        (destination / "task.toml").write_text(config, encoding="utf-8")

    def run(self) -> None:
        tasks = self._select(self._discover(self._fetch()))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = skipped = 0
        for task in tasks:
            destination = self.output_dir / task.task_id
            if destination.exists():
                if not self.overwrite:
                    skipped += 1
                    continue
                shutil.rmtree(destination)
            try:
                self._render(task, destination)
            except Exception:
                shutil.rmtree(destination, ignore_errors=True)
                raise
            written += 1
        print(f"Generated {written} JobBench tasks in {self.output_dir}")
        if skipped:
            print(f"Skipped {skipped} existing tasks (pass --overwrite to replace them)")
