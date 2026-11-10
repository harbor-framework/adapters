"""
ResearchRubrics adapter: converts ScaleAI/researchrubrics into Harbor tasks.

ResearchRubrics pairs 101 open-ended deep-research prompts with 2,593
expert-written, weighted rubric criteria. The agent writes a Markdown report to
/app/report.md; the verifier grades it rubric-by-rubric with an LLM judge and
reports the upstream compliance score.

Paper: https://arxiv.org/abs/2511.07685
Code: https://github.com/scaleapi/researchrubrics
Dataset: https://huggingface.co/datasets/ScaleAI/researchrubrics
"""

import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "task-template"

HF_REPO_ID = "ScaleAI/researchrubrics"
HF_FILENAME = "processed_data.jsonl"
# Pinned dataset revision so generated tasks are reproducible.
HF_REVISION = "85de3115053d1453ed612caacf4a405edc1ad756"


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


def rubric_derived_report(record: dict) -> str:
    """Fallback oracle report built from the task's positive-weight rubrics.

    ResearchRubrics has no reference reports. This document restates every
    positive criterion as a requirement the report addresses, which exercises
    the full judge pipeline end to end. It is a pipeline check, not a real
    research report; pass --oracle-reports-dir to stage genuine reports.
    """
    lines = [
        "# Research Report",
        "",
        "## Request",
        "",
        record["prompt"].strip(),
        "",
    ]
    by_axis: dict[str, list[str]] = {}
    for rubric in record["rubrics"]:
        if rubric["weight"] > 0:
            by_axis.setdefault(rubric["axis"], []).append(rubric["criterion"].strip())
    for axis, criteria in by_axis.items():
        lines += [f"## {axis}", ""]
        lines += [f"- {criterion}" for criterion in criteria]
        lines.append("")
    return "\n".join(lines)


class ResearchRubricsAdapter:
    NAME = "researchrubrics"

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

    def _oracle_report(self, record: dict) -> str:
        if self.oracle_reports_dir is not None:
            path = self.oracle_reports_dir / f"{record['sample_id']}.md"
            if path.exists():
                return path.read_text(encoding="utf-8")
            logger.warning(
                f"No oracle report at {path}; using rubric-derived fallback"
            )
        return rubric_derived_report(record)

    def _prepare_task(self, record: dict, task_dir: Path) -> None:
        task_id = record["sample_id"]
        shutil.copytree(TEMPLATE_DIR, task_dir, dirs_exist_ok=True)

        task_toml = (TEMPLATE_DIR / "task.toml").read_text()
        replacements = {
            "{task_id}": task_id,
            "{keywords}": _toml_str(_slug(record["domain"])),
            '"{domain}"': _toml_str(record["domain"]),
            '"{conceptual_breadth}"': _toml_str(record["conceptual_breadth"]),
            '"{logical_nesting}"': _toml_str(record["logical_nesting"]),
            '"{exploration}"': _toml_str(record["exploration"]),
            "{n_rubrics}": str(len(record["rubrics"])),
        }
        for placeholder, value in replacements.items():
            task_toml = task_toml.replace(placeholder, value)
        (task_dir / "task.toml").write_text(task_toml)

        instruction = (TEMPLATE_DIR / "instruction.md").read_text()
        instruction = instruction.replace("{prompt}", record["prompt"].strip())
        (task_dir / "instruction.md").write_text(instruction)

        (task_dir / "tests" / "rubrics.json").write_text(
            json.dumps(record["rubrics"], indent=2, ensure_ascii=False)
        )
        (task_dir / "solution" / "report.md").write_text(self._oracle_report(record))

    def run(self) -> tuple[int, int]:
        records = load_records(self.data_file)
        records.sort(key=lambda r: r["sample_id"])

        if self.task_ids:
            wanted = set(self.task_ids)
            missing = wanted - {r["sample_id"] for r in records}
            if missing:
                logger.warning(f"Unknown task IDs: {sorted(missing)}")
            records = [r for r in records if r["sample_id"] in wanted]
        if self.limit is not None:
            records = records[: max(0, self.limit)]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        generated = skipped = 0
        for record in records:
            task_dir = self.output_dir / record["sample_id"]
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
