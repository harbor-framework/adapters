"""
DRACO adapter: converts perplexity-ai/draco into Harbor tasks.

DRACO pairs 100 deep-research queries with expert-written rubrics (3,934
weighted criteria across four axes). The agent writes a Markdown report to
/app/report.md; the verifier grades it criterion-by-criterion with an LLM judge
using the official grader library and reports the normalized rubric score.

Paper: https://arxiv.org/abs/2602.11685
Dataset: https://huggingface.co/datasets/perplexity-ai/draco
Grader: https://github.com/paper-instruments/rubric
"""

import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "task-template"

HF_REPO_ID = "perplexity-ai/draco"
HF_FILENAME = "test.jsonl"
# Pinned dataset revision so generated tasks are reproducible.
HF_REVISION = "ce076749809027649ebd331bcb70f42bf720d387"


def load_records(data_file: Path | None = None) -> list[dict]:
    """Load benchmark records from a local JSONL file or the pinned HF revision."""
    if data_file is None:
        from huggingface_hub import hf_hub_download

        data_file = Path(
            hf_hub_download(
                HF_REPO_ID, HF_FILENAME, repo_type="dataset", revision=HF_REVISION
            )
        )
    with open(data_file, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _toml_str(value: str) -> str:
    # JSON string escaping is a valid TOML basic string.
    return json.dumps(value, ensure_ascii=False)


def _slug(value: str) -> str:
    return "-".join(
        "".join(c if c.isalnum() else " " for c in value.lower()).split()
    )


def _criteria(rubric: dict) -> list[dict]:
    return [c for section in rubric["sections"] for c in section["criteria"]]


def rubric_derived_report(record: dict, rubric: dict) -> str:
    """Fallback oracle report built from the task's positive-weight criteria.

    DRACO has no reference reports. This document restates every positive
    criterion under its rubric axis, which exercises the full judge pipeline end
    to end. It is a pipeline check, not a real research report; pass
    --oracle-reports-dir to stage genuine reports.
    """
    lines = [
        "# Research Report",
        "",
        "## Request",
        "",
        record["problem"].strip(),
        "",
    ]
    for section in rubric["sections"]:
        criteria = [c["requirement"].strip() for c in section["criteria"] if c["weight"] > 0]
        if criteria:
            lines += [f"## {section['title']}", ""]
            lines += [f"- {criterion}" for criterion in criteria]
            lines.append("")
    return "\n".join(lines)


class DracoAdapter:
    NAME = "draco"

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        data_file: Path | None = None,
        oracle_reports_dir: Path | None = None,
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.data_file = data_file
        self.oracle_reports_dir = oracle_reports_dir

    def _oracle_report(self, record: dict, rubric: dict) -> str:
        if self.oracle_reports_dir is not None:
            path = self.oracle_reports_dir / f"{record['id']}.md"
            if path.exists():
                return path.read_text(encoding="utf-8")
            logger.warning(
                f"No oracle report at {path}; using rubric-derived fallback"
            )
        return rubric_derived_report(record, rubric)

    def _prepare_task(self, record: dict, task_dir: Path) -> None:
        task_id = record["id"]
        rubric = json.loads(record["answer"])
        criteria = _criteria(rubric)
        shutil.copytree(TEMPLATE_DIR, task_dir, dirs_exist_ok=True)

        task_toml = (TEMPLATE_DIR / "task.toml").read_text()
        replacements = {
            "{task_id}": task_id,
            "{keywords}": _toml_str(_slug(record["domain"])),
            '"{domain}"': _toml_str(record["domain"]),
            '"{rubric_id}"': _toml_str(rubric["id"]),
            "{n_criteria}": str(len(criteria)),
            "{n_negative_criteria}": str(sum(c["weight"] < 0 for c in criteria)),
        }
        for placeholder, value in replacements.items():
            task_toml = task_toml.replace(placeholder, value)
        (task_dir / "task.toml").write_text(task_toml)

        instruction = (TEMPLATE_DIR / "instruction.md").read_text()
        instruction = instruction.replace("{problem}", record["problem"].strip())
        (task_dir / "instruction.md").write_text(instruction)

        # The judge sees the query alongside each criterion, as in the paper.
        (task_dir / "tests" / "task.json").write_text(
            json.dumps(
                {
                    "id": task_id,
                    "domain": record["domain"],
                    "problem": record["problem"],
                    "rubric": rubric,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        (task_dir / "solution" / "report.md").write_text(
            self._oracle_report(record, rubric)
        )

    def run(self) -> tuple[int, int]:
        records = load_records(self.data_file)
        records.sort(key=lambda r: r["id"])

        if self.task_ids:
            wanted = set(self.task_ids)
            missing = wanted - {r["id"] for r in records}
            if missing:
                logger.warning(f"Unknown task IDs: {sorted(missing)}")
            records = [r for r in records if r["id"] in wanted]
        if self.limit is not None:
            records = records[: max(0, self.limit)]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        generated = skipped = 0
        for record in records:
            task_dir = self.output_dir / record["id"]
            if task_dir.exists():
                if not self.overwrite:
                    skipped += 1
                    continue
                shutil.rmtree(task_dir)
            self._prepare_task(record, task_dir)
            generated += 1

        logger.info(
            f"Generated {generated} tasks in {self.output_dir}"
            + (f" (skipped {skipped} existing)" if skipped else "")
        )
        return generated, skipped
