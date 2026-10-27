import json
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from webgen_bench.adapter import WebGenBenchAdapter, WebGenBenchDataset


@pytest.fixture
def dataset_file(tmp_path: Path) -> Path:
    path = tmp_path / "tasks.jsonl"
    records = [
        {
            "id": f"{i:06d}",
            "instruction": f"Build website {i}.",
            "Category": {"primary_category": "Utilities"},
            "application_type": "utility",
            "ui_instruct": [
                {
                    "task": "Open the home page",
                    "expected_result": "A heading is visible",
                }
            ],
        }
        for i in range(1, 102)
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    return path


def run_cli(
    dataset_file: Path, output: Path, *args: str
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "webgen_bench.main",
            "--jsonl",
            str(dataset_file),
            "--output-dir",
            str(output),
            *args,
        ],
        cwd=dataset_file.parent,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "selection",
    [
        ["000002", "000001"],
        ["--task-ids", "000002", "000001"],
        ["--task-ids", "000002", "--task-ids", "000001"],
    ],
)
def test_selection_preserves_order_before_limit(dataset_file, tmp_path, selection):
    output = tmp_path / "output"
    result = run_cli(dataset_file, output, *selection, "--limit", "1")
    assert result.returncode == 0, result.stderr
    assert [p.name for p in output.iterdir()] == ["webgen-bench-000002"]


def test_combined_id_sources_deduplicate_before_limit(dataset_file, tmp_path):
    ids = tmp_path / "ids.txt"
    ids.write_text("# Selected tasks\n000002\n000003\n000004\n")
    output = tmp_path / "output"
    result = run_cli(
        dataset_file,
        output,
        "000001",
        "--task-ids",
        "000002",
        "000001",
        "--task-id-file",
        str(ids),
        "--limit",
        "3",
    )
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in output.iterdir()) == [
        "webgen-bench-000001",
        "webgen-bench-000002",
        "webgen-bench-000003",
    ]


def test_generation_failure_exits_nonzero(dataset_file, tmp_path):
    result = run_cli(dataset_file, tmp_path / "output", "--task-ids", "missing")
    assert result.returncode != 0
    assert "Failed to convert WebGen-Bench tasks" in result.stderr
    assert "Completed:" not in result.stderr


def test_skip_and_overwrite_preserve_cli_behavior(dataset_file, tmp_path):
    output = tmp_path / "output"
    result = run_cli(dataset_file, output, "--task-ids", "000001")
    assert result.returncode == 0, result.stderr
    instruction = output / "webgen-bench-000001" / "instruction.md"
    instruction.write_text("local edit")
    result = run_cli(dataset_file, output, "000001")
    assert result.returncode == 0, result.stderr
    assert instruction.read_text() == "local edit"
    result = run_cli(dataset_file, output, "000001", "--overwrite")
    assert result.returncode == 0, result.stderr
    assert "Build website 1." in instruction.read_text()


def test_all_oracles_are_materialized_with_task_metadata(dataset_file, tmp_path):
    adapter = WebGenBenchAdapter(
        output_dir=tmp_path / "output",
        dataset=WebGenBenchDataset(jsonl_path=dataset_file),
    )
    tasks = adapter.run()
    assert len(tasks) == 101
    names = set()
    for task in tasks:
        config = tomllib.loads((task / "task.toml").read_text())
        names.add(config["task"]["name"])
        authors = config["task"]["authors"]
        assert len(authors) == 10
        assert all(author.get("email") != "unknown" for author in authors)
        assert (task / "solution" / "app" / "package.json").is_file()
        assert (task / "tests" / "webvoyager" / "run.py").is_file()
        assert (task / "solution" / "solve.sh").stat().st_mode & 0o111
        assert (task / "tests" / "test.sh").stat().st_mode & 0o111
        assert not (task / "environment" / "app").exists()
        assert (task / "tests" / "ui_instruct.json").read_bytes() == (
            task / "environment" / "ui_instruct.json"
        ).read_bytes()
    assert names == {f"webgen-bench/{i:06d}" for i in range(1, 102)}


@pytest.mark.parametrize(
    ("task_id", "database", "required_tables"),
    [
        ("000008", "server/db.sqlite", {"contests", "questions", "submissions"}),
        ("000058", "server/data.db", {"users", "coaches", "assessments"}),
        ("000073", "server/data/db.sqlite", {"users", "links"}),
        ("000091", "server/data.sqlite", {"users", "profiles", "messages"}),
    ],
)
def test_recovered_oracle_databases_are_self_contained(
    dataset_file, tmp_path, task_id, database, required_tables
):
    adapter = WebGenBenchAdapter(
        output_dir=tmp_path / "output",
        dataset=WebGenBenchDataset(jsonl_path=dataset_file),
        task_ids=[task_id],
    )
    task = adapter.run()[0]
    app = task / "solution" / "app"
    assert not list(app.rglob("*-wal"))
    assert not list(app.rglob("*-shm"))
    with sqlite3.connect(f"file:{app / database}?mode=ro", uri=True) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert required_tables <= tables
        if task_id == "000008":
            assert conn.execute("SELECT count(*) FROM questions").fetchone()[0] > 0
