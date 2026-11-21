"""
DeepSearchQA Adapter - converts Google DeepMind's DeepSearchQA into Harbor tasks.

DeepSearchQA is a 900-prompt benchmark for deep research agents. Each prompt is a
multi-step information-seeking task over the open web whose answer is either a
single entity ("Single Answer") or an exhaustive list ("Set Answer"). Responses
are graded by an LLM autorater (Gemini 2.5 Flash in the official setup) that
reports, per gold item, whether it was found plus any excessive answers; from
that, per-prompt precision / recall / F1 are computed and averaged.

Source data: https://huggingface.co/datasets/google/deepsearchqa (DSQA-full.csv)
Leaderboard: https://www.kaggle.com/benchmarks/google/dsqa/leaderboard
Paper:       https://arxiv.org/abs/2601.20975
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import random
import re
import shutil
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "task-template"
DATASET_URL = (
    "https://huggingface.co/datasets/google/deepsearchqa/resolve/main/DSQA-full.csv"
)
EXPECTED_COLUMNS = {"problem", "problem_category", "answer", "answer_type"}
ANSWER_TYPES = {"Single Answer", "Set Answer"}
SOLUTION_HEREDOC = "DSQA_ORACLE_ANSWER_EOF"

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "uncategorized"


@dataclass(frozen=True)
class DeepSearchQATask:
    """One DeepSearchQA prompt. `index` is the 0-based row in DSQA-full.csv."""

    index: int
    problem: str
    problem_category: str
    answer: str
    answer_type: str

    @property
    def source_id(self) -> str:
        return f"{self.index:03d}"

    @property
    def local_task_id(self) -> str:
        return f"deepsearchqa-{self.source_id}"


class DeepSearchQAAdapter:
    """Generates Harbor task directories for DeepSearchQA."""

    NAME = "deepsearchqa"

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "full",
        parity_size: int = 100,
        parity_seed: int = 42,
        source_csv: Path | None = None,
        dataset_url: str = DATASET_URL,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.split = split
        self.parity_size = parity_size
        self.parity_seed = parity_seed
        self.tasks = self.load_tasks(source_csv=source_csv, dataset_url=dataset_url)

    # ------------------------------------------------------------------ data
    @staticmethod
    def _read_csv_text(source_csv: Path | None, dataset_url: str) -> str:
        if source_csv is not None:
            logger.info(f"Reading DeepSearchQA from local file {source_csv}")
            return Path(source_csv).read_text(encoding="utf-8")
        logger.info(f"Downloading DeepSearchQA from {dataset_url}")
        request = urllib.request.Request(dataset_url)
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read().decode("utf-8")

    @classmethod
    def load_tasks(
        cls, source_csv: Path | None = None, dataset_url: str = DATASET_URL
    ) -> list[DeepSearchQATask]:
        text = cls._read_csv_text(source_csv, dataset_url)
        reader = csv.DictReader(io.StringIO(text))
        missing = EXPECTED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"DeepSearchQA CSV is missing columns: {sorted(missing)}")

        tasks: list[DeepSearchQATask] = []
        for index, row in enumerate(reader):
            answer_type = (row["answer_type"] or "").strip()
            if answer_type not in ANSWER_TYPES:
                raise ValueError(
                    f"Row {index}: unexpected answer_type {answer_type!r}"
                )
            tasks.append(
                DeepSearchQATask(
                    index=index,
                    problem=(row["problem"] or "").strip(),
                    problem_category=(row["problem_category"] or "").strip(),
                    answer=(row["answer"] or "").strip(),
                    answer_type=answer_type,
                )
            )
        logger.info(f"Loaded {len(tasks)} DeepSearchQA prompts")
        return tasks

    # ------------------------------------------------------------ selection
    def parity_subset(self) -> list[DeepSearchQATask]:
        """Deterministic subset stratified by (problem_category, answer_type).

        Each stratum receives a share proportional to its size (largest
        remainder rounding), sampled with a fixed seed, then returned in
        original CSV order so task IDs and ordering are stable across runs.
        """
        size = min(self.parity_size, len(self.tasks))
        strata: dict[tuple[str, str], list[DeepSearchQATask]] = defaultdict(list)
        for task in self.tasks:
            strata[(task.problem_category, task.answer_type)].append(task)

        keys = sorted(strata)
        total = len(self.tasks)
        quotas = {k: size * len(strata[k]) / total for k in keys}
        alloc = {k: int(quotas[k]) for k in keys}
        remaining = size - sum(alloc.values())
        for k in sorted(keys, key=lambda k: (-(quotas[k] - alloc[k]), k))[:remaining]:
            alloc[k] += 1

        rng = random.Random(self.parity_seed)
        chosen: list[DeepSearchQATask] = []
        for k in keys:
            chosen.extend(rng.sample(strata[k], alloc[k]))
        return sorted(chosen, key=lambda t: t.index)

    def selected_tasks(self) -> list[DeepSearchQATask]:
        if self.split == "parity":
            tasks = self.parity_subset()
        elif self.split == "full":
            tasks = list(self.tasks)
        else:
            raise ValueError(f"Unknown split {self.split!r} (expected full|parity)")

        if self.task_ids:
            wanted = {t.strip() for t in self.task_ids}
            tasks = [
                t
                for t in tasks
                if t.local_task_id in wanted
                or t.source_id in wanted
                or str(t.index) in wanted
            ]
        if self.limit is not None:
            tasks = tasks[: self.limit]
        return tasks

    # ------------------------------------------------------------ rendering
    @staticmethod
    def _toml_string(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _render_task_toml(self, task: DeepSearchQATask) -> str:
        template = (TEMPLATE_DIR / "task.toml").read_text()
        keywords = [
            "deepsearchqa",
            "deep-research",
            "web-search",
            _slug(task.answer_type),
            _slug(task.problem_category),
        ]
        rendered = template.replace("{task_id}", task.source_id)
        rendered = rendered.replace(
            'keywords = ["deepsearchqa"]',
            "keywords = [" + ", ".join(self._toml_string(k) for k in keywords) + "]",
        )
        rendered = rendered.replace(
            'category = "deep-research"',
            f"category = {self._toml_string('deep-research')}\n"
            f"problem_category = {self._toml_string(task.problem_category)}\n"
            f"answer_type = {self._toml_string(task.answer_type)}",
        )
        return rendered

    @staticmethod
    def _render_solution(task: DeepSearchQATask) -> str:
        if SOLUTION_HEREDOC in task.answer:
            raise ValueError(f"Answer for {task.local_task_id} contains heredoc marker")
        template = (TEMPLATE_DIR / "solution" / "solve.sh").read_text()
        return template.replace("{answer}", task.answer)

    def generate_task(self, task: DeepSearchQATask) -> Path:
        task_dir = self.output_dir / task.local_task_id
        if task_dir.exists():
            if not self.overwrite:
                logger.debug(f"Skipping existing {task_dir}")
                return task_dir
            shutil.rmtree(task_dir)

        (task_dir / "environment").mkdir(parents=True)
        (task_dir / "solution").mkdir()
        (task_dir / "tests").mkdir()

        shutil.copy2(
            TEMPLATE_DIR / "environment" / "Dockerfile",
            task_dir / "environment" / "Dockerfile",
        )

        instruction = (TEMPLATE_DIR / "instruction.md").read_text()
        (task_dir / "instruction.md").write_text(
            instruction.replace("{problem}", task.problem)
        )

        (task_dir / "task.toml").write_text(self._render_task_toml(task))

        solve = task_dir / "solution" / "solve.sh"
        solve.write_text(self._render_solution(task))
        solve.chmod(0o755)

        for name in ("test.sh", "grade.py"):
            shutil.copy2(TEMPLATE_DIR / "tests" / name, task_dir / "tests" / name)
        (task_dir / "tests" / "test.sh").chmod(0o755)

        ground_truth = {
            "task_id": task.local_task_id,
            "source_index": task.index,
            "problem": task.problem,
            "problem_category": task.problem_category,
            "answer": task.answer,
            "answer_type": task.answer_type,
        }
        (task_dir / "tests" / "ground_truth.json").write_text(
            json.dumps(ground_truth, indent=2, ensure_ascii=False) + "\n"
        )
        return task_dir

    def run(self) -> list[Path]:
        tasks = self.selected_tasks()
        logger.info(f"Generating {len(tasks)} tasks (split={self.split}) ...")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for i, task in enumerate(tasks, 1):
            written.append(self.generate_task(task))
            if i == 1 or i % 100 == 0 or i == len(tasks):
                logger.info(f"Progress: {i}/{len(tasks)} - {task.local_task_id}")
        return written
