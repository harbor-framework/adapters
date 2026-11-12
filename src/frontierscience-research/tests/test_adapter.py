"""Offline tests for the FrontierScience-Research adapter and grader (no network, no API key).

Run from src/frontierscience-research/:
    uv run --with pytest --with anthropic==2.8.0 pytest tests -q
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ADAPTER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ADAPTER_ROOT / "src"))

from frontierscience_research import adapter as fs_adapter

GRADER_PATH = (
    ADAPTER_ROOT
    / "src"
    / "frontierscience_research"
    / "task-template"
    / "tests"
    / "grader.py"
)

SENTINEL_RUBRIC = "Points: 10, Item: SENTINEL-RUBRIC-TEXT must never reach the agent"


def _records() -> list[dict]:
    rows = [
        {
            "problem": "P1 {braces} $x$",
            "answer": SENTINEL_RUBRIC,
            "subject": "physics",
            "task_group_id": "aaaaaaaa-1111-2222-3333-444444444444",
        },
        {
            "problem": "P2",
            "answer": SENTINEL_RUBRIC,
            "subject": "biology",
            "task_group_id": "bbbbbbbb-1111-2222-3333-444444444444",
        },
    ]
    # An exact duplicate row, as in the real research split.
    return rows + [dict(rows[0])]


def _load_grader():
    spec = importlib.util.spec_from_file_location("fs_grader", GRADER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_task_ids_are_unique_and_duplicates_suffixed():
    tasks = fs_adapter.build_tasks(_records())
    assert [t.task_id for t in tasks] == [
        "physics-aaaaaaaa",
        "biology-bbbbbbbb",
        "physics-aaaaaaaa-2",
    ]
    assert tasks[0].oracle_key == tasks[2].oracle_key == "physics-aaaaaaaa"


def test_generated_task_layout_and_rubric_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_adapter, "load_records", lambda data_file=None: _records())
    oracle_dir = tmp_path / "oracle"
    oracle_dir.mkdir()
    (oracle_dir / "physics-aaaaaaaa.md").write_text("oracle answer for physics")

    out = tmp_path / "out"
    fs_adapter.FrontierScienceResearchAdapter(out, oracle_dir=oracle_dir).run()

    assert sorted(p.name for p in out.iterdir()) == [
        "biology-bbbbbbbb",
        "physics-aaaaaaaa",
        "physics-aaaaaaaa-2",
    ]
    task_dir = out / "physics-aaaaaaaa"
    for rel in [
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "solution/solve.sh",
        "solution/answer.md",
        "tests/test.sh",
        "tests/grader.py",
        "tests/task.json",
    ]:
        assert (task_dir / rel).is_file(), rel

    toml = (task_dir / "task.toml").read_text()
    assert 'name = "openai/frontierscience-research__physics-aaaaaaaa"' in toml
    assert "{" + "task_id}" not in toml and "{subject}" not in toml

    instruction = (task_dir / "instruction.md").read_text()
    assert instruction.startswith("P1 {braces} $x$")
    assert "/workspace/answer.md" in instruction

    # The rubric may only appear under tests/.
    for path in task_dir.rglob("*"):
        if path.is_file() and "tests" not in path.relative_to(task_dir).parts:
            assert "SENTINEL-RUBRIC-TEXT" not in path.read_text(errors="ignore"), path
    assert (
        json.loads((task_dir / "tests" / "task.json").read_text())["rubric"]
        == SENTINEL_RUBRIC
    )

    # Duplicate shares the oracle; a task without an oracle gets no answer.md.
    assert (
        out / "physics-aaaaaaaa-2" / "solution" / "answer.md"
    ).read_text() == "oracle answer for physics"
    assert not (out / "biology-bbbbbbbb" / "solution" / "answer.md").exists()


def test_task_ids_filter_and_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_adapter, "load_records", lambda data_file=None: _records())
    a = fs_adapter.FrontierScienceResearchAdapter(
        tmp_path, task_ids=["biology-bbbbbbbb"]
    )
    assert [t.task_id for t in a.select_tasks()] == ["biology-bbbbbbbb"]
    with pytest.raises(ValueError):
        fs_adapter.FrontierScienceResearchAdapter(
            tmp_path, task_ids=["nope"]
        ).select_tasks()


def test_shipped_oracle_answers_are_complete():
    files = sorted((ADAPTER_ROOT / "oracle_solutions").glob("*.md"))
    assert len(files) == 59  # 60 rows, one exact duplicate
    for path in files:
        assert path.read_text().strip(), path.name


@pytest.mark.parametrize(
    "text, expected",
    [
        ("item 1 ok\nVERDICT: 8", 8.0),
        ("VERDICT: 2.5", 2.5),
        ("verdict: 7", 7.0),
        ("VERDICT: 12", 10.0),  # clamped
        ("first VERDICT: 3\nlast VERDICT: 9", 3.0),  # first match, like inspect_evals
        ("no verdict here", None),
        ("VERDICT: .", None),
    ],
)
def test_parse_points(text, expected):
    assert _load_grader().parse_points(text) == expected


def test_reward_threshold_and_empty_answer(tmp_path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps({"task_id": "t", "problem": "p", "rubric": "r"}))
    monkeypatch.setenv("FS_TASK_FILE", str(task_file))
    monkeypatch.setenv("FS_ANSWER_FILE", str(tmp_path / "missing.md"))
    monkeypatch.setenv("FS_VERIFIER_DIR", str(tmp_path / "verifier"))
    grader = _load_grader()

    assert grader.write_rewards(7.0) == {"reward": 1.0, "score": 0.7}
    assert grader.write_rewards(6.75) == {"reward": 0.0, "score": 0.675}

    # Missing answer: scored 0 without any API call.
    assert grader.main() == 0
    rewards = json.loads((tmp_path / "verifier" / "reward.json").read_text())
    assert rewards == {"reward": 0.0, "score": 0.0}
    assert (
        json.loads((tmp_path / "verifier" / "grading.json").read_text())["status"]
        == "no_answer"
    )
