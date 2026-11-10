"""Offline migration checks using invented rows, without executing a grader or oracle."""

import ast
import base64
import csv
import hashlib
import io
import re
import socket
import sys
import tomllib
import urllib.request
from pathlib import Path

import pytest

import browsecomp.main as cli
from browsecomp.adapter import TEMPLATE_DIR, BrowseCompAdapter


def _encrypt_fixture(value: str, password: str) -> str:
    """Encode synthetic inputs using the upstream CSV's SHA-256/XOR specification."""
    key = hashlib.sha256(password.encode("utf-8")).digest()
    ciphertext = bytes(
        byte ^ key[index % len(key)] for index, byte in enumerate(value.encode("utf-8"))
    )
    return base64.b64encode(ciphertext).decode("ascii")


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Offline migration checks must not access the network")

    monkeypatch.setattr(urllib.request, "urlretrieve", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def synthetic_csv(tmp_path: Path) -> tuple[Path, list[tuple[str, str]]]:
    rows = [
        (
            (
                'Invented question: "quotes", backslash \\, newline\nnext line; '
                'tab\tand Unicode 中文 🧪; {braces}; """; "); raise RuntimeError("x")'
            ),
            'Synthetic answer: "雪" \\ $HOME `command`\nsecond line',
        ),
        ("Invented second question?", "Synthetic second answer"),
        ("Invented third question?", "Synthetic third answer"),
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["problem", "answer", "canary"])
    writer.writeheader()
    for index, (question, answer) in enumerate(rows):
        password = f"synthetic-offline-password-{index}"
        writer.writerow(
            {
                "problem": _encrypt_fixture(question, password),
                "answer": _encrypt_fixture(answer, password),
                "canary": password,
            }
        )
    csv_path = tmp_path / "synthetic.csv"
    csv_path.write_text(buffer.getvalue(), encoding="utf-8")
    return csv_path, rows


def _generate(
    csv_path: Path,
    output_dir: Path,
    *,
    limit: int | None = None,
    task_ids: set[int] | None = None,
    overwrite: bool = False,
) -> Path:
    BrowseCompAdapter(
        task_dir=output_dir,
        csv_path=csv_path,
        limit=limit,
        task_ids=task_ids,
        overwrite=overwrite,
    ).run()
    return output_dir / "browsecomp_001"


def test_question_and_judge_literals_round_trip_without_execution(
    synthetic_csv: tuple[Path, list[tuple[str, str]]], tmp_path: Path
) -> None:
    csv_path, rows = synthetic_csv
    question, answer = rows[0]
    task_dir = _generate(csv_path, tmp_path / "tasks", limit=1)

    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8")
    assert instruction.startswith(question + "\n\n")
    assert answer not in instruction

    # Inspect Python literals without importing the generated verifier or calling its judge.
    tree = ast.parse((task_dir / "tests/test_outputs.py").read_text(encoding="utf-8"))
    literals = {
        target.id: ast.literal_eval(statement.value)
        for statement in tree.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
        and target.id in {"QUESTION", "EXPECTED_ANSWER_B64"}
    }
    assert literals["QUESTION"] == question
    assert base64.b64decode(literals["EXPECTED_ANSWER_B64"]).decode("utf-8") == answer


def test_subset_and_limit_preserve_source_task_identity(
    synthetic_csv: tuple[Path, list[tuple[str, str]]], tmp_path: Path
) -> None:
    csv_path, _ = synthetic_csv
    full_dir = tmp_path / "full"
    _generate(csv_path, full_dir)
    assert sorted(path.name for path in full_dir.iterdir()) == [
        "browsecomp_001",
        "browsecomp_002",
        "browsecomp_003",
    ]

    subset_dir = tmp_path / "subset"
    _generate(csv_path, subset_dir, task_ids={1, 3})
    assert sorted(path.name for path in subset_dir.iterdir()) == [
        "browsecomp_001",
        "browsecomp_003",
    ]
    for name in ("browsecomp_001", "browsecomp_003"):
        original = tomllib.loads((full_dir / name / "task.toml").read_text())
        selected = tomllib.loads((subset_dir / name / "task.toml").read_text())
        assert selected["task"]["name"] == original["task"]["name"]
        assert selected["task"]["name"] == f"browsecomp/{name}"

    limited_dir = tmp_path / "limited"
    _generate(csv_path, limited_dir, task_ids={1, 3}, limit=1)
    assert [path.name for path in limited_dir.iterdir()] == ["browsecomp_001"]


def test_overwrite_is_explicit_and_replaces_stale_task_files(
    synthetic_csv: tuple[Path, list[tuple[str, str]]], tmp_path: Path
) -> None:
    csv_path, _ = synthetic_csv
    output_dir = tmp_path / "tasks"
    task_dir = _generate(csv_path, output_dir, limit=1)
    instruction_path = task_dir / "instruction.md"
    original = instruction_path.read_bytes()
    instruction_path.write_text("local edit", encoding="utf-8")
    stale_path = task_dir / "stale.txt"
    stale_path.write_text("old generated material", encoding="utf-8")

    _generate(csv_path, output_dir, limit=1)
    assert instruction_path.read_text() == "local edit"
    assert stale_path.exists()

    _generate(csv_path, output_dir, limit=1, overwrite=True)
    assert instruction_path.read_bytes() == original
    assert not stale_path.exists()


def test_required_templates_generate_complete_named_tasks(
    synthetic_csv: tuple[Path, list[tuple[str, str]]], tmp_path: Path
) -> None:
    csv_path, _ = synthetic_csv
    adapter = BrowseCompAdapter(task_dir=tmp_path / "tasks", csv_path=csv_path, limit=1)
    adapter.run()
    required_files = (
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "solution/solve.sh",
        "tests/test.sh",
    )
    for relative_path in required_files:
        assert (TEMPLATE_DIR / relative_path).is_file(), relative_path
        assert (adapter.output_dir / "browsecomp_001" / relative_path).is_file(), (
            relative_path
        )

    config = tomllib.loads(
        (adapter.output_dir / "browsecomp_001/task.toml").read_text()
    )
    assert config.get("schema_version", config.get("version")) == "1.0"
    assert config["task"]["name"] == "browsecomp/browsecomp_001"
    assert all(author["name"] for author in config["task"]["authors"])


def test_oracle_encodes_exact_answer_without_executing_shell(
    synthetic_csv: tuple[Path, list[tuple[str, str]]], tmp_path: Path
) -> None:
    csv_path, rows = synthetic_csv
    task_dir = _generate(csv_path, tmp_path / "tasks", limit=1)
    script = (task_dir / "solution/solve.sh").read_text(encoding="utf-8")
    match = re.search(
        r"cat << 'EOF' \| base64 -d > /app/answer\.txt\n(.*?)\nEOF(?:\n|$)",
        script,
        flags=re.DOTALL,
    )
    assert match is not None
    assert base64.b64decode(match.group(1), validate=True).decode("utf-8") == rows[0][1]
    assert rows[0][1] not in script


def test_cli_parses_required_flags_and_both_task_id_forms(tmp_path: Path) -> None:
    args = cli.build_parser().parse_args(
        [
            "--output-dir",
            str(tmp_path / "tasks"),
            "--csv-path",
            str(tmp_path / "synthetic.csv"),
            "--task-ids",
            "browsecomp_003,1",
            "2",
            "--split",
            "parity",
            "--limit",
            "2",
            "--overwrite",
        ]
    )
    assert args.output_dir == tmp_path / "tasks"
    assert args.csv_path == tmp_path / "synthetic.csv"
    assert args.limit == 2
    assert args.split == "parity"
    assert args.overwrite is True
    assert cli.parse_task_ids(args.task_ids) == {1, 2, 3}


def test_help_exits_before_download(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden_download(*args: object, **kwargs: object) -> None:
        pytest.fail("--help must not fetch the dataset")

    monkeypatch.setattr(cli, "download_csv", forbidden_download)
    monkeypatch.setattr(sys, "argv", ["browsecomp", "--help"])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 0
    help_text = capsys.readouterr().out
    for flag in ("--output-dir", "--limit", "--overwrite", "--task-ids"):
        assert flag in help_text


def test_parity_cli_uses_local_rows_and_rejects_disjoint_ids(
    synthetic_csv: tuple[Path, list[tuple[str, str]]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path, _ = synthetic_csv
    output_dir = tmp_path / "parity"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "browsecomp",
            "--csv-path",
            str(csv_path),
            "--output-dir",
            str(output_dir),
            "--split",
            "parity",
            "--task-ids",
            "browsecomp_003",
        ],
    )
    assert cli.main() == 0
    assert [path.name for path in output_dir.iterdir()] == ["browsecomp_003"]

    disjoint_dir = tmp_path / "disjoint"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "browsecomp",
            "--csv-path",
            str(csv_path),
            "--output-dir",
            str(disjoint_dir),
            "--split",
            "parity",
            "--task-ids",
            "31",
        ],
    )
    assert cli.main() == 1
    assert not disjoint_dir.exists() or not list(disjoint_dir.iterdir())
