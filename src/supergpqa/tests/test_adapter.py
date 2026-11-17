"""Behavioral checks: fidelity, answer isolation, negative controls and selection."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from supergpqa.adapter import (
    ANSWER_HANDOFF,
    SuperGPQAAdapter,
    original_prompt,
    parity_subset,
    validate_records,
)
from supergpqa.scoring import aggregate, score_response


def record(index=0, answer="B", subfield="Circuits", difficulty="middle"):
    return {
        "uuid": f"{index:032x}",
        "question": "Choose the correct answer.",
        "options": ["incorrect", "correct"],
        "answer": "correct" if answer == "B" else "incorrect",
        "answer_letter": answer,
        "discipline": "Engineering",
        "field": "Electronics",
        "subfield": subfield,
        "difficulty": difficulty,
        "is_calculation": False,
    }


def test_prompt_preserves_options_and_never_inserts_answer():
    row = record()
    assert original_prompt(row).endswith(
        "Choose the correct answer.\nA) incorrect\nB) correct\n"
    )
    assert "Answer: $LETTER" in original_prompt(row)


def test_generated_task_is_harbor_valid_and_gold_stays_outside_build(tmp_path):
    from harbor.models.task.task import Task

    row = record()
    task_path = SuperGPQAAdapter(tmp_path, [row]).run()[0]
    task = Task(task_path)
    assert task.config.task is not None
    assert task.config.task.name == f"m-a-p/supergpqa-{row['uuid']}"
    assert task.config.schema_version == "1.4"
    assert task.config.task.version == "1.0"
    assert task.instruction == original_prompt(row) + ANSWER_HANDOFF + "\n"
    assert list((task_path / "environment").iterdir()) == [
        task_path / "environment/Dockerfile"
    ]
    assert "COPY" not in (task_path / "environment/Dockerfile").read_text()
    assert (
        json.loads((task_path / "tests/record.json").read_text())["answer_letter"]
        == "B"
    )


def test_duplicate_and_mismatched_gold_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        validate_records([record(), record()])
    row = record()
    row["answer"] = "wrong"
    with pytest.raises(ValueError, match="mismatch"):
        validate_records([row])


def test_harbor_newline_normalization_is_explicit(tmp_path):
    from harbor.models.task.task import Task

    row = record()
    row["question"] = "Line one\rLine two\r\nLine three"
    target = SuperGPQAAdapter(tmp_path, [row]).run()[0]
    raw = original_prompt(row) + ANSWER_HANDOFF + "\n"
    assert (target / "instruction.md").read_bytes().decode() == raw
    assert Task(target).instruction == raw.replace("\r\n", "\n").replace("\r", "\n")


def test_selection_deterministic_and_exact_size():
    rows = [
        record(i, subfield=str(i % 4), difficulty=("easy", "middle", "hard")[i % 3])
        for i in range(60)
    ]
    first = parity_subset(rows, 17, 42)
    assert len(first) == 17
    assert len({row["uuid"] for row in first}) == 17
    assert first == parity_subset(list(reversed(rows)), 17, 42)
    assert first != parity_subset(rows, 17, 43)


def test_overwrite_is_explicit_and_does_not_follow_symlinks(tmp_path):
    target = SuperGPQAAdapter(tmp_path, [record()]).run()[0]
    with pytest.raises(FileExistsError):
        SuperGPQAAdapter(tmp_path, [record()]).run()
    SuperGPQAAdapter(tmp_path, [record()], overwrite=True).run()
    other = tmp_path / "other"
    other.mkdir()
    import shutil

    shutil.rmtree(target)
    target.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        SuperGPQAAdapter(tmp_path, [record()], overwrite=True).run()


@pytest.mark.parametrize(
    "response,expected",
    [
        ("Answer: B", 1),
        ("Answer: A", 0),
        ("Answer: b", 0),
        ("Answer: correct", 0),
        ("The answer is correct", 1),
        ("I cannot determine the answer", 0),
        ("", 0),
    ],
)
def test_scoring_preserves_upstream_behavior(response, expected):
    assert score_response(record(), response)["reward"] == expected


def test_macro_aggregation_does_not_collapse_into_micro():
    rows = [record(0, subfield="A"), record(1, subfield="A"), record(2, subfield="B")]
    scores = [{"uuid": row["uuid"], "reward": int(i < 2)} for i, row in enumerate(rows)]
    result = aggregate(rows, scores)
    assert result["sample_accuracy"] == pytest.approx(2 / 3)
    assert result["subfield_accuracy"] == 0.5
    with pytest.raises(ValueError, match="exactly once"):
        aggregate(rows, scores[:-1])


def test_real_solution_and_grader_pass_fail_missing_and_crash(tmp_path):
    task = SuperGPQAAdapter(tmp_path / "tasks", [record()]).run()[0]
    answer = tmp_path / "answer.txt"
    output = tmp_path / "logs"
    subprocess.run(
        ["bash", str(task / "solution/solve.sh")],
        check=True,
        env={**os.environ, "SUPERGPQA_ANSWER_PATH": str(answer)},
    )
    command = [
        sys.executable,
        str(task / "tests/grade.py"),
        "--answer",
        str(answer),
        "--record",
        str(task / "tests/record.json"),
        "--output-dir",
        str(output),
    ]
    passed = subprocess.run(command, capture_output=True, check=False)
    assert passed.returncode == 0, passed.stderr
    assert (output / "reward.txt").read_text().strip() == "1"
    answer.write_text("Answer: A\n")
    assert subprocess.run(command, capture_output=True, check=False).returncode == 1
    assert (output / "reward.txt").read_text().strip() == "0"
    answer.unlink()
    assert subprocess.run(command, capture_output=True, check=False).returncode == 1
    assert (
        json.loads((output / "result.json").read_text())["status"] == "missing_answer"
    )
    (output / "reward.txt").write_text("1\n")
    (task / "tests/record.json").write_text("invalid json")
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0
    assert not (output / "reward.txt").exists()


def test_vendor_matches_pinned_upstream_when_available():
    upstream = Path(__file__).resolve().parents[4] / "SuperGPQA/eval/eval.py"
    if not upstream.exists():
        pytest.skip("Supply the pinned upstream checkout for differential checks")
    spec = importlib.util.spec_from_file_location("original_supergpqa", upstream)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from supergpqa import upstream_parser

    responses = [
        "Answer: B",
        "Answer: b",
        "Reasoning\nAnswer: B.",
        "B",
        "Answer: correct",
        "",
        "Answer: Z",
    ]
    for response in responses:
        assert module.extract_option_labels(
            response
        ) == upstream_parser.extract_option_labels(response)
        assert module.extract_option_content(
            response, record()["options"]
        ) == upstream_parser.extract_option_content(response, record()["options"])
