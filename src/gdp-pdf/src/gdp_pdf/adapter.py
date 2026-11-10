"""Generate Harbor tasks from GDP.pdf (100 expert prompts over professional PDFs)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "task-template"

# Surge AI's own repo (surgeai/GDP.pdf) is no longer reachable. This is a
# Hugging Face "Duplicate" of it taken on 2026-09-08, which is the newest
# Surge version we found (it fixes the prompt of task efb22c1d).
HF_REPO = "cloudybean/GDP.pdf"
HF_REVISION = "1b73b865da6be76dca2e4f3ad66a53d6709ac9f5"
PARQUET_SHA256 = "c630e8ff254952eb54b89e180311aba5f4e599ce050d056994c75f94a3ff1644"

# Matches the rubric text columns, e.g. "rubric - 12. criterion".
_RUBRIC_RE = re.compile(r"rubric\s*-\s*(\d+)\.\s*criterion", re.IGNORECASE)


@dataclass
class GdpPdfTask:
    task_id: str
    domain: str
    prompt: str
    pdf_path: str
    rubrics: list[dict[str, str]]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rubrics_from_row(row: dict) -> list[dict[str, str]]:
    """Collect the non-empty `rubric - N. criterion` columns, ordered by N."""
    found = []
    for column, value in row.items():
        match = _RUBRIC_RE.fullmatch(str(column).strip())
        if match and value not in (None, ""):
            found.append((int(match.group(1)), str(value)))
    found.sort()
    return [{"id": f"r{n}", "criterion": text} for n, text in found]


class GdpPdfAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        oracle_dir: Path | None = None,
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = set(task_ids) if task_ids else None
        self.oracle_dir = Path(oracle_dir) if oracle_dir else None

    def _download(self, filename: str) -> Path:
        try:
            return Path(
                hf_hub_download(
                    repo_id=HF_REPO,
                    filename=filename,
                    repo_type="dataset",
                    revision=HF_REVISION,
                )
            )
        except Exception as e:
            raise RuntimeError(f"Could not download {filename} from {HF_REPO}") from e

    def load_tasks(self) -> list[GdpPdfTask]:
        parquet = self._download("data.parquet")
        if _sha256(parquet) != PARQUET_SHA256:
            raise RuntimeError(f"{parquet} does not match the pinned sha256")
        tasks = [
            GdpPdfTask(
                task_id=row["task_id"],
                domain=row["domain"],
                prompt=row["prompt"],
                pdf_path=row["pdf_path"],
                rubrics=_rubrics_from_row(row),
            )
            for row in pq.read_table(parquet).to_pylist()
        ]
        if len(tasks) != 100 or len({t.task_id for t in tasks}) != 100:
            raise RuntimeError(f"Expected 100 unique tasks, found {len(tasks)}")
        return tasks

    @staticmethod
    def harbor_names(tasks: list[GdpPdfTask]) -> dict[str, str]:
        """Map upstream task_id to a stable name like `hr-03`.

        Numbering follows the sorted upstream ids inside each domain, so names
        stay the same across runs without exposing the upstream ids.
        """
        names = {}
        by_domain: dict[str, list[str]] = {}
        for task in tasks:
            by_domain.setdefault(_slug(task.domain), []).append(task.task_id)
        for domain, ids in by_domain.items():
            for i, task_id in enumerate(sorted(ids), start=1):
                names[task_id] = f"{domain}-{i:02d}"
        return names

    def _oracle_answer(self, task: GdpPdfTask) -> str | None:
        """Read `<oracle_dir>/<task_id>.md`, written by scripts/build_oracle.py."""
        if self.oracle_dir is None:
            return None
        path = self.oracle_dir / f"{task.task_id}.md"
        try:
            return path.read_text()
        except FileNotFoundError:
            return None

    def _render(self, path: Path, **values: str) -> None:
        text = path.read_text()
        for key, value in values.items():
            text = text.replace("{" + key + "}", value)
        path.write_text(text)

    def generate_task(self, task: GdpPdfTask, name: str, answer: str | None) -> None:
        task_dir = self.output_dir / name
        if task_dir.exists():
            if not self.overwrite:
                logger.info("Skipping %s (exists; use --overwrite)", name)
                return
            shutil.rmtree(task_dir)
        shutil.copytree(TEMPLATE_DIR, task_dir)

        pdf = self._download(task.pdf_path)
        shutil.copyfile(pdf, task_dir / "environment" / "document.pdf")

        # Surge's prompt is kept word for word; only the file locations are added.
        self._render(task_dir / "instruction.md", prompt=task.prompt.strip())
        self._render(
            task_dir / "task.toml",
            task_name=name,
            domain=_slug(task.domain),
        )
        (task_dir / "tests" / "rubric.json").write_text(
            json.dumps(task.rubrics, indent=2, ensure_ascii=False) + "\n"
        )

        solve = task_dir / "solution" / "solve.sh"
        if answer is None:
            logger.warning("No oracle answer for %s; solve.sh will fail", name)
            answer = ""
        (task_dir / "solution" / "answer.md").write_text(answer)
        solve.chmod(0o755)
        (task_dir / "tests" / "test.sh").chmod(0o755)

    def run(self) -> None:
        tasks = self.load_tasks()
        names = self.harbor_names(tasks)

        selected = [
            t
            for t in sorted(tasks, key=lambda t: names[t.task_id])
            if self.task_ids is None
            or names[t.task_id] in self.task_ids
            or t.task_id in self.task_ids
        ]
        if self.limit is not None:
            selected = selected[: self.limit]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        for task in selected:
            self.generate_task(task, names[task.task_id], self._oracle_answer(task))
        logger.info("Wrote %d tasks to %s", len(selected), self.output_dir)
