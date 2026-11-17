"""Unit tests: data pin, task generation, scoring semantics, and the oracle round trip."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from chess_puzzles import adapter as adapter_module
from chess_puzzles.adapter import (
    DATA_SHA256,
    ChessPuzzlesAdapter,
    load_records,
    normalize_task_ids,
    parse_records,
    render_instruction,
    task_id,
)
from chess_puzzles.scoring import is_correct

# Set CHESS_PUZZLES_CSV to a local copy of the pinned upstream puzzles.csv to run the
# data-dependent tests offline.
import os

CSV = os.environ.get("CHESS_PUZZLES_CSV")
needs_csv = pytest.mark.skipif(not CSV, reason="CHESS_PUZZLES_CSV not set")


# ---- scoring: behaviour of Inspect's exact() as used by upstream 2.0.x ----------------
@pytest.mark.parametrize(
    "answer",
    ["d4d3", "D4D3", " d4d3 ", "d4d3\n", "`d4d3`", "d4d3.", "(d4d3)", '"d4d3"', "d4D3"],
)
def test_accepts_formatting_variants_that_inspect_exact_accepts(answer):
    assert is_correct(answer, "d4d3")


@pytest.mark.parametrize(
    "answer",
    ["", " ", "d4d4", "a1a2", "d4-d3", "Rd3", "d3", "MOVE: d4d3", "d4d3 d4d3", "d4d3d4d3"],
)
def test_rejects_everything_else(answer):
    # 2.0.x does not read SAN or separated UCI; that arrived in the unreleased 2.1.0.
    assert not is_correct(answer, "d4d3")


# ---- data ------------------------------------------------------------------------------
def test_parse_rejects_wrong_row_count():
    with pytest.raises(ValueError, match="Expected 100"):
        parse_records(b"input,target\n8/8/8/8/8/8/8/K6k w - - 0 1,a1a2\n")


def test_parse_rejects_bad_columns():
    with pytest.raises(ValueError, match="Unexpected columns"):
        parse_records(b"fen,move\n")


def test_load_rejects_checksum_mismatch(tmp_path):
    bad = tmp_path / "puzzles.csv"
    bad.write_bytes(b"input,target\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_records(bad, tmp_path)


@needs_csv
def test_pinned_data_loads():
    records = load_records(Path(CSV), Path("."))
    assert len(records) == 100
    assert [r["id"] for r in records] == list(range(1, 101))
    assert records[0]["target"] == "d4d3"
    assert len({r["fen"] for r in records}) == 100


# ---- ids -------------------------------------------------------------------------------
def test_task_id_format():
    assert task_id(7) == "chess-puzzles-007"


def test_normalize_task_ids():
    assert normalize_task_ids(["chess-puzzles-007", "7", "007", "100"]) == {7, 100}
    with pytest.raises(ValueError):
        normalize_task_ids(["abc"])


# ---- generation ------------------------------------------------------------------------
def test_instruction_has_fen_and_no_answer():
    text = render_instruction("6k1/3R4/2N3p1/PpPp4/1P1r4/5r2/6K1/8 b - - 3 56")
    assert "6k1/3R4/2N3p1/PpPp4/1P1r4/5r2/6K1/8 b - - 3 56" in text
    assert "/app/answer.txt" in text
    assert "d4d3" not in text.replace("b1c3", "")


@needs_csv
def test_generation_layout_and_oracle(tmp_path):
    out = tmp_path / "chess-puzzles"
    tasks = ChessPuzzlesAdapter(out, data_path=Path(CSV), limit=3).run()
    assert [t.name for t in tasks] == [
        "chess-puzzles-001",
        "chess-puzzles-002",
        "chess-puzzles-003",
    ]
    for task in tasks:
        for rel in (
            "task.toml",
            "instruction.md",
            "environment/Dockerfile",
            "solution/solve.sh",
            "tests/test.sh",
            "tests/grade.py",
            "tests/scoring.py",
            "tests/record.json",
        ):
            assert (task / rel).is_file(), rel
        record = json.loads((task / "tests/record.json").read_text())
        # The gold move must never be in what the agent sees.
        assert record["target"] not in (task / "instruction.md").read_text()
        assert record["target"] not in (task / "environment/Dockerfile").read_text()
        # Oracle round trip with redirected paths.
        answer = task / "answer.txt"
        env = {"CHESS_PUZZLES_ANSWER_PATH": str(answer), "PATH": "/usr/bin:/bin"}
        subprocess.run(["bash", str(task / "solution/solve.sh")], check=True, env=env)
        logs = task / "logs"
        subprocess.run(
            [
                sys.executable,
                str(task / "tests/grade.py"),
                "--answer",
                str(answer),
                "--record",
                str(task / "tests/record.json"),
                "--output-dir",
                str(logs),
            ],
            check=True,
        )
        assert (logs / "reward.txt").read_text().strip() == "1"
    name = json.loads((tasks[0] / "tests/record.json").read_text())["id"]
    assert name == 1


@needs_csv
def test_overwrite_protection_and_task_selection(tmp_path):
    out = tmp_path / "chess-puzzles"
    ChessPuzzlesAdapter(out, data_path=Path(CSV), task_ids=["5", "chess-puzzles-009"]).run()
    assert sorted(p.name for p in out.iterdir() if p.is_dir()) == [
        "chess-puzzles-005",
        "chess-puzzles-009",
    ]
    with pytest.raises(FileExistsError):
        ChessPuzzlesAdapter(out, data_path=Path(CSV), task_ids=["5"]).run()
    ChessPuzzlesAdapter(
        out, data_path=Path(CSV), task_ids=["5", "9"], overwrite=True
    ).run()
    with pytest.raises(ValueError, match="Unknown task ids"):
        ChessPuzzlesAdapter(tmp_path / "x", data_path=Path(CSV), task_ids=["101"]).run()


@needs_csv
def test_smaller_selection_cannot_leave_stale_tasks(tmp_path):
    out = tmp_path / "chess-puzzles"
    ChessPuzzlesAdapter(out, data_path=Path(CSV), limit=3).run()
    with pytest.raises(ValueError, match="outside this selection"):
        ChessPuzzlesAdapter(out, data_path=Path(CSV), limit=1, overwrite=True).run()
    manifest = json.loads((out / "generation_manifest.json").read_text())
    assert len(manifest["task_ids"]) == 3  # untouched, still matches the directory


def test_default_output_dir_is_named_chess_puzzles():
    from chess_puzzles.main import DEFAULT_OUTPUT_DIR

    assert DEFAULT_OUTPUT_DIR.parts[-2:] == ("datasets", "chess-puzzles")


def test_pin_constants_are_consistent():
    assert len(DATA_SHA256) == 64
    assert adapter_module.UPSTREAM_COMMIT in adapter_module.DATA_URL
