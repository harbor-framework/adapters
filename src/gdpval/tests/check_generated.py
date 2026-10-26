"""Validate generated GDPval packages without Docker or model calls.

From this adapter directory:
  uv run --with harbor==0.23.0 python tests/check_generated.py ../../datasets/gdpval
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from harbor.models.task.config import TaskConfig
from harbor.models.task.task import Task

from gdpval.adapter import GdpvalAdapter
from gdpval.dataset_loader import load_gdpval_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    rows = {str(row["task_id"]): row for row in load_gdpval_dataset()}
    names = set()
    generated = []
    references = 0
    gold_files = 0
    build_time_references = 0
    for directory in sorted(args.dataset.iterdir()):
        if not directory.is_dir():
            continue
        raw = (directory / "task.toml").read_text()
        config = TaskConfig.model_validate_toml(raw)
        task = Task(directory)
        assert task.config.task.name == config.task.name
        assert config.task.name not in names
        names.add(config.task.name)
        assert tomllib.loads(raw)["version"] == "1.0"
        row = rows[directory.name]
        prompt = row["prompt"].strip()
        assert (directory / "tests/task_prompt.txt").read_text() == prompt
        assert prompt in (directory / "instruction.md").read_text()
        rubric = GdpvalAdapter._stringify_rubric(
            row.get("rubric_pretty") or row.get("rubric_json")
        )
        assert (directory / "tests/rubric.txt").read_text() == rubric
        for name in config.metadata["gdpval_deliverable_filenames"]:
            gold = (directory / "tests/gold" / name).read_bytes()
            assert gold == (directory / "solution/gold" / name).read_bytes()
            assert f"/app/{name}" in (directory / "instruction.md").read_text()
            gold_files += 1
        for name in config.metadata["gdpval_reference_files"]:
            path = directory / "environment/reference_files" / name
            # One upstream oversized reference is fetched at Docker build time.
            if not path.is_file():
                dockerfile = (directory / "environment/Dockerfile").read_text()
                assert str(Path("/workspace/reference_files") / name) in dockerfile
                build_time_references += 1
            references += 1
        for relative in (
            "instruction.md",
            "task.toml",
            "solution/solve.sh",
            "tests/test.sh",
        ):
            assert not re.search(r"\{\{[A-Z_]+\}\}", (directory / relative).read_text())
        for script in directory.rglob("*.sh"):
            subprocess.run(["bash", "-n", str(script)], check=True)
        generated.append(directory.name)
    assert generated, "No tasks generated"
    report = {
        "harbor_version": importlib.metadata.version("harbor"),
        "source_rows": len(rows),
        "generated_tasks": len(generated),
        "reference_files": references,
        "gold_files": gold_files,
        "build_time_reference_files": build_time_references,
        "generated_task_ids": generated,
        "not_generated_task_ids": sorted(set(rows) - set(generated)),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if not k.endswith("_ids")}, indent=2
        )
    )


if __name__ == "__main__":
    main()
