"""Generate Harbor tasks for the FrontierScience-Research split.

Source: Hugging Face dataset ``openai/frontierscience``, file ``research/test.jsonl``
(60 rows: problem, rubric in ``answer``, subject, task_group_id), pinned to a fixed
revision and checked against a SHA-256 digest.

Each row becomes one task. Rows 6 and 11 of the file are an identical duplicate; both
are kept (matching ``inspect_evals/frontierscience``), and the second copy gets a
``-2`` suffix so every task name stays unique and stable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

HF_REPO = "openai/frontierscience"
HF_REVISION = "25ed67db7da8f4591484e764008ff585544f5a30"
HF_FILE = "research/test.jsonl"
DATA_URL = f"https://huggingface.co/datasets/{HF_REPO}/resolve/{HF_REVISION}/{HF_FILE}"
DATA_SHA256 = "96c0434abfcbadd6ef6f59a03cc374be4caf9c1f2d5e62d8fe921e768f66aa46"

TEMPLATE_DIR = Path(__file__).parent / "task-template"
# src/frontierscience-research/ (the adapter root that holds README.md, oracle_solutions/)
ADAPTER_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ORACLE_DIR = ADAPTER_ROOT / "oracle_solutions"

# Files copied verbatim from the template into every task.
STATIC_FILES = (
    "environment/Dockerfile",
    "solution/solve.sh",
    "tests/test.sh",
    "tests/grader.py",
)
EXECUTABLES = ("solution/solve.sh", "tests/test.sh")


@dataclass(frozen=True)
class ResearchTask:
    task_id: str  # e.g. "physics-222e24bf"; a repeated row gets "-2", "-3", ...
    oracle_key: (
        str  # "<subject>-<first 8 chars of task_group_id>", shared by duplicates
    )
    row_index: int  # 0-based line number in research/test.jsonl
    subject: str
    task_group_id: str
    problem: str
    rubric: str


def load_records(data_file: Path | None = None) -> list[dict]:
    """Read research/test.jsonl from a local file or the pinned HF revision."""
    if data_file is not None:
        raw = Path(data_file).read_bytes()
    else:
        logger.info("Downloading %s", DATA_URL)
        with urllib.request.urlopen(DATA_URL, timeout=120) as resp:
            raw = resp.read()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != DATA_SHA256:
        raise ValueError(
            f"research/test.jsonl SHA-256 mismatch: expected {DATA_SHA256}, got {digest}"
        )
    return [
        json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()
    ]


def build_tasks(records: list[dict]) -> list[ResearchTask]:
    """Map dataset rows to tasks with stable, unique IDs."""
    prefixes = {r["task_group_id"][:8] for r in records}
    if len(prefixes) != len({r["task_group_id"] for r in records}):
        raise ValueError("task_group_id 8-character prefixes are not unique")

    seen: Counter[str] = Counter()
    tasks: list[ResearchTask] = []
    for index, record in enumerate(records):
        oracle_key = f"{record['subject']}-{record['task_group_id'][:8]}"
        seen[oracle_key] += 1
        count = seen[oracle_key]
        task_id = oracle_key if count == 1 else f"{oracle_key}-{count}"
        tasks.append(
            ResearchTask(
                task_id=task_id,
                oracle_key=oracle_key,
                row_index=index,
                subject=record["subject"],
                task_group_id=record["task_group_id"],
                problem=record["problem"],
                rubric=record["answer"],
            )
        )
    return tasks


class FrontierScienceResearchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        data_file: Path | None = None,
        oracle_dir: Path | None = DEFAULT_ORACLE_DIR,
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.data_file = data_file
        self.oracle_dir = Path(oracle_dir) if oracle_dir else None

    def select_tasks(self) -> list[ResearchTask]:
        tasks = build_tasks(load_records(self.data_file))
        if self.task_ids:
            wanted = set(self.task_ids)
            unknown = wanted - {t.task_id for t in tasks}
            if unknown:
                raise ValueError(f"Unknown task IDs: {sorted(unknown)}")
            tasks = [t for t in tasks if t.task_id in wanted]
        if self.limit is not None:
            tasks = tasks[: self.limit]
        return tasks

    def run(self) -> None:
        tasks = self.select_tasks()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written, skipped, missing_oracle = 0, 0, []
        for task in tasks:
            task_dir = self.output_dir / task.task_id
            if task_dir.exists():
                if not self.overwrite:
                    skipped += 1
                    continue
                shutil.rmtree(task_dir)
            if not self._write_task(task, task_dir):
                missing_oracle.append(task.task_id)
            written += 1
        print(
            f"Wrote {written} tasks to {self.output_dir} ({skipped} existing skipped)."
        )
        if missing_oracle:
            print(
                f"WARNING: no oracle answer for {len(missing_oracle)} task(s); their "
                f"solve.sh will fail: {', '.join(missing_oracle)}"
            )

    def _write_task(self, task: ResearchTask, task_dir: Path) -> bool:
        """Write one task directory. Returns False if no oracle answer was found."""
        for rel in STATIC_FILES:
            dest = task_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(TEMPLATE_DIR / rel, dest)
        for rel in EXECUTABLES:
            (task_dir / rel).chmod(0o755)

        toml = (TEMPLATE_DIR / "task.toml").read_text()
        for key, value in {
            "{task_id}": task.task_id,
            "{subject}": task.subject,
            "{task_group_id}": task.task_group_id,
            "{row_index}": str(task.row_index),
        }.items():
            toml = toml.replace(key, value)
        (task_dir / "task.toml").write_text(toml)

        instruction = (TEMPLATE_DIR / "instruction.md").read_text()
        (task_dir / "instruction.md").write_text(
            instruction.replace("{problem}", task.problem)
        )

        # The rubric only ever lives under tests/, which Harbor uploads at verification
        # time, so the agent cannot read it.
        (task_dir / "tests" / "task.json").write_text(
            json.dumps(
                {
                    "task_id": task.task_id,
                    "subject": task.subject,
                    "task_group_id": task.task_group_id,
                    "problem": task.problem,
                    "rubric": task.rubric,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        oracle_file = (
            self.oracle_dir / f"{task.oracle_key}.md" if self.oracle_dir else None
        )
        if (
            oracle_file is not None
            and oracle_file.is_file()
            and oracle_file.read_text().strip()
        ):
            shutil.copy2(oracle_file, task_dir / "solution" / "answer.md")
            return True
        return False
