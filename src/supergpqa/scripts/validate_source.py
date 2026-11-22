"""Pre-parity checks on source data, prompts, scoring and generated tasks.

Runs no model calls and no containers. Never labels these checks Harbor oracle
trials. Requires the upstream reporting dependencies for differential checks.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path

import yaml

from supergpqa import upstream_parser
from supergpqa.adapter import (
    ANSWER_HANDOFF,
    DATA_SHA256,
    UPSTREAM_COMMIT,
    SuperGPQAAdapter,
    load_records,
    original_prompt,
)
from supergpqa.scoring import aggregate, score_response


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-repo", type=Path, required=True)
    parser.add_argument("--generated-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    from harbor.models.task.task import Task

    rows = load_records(args.upstream_repo / "data/SuperGPQA-all.jsonl", Path(".cache"))
    original_path = args.upstream_repo / "eval/eval.py"
    spec = importlib.util.spec_from_file_location(
        "supergpqa_original_eval", original_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load upstream evaluator")
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    original_ast = ast.parse(original_path.read_text())
    vendor_ast = ast.parse(Path(upstream_parser.__file__).read_text())
    names = {"safe_regex_search", "extract_option_labels", "extract_option_content"}
    original_functions = {
        n.name: ast.dump(n)
        for n in original_ast.body
        if isinstance(n, ast.FunctionDef) and n.name in names
    }
    vendor_functions = {
        n.name: ast.dump(n)
        for n in vendor_ast.body
        if isinstance(n, ast.FunctionDef) and n.name in names
    }
    require(
        original_functions == vendor_functions,
        "Vendored parser differs from pinned upstream",
    )
    prompt_template = yaml.safe_load(
        (args.upstream_repo / "config/prompt/zero-shot.yaml").read_text()
    )["prompt_format"][0]
    scores = []
    newline_normalized_count = 0
    mixed = []
    controls = []
    for index, row in enumerate(rows):
        if index % 5000 == 0:
            print(f"Validating tasks: {index}/{len(rows)}", flush=True)
        target = args.generated_dir / SuperGPQAAdapter.task_id(row)
        task = Task(target)
        expected_prompt = prompt_template.format(
            row["question"]
            + "\n"
            + "\n".join(
                f"{chr(65 + i)}) {option}" for i, option in enumerate(row["options"])
            )
        )
        require(
            original_prompt(row) == expected_prompt, f"Prompt mismatch: {row['uuid']}"
        )
        stored_instruction = expected_prompt + ANSWER_HANDOFF + "\n"
        require(
            (target / "instruction.md").read_bytes().decode("utf-8")
            == stored_instruction,
            f"Stored prompt bytes mismatch: {row['uuid']}",
        )
        loaded_instruction = stored_instruction.replace("\r\n", "\n").replace(
            "\r", "\n"
        )
        newline_normalized_count += int(loaded_instruction != stored_instruction)
        require(
            task.instruction == loaded_instruction,
            f"Task prompt mismatch: {row['uuid']}",
        )
        require(
            task.config.task is not None
            and task.config.task.name == f"m-a-p/{target.name}",
            "Task identity mismatch",
        )
        require(
            json.loads((target / "tests/record.json").read_text()) == row,
            "Verifier record mismatch",
        )
        require(
            f"'Answer: {row['answer_letter']}'"
            in (target / "solution/solve.sh").read_text(),
            "Oracle script mismatch",
        )
        require(
            len(list((target / "environment").iterdir())) == 1,
            "Unexpected agent-visible build asset",
        )
        score = score_response(row, f"Answer: {row['answer_letter']}")
        require(score["reward"] == 1, f"Gold label failed: {row['uuid']}")
        scores.append(score)
        wrong = chr(65 + (ord(row["answer_letter"]) - 65 + 1) % len(row["options"]))
        require(
            score_response(row, f"Answer: {wrong}")["reward"] == 0,
            "Wrong answer accepted",
        )
        require(score_response(row, "")["reward"] == 0, "Empty answer accepted")
        # A mixed, deterministic response corpus exercises both correct and
        # incorrect grades and aggregation independently of golden controls.
        response = f"Answer: {row['answer_letter'] if index % 3 else wrong}"
        mixed.append({**row, "response": response})
        controls.append(score_response(row, response))
    expected_dirs = {SuperGPQAAdapter.task_id(row) for row in rows}
    actual_dirs = {p.name for p in args.generated_dir.iterdir() if p.is_dir()}
    require(actual_dirs == expected_dirs, "Generated dataset task count/IDs mismatch")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "mixed.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in mixed))
        with contextlib.redirect_stderr(io.StringIO()):
            upstream_result = upstream.calculate_accuracy(
                str(path), str(Path(directory) / "graded"), "zero-shot"
            )
        graded = [
            json.loads(line)
            for line in (Path(directory) / "graded/mixed.jsonl")
            .read_text()
            .splitlines()
        ]
        for original, ours in zip(graded, controls, strict=True):
            require(
                original["extracted_answer"] == ours["extracted_answer"],
                "Differential extraction mismatch",
            )
            require(
                original["status"] == ours["status"], "Differential status mismatch"
            )
        stats = aggregate(rows, controls)
        require(
            abs(upstream_result[0] - stats["sample_accuracy"]) < 1e-12,
            "Micro accuracy mismatch",
        )
        for dimension in ("discipline", "field", "subfield"):
            groups = upstream_result[-1][dimension].values()
            macro = sum(group["correct"] / group["total"] for group in groups) / len(
                groups
            )
            require(
                abs(macro - stats[f"{dimension}_accuracy"]) < 1e-12,
                f"Macro mismatch: {dimension}",
            )
        for offset, difficulty in enumerate(("hard", "middle", "easy"), start=3):
            require(
                abs(upstream_result[offset] - stats["difficulty_accuracy"][difficulty])
                < 1e-12,
                "Difficulty mismatch",
            )
    report = {
        "kind": "local_pre_parity_validation_not_harbor_oracle",
        "upstream_commit": UPSTREAM_COMMIT,
        "data_sha256": DATA_SHA256,
        "tasks_generated_and_harbor_model_validated": len(rows),
        "prompts_equal_to_upstream_plus_documented_handoff": len(rows),
        "harbor_universal_newline_normalization_count": newline_normalized_count,
        "gold_label_checks_passed": sum(score["reward"] for score in scores),
        "wrong_and_empty_answer_controls_passed": 2 * len(rows),
        "upstream_parser_ast_equal": True,
        "mixed_corpus_differential_checks": len(rows),
        "micro_macro_and_difficulty_aggregation_equal": True,
        "harbor_container_oracle_run": "not_run",
        "parity": "not_run_per_user_scope",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
