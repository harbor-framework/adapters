from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from pyarrow import parquet

from contextbench import adapter as adapter_module
from contextbench import main as main_module
from contextbench.adapter import (
    CONTEXTBENCH_COMMIT,
    DATASETS,
    GIT_IMAGE,
    IMAGE_DIGESTS_PATH,
    PARITY_DATASET_NAME,
    PARITY_TASK_IDS,
    REPORT_FILENAME,
    VERIFIER_IMAGE,
    ContextBenchAdapter,
    InvalidDatasetRowsError,
    OracleRead,
    _dataset_label,
    _gold_payload,
    decoded_json_string,
    load_corrections,
    native_environment,
    oracle_trajectory,
    prepare_row,
    task_directory_name,
)
from contextbench.attribution.trajectory import project_atif
from contextbench.vendor.contextbench_source.contextbench.parsers.gold import Gold
from tests.helpers import synthetic_digest

ADAPTER_ROOT = Path(__file__).parents[1]
VENDOR_ROOT = ADAPTER_ROOT / "src/contextbench/vendor"
CORPUS_CONTRACT = ADAPTER_ROOT / "tests/fixtures/published-corpus-contract.json.gz"
# Rows ContextBench publishes malformed in `full`. corrections.json restores the
# missing statement of 788af515 from SWE-bench Pro v1; the other three have no
# gold context in any published source.
UPSTREAM_MALFORMED_FULL_IDS = {
    "SWE-Bench-Pro__python__maintenance__bugfix__788af515",
    "Multi-SWE-Bench__cpp__maintenance__bugfix__0fd29e35",
    "Multi-SWE-Bench__javascript__maintenance__bugfix__3cd96c13",
    "Multi-SWE-Bench__rust__maintenance__bugfix__0e4e102e",
}
RESTORED_FULL_IDS = {"SWE-Bench-Pro__python__maintenance__bugfix__788af515"}
MALFORMED_FULL_IDS = UPSTREAM_MALFORMED_FULL_IDS - RESTORED_FULL_IDS
MULTI_SWE_BENCH_HARNESS = {
    "/home/fix.patch",
    "/home/test.patch",
    "/home/fix-run.sh",
    "/home/test-run.sh",
    "/home/run.sh",
    "/home/prepare.sh",
    "/home/check_git_changes.sh",
}


def _corpus_contract() -> dict[str, Any]:
    with gzip.open(CORPUS_CONTRACT, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    assert isinstance(value, dict)
    return value


def _contract_row(
    contract: dict[str, Any], dataset_name: str, instance_id: str
) -> dict[str, Any]:
    row = dict(contract["datasets"][dataset_name]["instances"][instance_id])
    row["problem_statement"] = (
        "Published problem statement." if row.pop("problem_statement_present") else ""
    )
    row["patch"] = ""
    return row


def _restored(row: dict[str, Any]) -> dict[str, Any]:
    """The contract row with the statement corrections.json restores."""
    if row["instance_id"] in RESTORED_FULL_IDS:
        return {**row, "problem_statement": "Restored problem statement."}
    return row


def _contract_rows(dataset_name: str) -> list[dict[str, Any]]:
    contract = _corpus_contract()
    return [
        _contract_row(contract, dataset_name, instance_id)
        for instance_id in contract["datasets"][dataset_name]["instance_ids"]
    ]


def _row(instance_id: str, index: int, source: str = "Verified") -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "original_inst_id": f"owner__repo-{index}",
        "repo": "owner/repo",
        "base_commit": f"{index:040x}",
        "language": "python",
        "source": source,
        "problem_statement": f"Find relevant code for task {index}.",
        "gold_context": json.dumps(
            [
                {
                    "file": f"src/example_{index}.py",
                    "start_line": 2,
                    "end_line": 4,
                    "content": "two\nthree\nfour\n",
                }
            ]
        ),
        "patch": (
            f"diff --git a/src/example_{index}.py b/src/example_{index}.py\n"
            f"--- a/src/example_{index}.py\n"
            f"+++ b/src/example_{index}.py\n"
            "@@ -1 +1 @@\n-old\n+new\n"
        ),
    }


def _write_dataset(path: Path, rows: list[dict[str, Any]]) -> Path:
    parquet.write_table(pa.Table.from_pylist(rows), path)
    return path


def _dataset_label_of(path: Path) -> str:
    return _dataset_label(hashlib.sha256(path.read_bytes()).hexdigest())


def _task_name(dataset: Path, instance_id: str) -> str:
    return task_directory_name(_dataset_label_of(dataset), instance_id)


def _report(output: Path) -> dict[str, Any]:
    return json.loads((output / REPORT_FILENAME).read_text(encoding="utf-8"))


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    return _write_dataset(
        tmp_path / "contextbench.parquet", [_row("first", 1), _row("second", 2)]
    )


def test_published_corpus_contract_matches_pinned_datasets() -> None:
    contract = _corpus_contract()

    assert contract["schema_version"] == 3
    assert contract["contextbench_commit"] == CONTEXTBENCH_COMMIT
    assert contract["annotation_count"] == 19_842
    assert contract["distinct_instance_count"] == 1_136
    assert set(contract["datasets"]) == set(DATASETS)
    for name, spec in DATASETS.items():
        published = contract["datasets"][name]
        assert published["filename"] == spec.filename
        assert published["sha256"] == spec.sha256
        assert published["rows"] == spec.rows
        assert len(published["instance_ids"]) == spec.rows
        assert len(set(published["instance_ids"])) == spec.rows
        assert set(published["instance_ids"]) == set(published["instances"])


@pytest.mark.parametrize(
    ("dataset_name", "expected_invalid"),
    [
        ("full", UPSTREAM_MALFORMED_FULL_IDS),
        ("verified", set()),
        ("verified-test", set()),
        ("verified-train", set()),
    ],
)
def test_every_published_row_is_validated(
    dataset_name: str, expected_invalid: set[str]
) -> None:
    invalid: set[str] = set()

    for row in _contract_rows(dataset_name):
        try:
            prepare_row(row)
        except (TypeError, ValueError):
            invalid.add(row["instance_id"])

    assert invalid == expected_invalid


@pytest.mark.parametrize(
    ("dataset_name", "truncated_repo_column"), [("verified", 34), ("full", 88)]
)
def test_repository_is_the_repo_url_slug(
    dataset_name: str, truncated_repo_column: int
) -> None:
    """`repo_url` decides the repository, not the truncated `repo` column."""
    truncated = 0
    for row in _contract_rows(dataset_name):
        if row["instance_id"] in MALFORMED_FULL_IDS:
            continue
        prepared = prepare_row(_restored(row))
        expected = row["repo_url"].removeprefix("https://github.com/")
        assert prepared.repository == expected.removesuffix(".git")
        truncated += row["repo"] != prepared.repository

    # For example `fasterxml/jackson` for `fasterxml/jackson-core`.
    assert truncated == truncated_repo_column


def test_every_instance_has_one_environment_across_datasets() -> None:
    """The splits lack `repo_url`, so they rely on `original_inst_id` alone."""
    environments: dict[str, set[tuple[str, str, str]]] = {}
    for dataset_name in DATASETS:
        for row in _contract_rows(dataset_name):
            if row["instance_id"] in MALFORMED_FULL_IDS:
                continue
            prepared = prepare_row(_restored(row))
            environments.setdefault(row["instance_id"], set()).add(
                (
                    prepared.repository,
                    prepared.native.image,
                    prepared.native.repository_path,
                )
            )

    assert len(environments) == 1_133
    assert {
        instance_id: values
        for instance_id, values in environments.items()
        if len(values) != 1
    } == {}
    assert {
        (image.split(":")[0], path)
        for values in environments.values()
        for repository, image, path in values
        if repository == "fasterxml/jackson-core"
    } == {("docker.io/mswebench/fasterxml_m_jackson-core", "/home/jackson-core")}


@pytest.mark.parametrize(
    ("repo_url", "message"),
    [
        ("https://github.com/owner/other.git", "repo_url names owner/other"),
        ("https://gitlab.com/owner/repo.git", "not a GitHub repository URL"),
    ],
)
def test_rows_whose_repository_sources_disagree_are_rejected(
    tmp_path: Path, repo_url: str, message: str
) -> None:
    row = {**_row("conflict", 1), "repo_url": repo_url}
    path = _write_dataset(tmp_path / "source.parquet", [row])

    with pytest.raises(InvalidDatasetRowsError, match=message):
        ContextBenchAdapter(path, tmp_path / "tasks").run()


def test_zero_gold_line_ranges_are_rejected_not_defaulted(tmp_path: Path) -> None:
    """A malformed 0 coordinate fails validation instead of taking a default.

    Defaults apply only to absent coordinates, so `start_line: 0` and
    `end_line: 0` reach the range check and do not change which lines a gold
    span covers.
    """
    row = _row("zero-range", 1)
    gold = json.loads(row["gold_context"])
    gold[0]["start_line"] = 0
    row["gold_context"] = json.dumps(gold)
    path = _write_dataset(tmp_path / "source.parquet", [row])

    with pytest.raises(ValueError, match="invalid gold line range 0-"):
        ContextBenchAdapter(path, tmp_path / "tasks").run(task_ids=["zero-range"])

    gold[0]["start_line"] = 2
    gold[0]["end_line"] = 0
    row["gold_context"] = json.dumps(gold)
    _write_dataset(path, [row])

    with pytest.raises(ValueError, match="invalid gold line range 2-0"):
        ContextBenchAdapter(path, tmp_path / "tasks").run(task_ids=["zero-range"])


@pytest.mark.parametrize("raw", ["", "src/../../outside.py", "/testbed/../x.py"])
def test_gold_paths_outside_the_repository_are_rejected(
    tmp_path: Path, raw: str
) -> None:
    row = _row("outside", 1)
    gold = json.loads(row["gold_context"])
    gold[0]["file"] = raw
    row["gold_context"] = json.dumps(gold)
    path = _write_dataset(tmp_path / "source.parquet", [row])

    with pytest.raises(InvalidDatasetRowsError, match="invalid gold context path"):
        ContextBenchAdapter(path, tmp_path / "tasks").run(task_ids=["outside"])


def test_invalid_row_errors_name_the_row_once(tmp_path: Path) -> None:
    row = {**_row("broken", 1), "problem_statement": "  "}
    path = _write_dataset(tmp_path / "source.parquet", [row, _row("valid", 2)])

    with pytest.raises(InvalidDatasetRowsError) as raised:
        ContextBenchAdapter(path, tmp_path / "tasks").run(task_ids=["broken"])

    assert str(raised.value) == (
        "1 selected ContextBench row(s) are invalid: broken: problem_statement is empty"
    )


def test_invalid_source_rows_can_be_explicitly_skipped(tmp_path: Path) -> None:
    """The checked-in corrections restore one malformed row; three stay invalid."""
    contract = _corpus_contract()
    valid_id = "Multi-SWE-Bench__go__maintenance__bugfix__2fea5f6b"
    selected_ids = [valid_id, *sorted(UPSTREAM_MALFORMED_FULL_IDS)]
    path = _write_dataset(
        tmp_path / "source.parquet",
        [_contract_row(contract, "full", instance_id) for instance_id in selected_ids],
    )
    output = tmp_path / "tasks"

    with pytest.raises(InvalidDatasetRowsError):
        ContextBenchAdapter(path, output).run(task_ids=selected_ids)
    generated = ContextBenchAdapter(path, output).run(
        task_ids=selected_ids,
        skip_invalid_source_rows=True,
    )

    generated_ids = [valid_id, *sorted(RESTORED_FULL_IDS)]
    assert [task.name for task in generated] == [
        _task_name(path, instance_id) for instance_id in generated_ids
    ]
    [entry] = _report(output)["datasets"].values()
    assert set(entry["tasks"]) == set(generated_ids)
    assert {item["instance_id"] for item in entry["invalid_rows"]} == (
        MALFORMED_FULL_IDS
    )
    assert {item["instance_id"] for item in entry["corrections"]} == RESTORED_FULL_IDS


def test_generation_preserves_selection_order_and_limit(
    dataset: Path, tmp_path: Path
) -> None:
    adapter = ContextBenchAdapter(dataset, tmp_path / "tasks")

    generated = adapter.run(task_ids=["second", "first"], limit=1)

    assert [task.name for task in generated] == [_task_name(dataset, "second")]
    config = tomllib.loads((generated[0] / "task.toml").read_text(encoding="utf-8"))
    assert config["metadata"]["instance_id"] == "second"
    assert config["metadata"]["contextbench_commit"] == CONTEXTBENCH_COMMIT
    assert config["metadata"]["dataset"] == adapter.dataset_name

    with pytest.raises(ValueError, match="not found"):
        adapter.run(task_ids=["missing"])
    with pytest.raises(ValueError, match="duplicate"):
        adapter.run(task_ids=["first", "first"])


def test_task_names_include_the_dataset(dataset: Path, tmp_path: Path) -> None:
    """One instance in two datasets yields two distinct task names."""
    other = _write_dataset(
        tmp_path / "other.parquet",
        [{**_row("first", 1), "problem_statement": "Different statement."}],
    )
    output = tmp_path / "tasks"

    [first] = ContextBenchAdapter(dataset, output).run(task_ids=["first"])
    [other_first] = ContextBenchAdapter(other, output).run(task_ids=["first"])

    assert first.name == _task_name(dataset, "first")
    assert other_first.name == _task_name(other, "first")
    assert first.name != other_first.name
    # The 16 hex digits are the start of the instance ID's SHA-256.
    assert task_directory_name("verified", "first") == "verified-a7937b64b8caa58f"
    for task in (first, other_first):
        config = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
        assert config["task"]["name"] == f"contextbench/{task.name}"
        assert config["metadata"]["dataset"] == task.name.rsplit("-", 1)[0]


def test_pinned_datasets_are_labeled_by_name() -> None:
    for name, spec in DATASETS.items():
        assert _dataset_label(spec.sha256) == name
    assert _dataset_label("ab" * 32) == "custom-abababab"


def test_parity_tasks_generate(tmp_path: Path) -> None:
    contract = _corpus_contract()
    path = _write_dataset(
        tmp_path / "parity.parquet",
        [
            {
                **_contract_row(contract, PARITY_DATASET_NAME, instance_id),
                "problem_statement": "Published problem statement.",
            }
            for instance_id in contract["datasets"][PARITY_DATASET_NAME]["instance_ids"]
        ],
    )

    generated = ContextBenchAdapter(path, tmp_path / "tasks").run(
        task_ids=list(PARITY_TASK_IDS)
    )

    assert len({task.name for task in generated}) == len(PARITY_TASK_IDS)
    for task, instance_id in zip(generated, PARITY_TASK_IDS, strict=True):
        config = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
        assert config["metadata"]["instance_id"] == instance_id
        assert config["metadata"]["source"] == "Verified"


def test_parity_cli_uses_pinned_dataset_and_task_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, Any] = {}
    dataset_path = tmp_path / "verified-test.parquet"
    dataset_path.touch()

    class StubAdapter:
        def __init__(self, dataset_path: Path, output_dir: Path) -> None:
            calls["dataset_path"] = dataset_path
            calls["output_dir"] = output_dir

        def run(self, **kwargs: Any) -> list[Path]:
            calls["run"] = kwargs
            return [tmp_path / "task"] * len(PARITY_TASK_IDS)

    monkeypatch.setattr(
        main_module,
        "download_dataset",
        lambda spec: (
            calls.setdefault("dataset_name", spec.name),
            dataset_path,
        )[1],
    )
    monkeypatch.setattr(main_module, "ContextBenchAdapter", StubAdapter)
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        ["contextbench", "--split", "parity", "--output-dir", str(output)],
    )

    main_module.main()

    assert calls["dataset_name"] == PARITY_DATASET_NAME
    assert calls["dataset_path"] == dataset_path
    assert calls["output_dir"] == output
    assert calls["run"]["task_ids"] == list(PARITY_TASK_IDS)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--split", "parity", "--dataset-path", "custom.parquet"],
        ["--split", "parity", "--dataset", "full"],
        ["--split", "parity", "--task-ids", "one,two"],
    ],
)
def test_parity_cli_rejects_conflicting_selection_flags(
    arguments: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["contextbench", *arguments])

    with pytest.raises(SystemExit):
        main_module.main()


def test_task_ids_are_parsed_by_argparse(
    dataset: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["contextbench", "--task-ids", " , "])
    with pytest.raises(SystemExit) as raised:
        main_module.main()
    assert raised.value.code == 2
    assert "--task-ids: must contain at least one ID" in capsys.readouterr().err

    output = tmp_path / "tasks"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "contextbench",
            "--dataset-path",
            str(dataset),
            "--output-dir",
            str(output),
            "--task-ids",
            " second, first ,",
        ],
    )
    main_module.main()
    assert set(_report(output)["datasets"][_dataset_label_of(dataset)]["tasks"]) == {
        "first",
        "second",
    }


def test_instruction_wraps_the_verbatim_problem_statement(tmp_path: Path) -> None:
    statement = "Inspect __WEBPACK_IMPORTED_MODULE_0__.\r\n\r\n  Indented\tline"
    row = {**_row("first", 1), "problem_statement": f"\n {statement} \n\n"}
    path = _write_dataset(tmp_path / "source.parquet", [row])

    [task] = ContextBenchAdapter(path, tmp_path / "tasks").run()
    instruction = (task / "instruction.md").read_bytes().decode("utf-8")

    template = (
        ADAPTER_ROOT / "src/contextbench/task-template/instruction.md"
    ).read_text(encoding="utf-8")
    assert instruction == template.replace("__PROBLEM_STATEMENT__", statement)
    assert f"<issue_description>\n{statement}\n</issue_description>" in instruction
    assert "/workspace" in instruction
    assert "non-test source files" in instruction


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('"Title\\n\\nBody with \\"quotes\\""', 'Title\n\nBody with "quotes"'),
        # Decoded once: the result is used even if it is quoted itself.
        ('"\\"inner\\""', '"inner"'),
        # Not one JSON string literal as a whole.
        ('"show_save_as_new" in admin can add', None),
        (' "a\\nb"', None),
        ('"a\\nb"\n', None),
        ('"unterminated', None),
        ('"', None),
        ('["a\\nb"]', None),
        ("Plain text with a literal \\n", None),
    ],
)
def test_problem_statements_are_decoded_only_when_one_json_string(
    value: str, expected: str | None
) -> None:
    assert decoded_json_string(value) == expected


def test_generation_decodes_json_quoted_statements(tmp_path: Path) -> None:
    rows = [
        {**_row("quoted", 1), "problem_statement": json.dumps("Title\n\nBody")},
        _row("plain", 2),
    ]
    output = tmp_path / "tasks"

    quoted, plain = ContextBenchAdapter(
        _write_dataset(tmp_path / "source.parquet", rows), output
    ).run()

    instruction = (quoted / "instruction.md").read_text(encoding="utf-8")
    assert "<issue_description>\nTitle\n\nBody\n</issue_description>" in instruction
    assert "task 2." in (plain / "instruction.md").read_text(encoding="utf-8")
    [entry] = _report(output)["datasets"].values()
    assert entry["decoded_problem_statements"] == ["quoted"]


def _corrections_file(
    path: Path, instance_id: str, replaced: str, value: str
) -> dict[str, Any]:
    correction = {
        "instance_id": instance_id,
        "field": "problem_statement",
        "replaces_sha256": hashlib.sha256(replaced.encode()).hexdigest(),
        "value": value,
        "source": {
            "dataset": "owner/source",
            "revision": "0" * 40,
            "file": "data/test.parquet",
            "instance_id": "owner__repo-1",
        },
        "reason": "The row carries another instance's statement.",
    }
    path.write_text(json.dumps({"corrections": [correction]}), encoding="utf-8")
    return correction


def test_corrections_replace_the_upstream_value_and_are_reported(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corrections = tmp_path / "corrections.json"
    correction = _corrections_file(
        corrections, "first", "Find relevant code for task 1.", "Corrected statement."
    )
    monkeypatch.setattr(adapter_module, "CORRECTIONS_PATH", corrections)
    output = tmp_path / "tasks"

    first, second = ContextBenchAdapter(dataset, output).run()

    instruction = (first / "instruction.md").read_text(encoding="utf-8")
    assert "<issue_description>\nCorrected statement.\n</issue_description>" in (
        instruction
    )
    assert "task 2." in (second / "instruction.md").read_text(encoding="utf-8")
    [entry] = _report(output)["datasets"].values()
    assert entry["corrections"] == [
        {
            "instance_id": "first",
            "field": "problem_statement",
            "source": correction["source"],
            "reason": correction["reason"],
        }
    ]


def test_corrections_of_a_different_upstream_value_are_rejected(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corrections = tmp_path / "corrections.json"
    _corrections_file(corrections, "first", "Another statement.", "Corrected.")
    monkeypatch.setattr(adapter_module, "CORRECTIONS_PATH", corrections)
    output = tmp_path / "tasks"

    with pytest.raises(
        InvalidDatasetRowsError,
        match="first: problem_statement is not the value its correction replaces",
    ):
        ContextBenchAdapter(dataset, output).run()
    [second] = ContextBenchAdapter(dataset, output).run(skip_invalid_source_rows=True)

    assert second.name == _task_name(dataset, "second")
    [entry] = _report(output)["datasets"].values()
    assert entry["corrections"] == []
    assert [item["instance_id"] for item in entry["invalid_rows"]] == ["first"]


def test_checked_in_corrections_name_the_instance_in_their_source() -> None:
    contract = _corpus_contract()
    corrections = load_corrections()

    assert {item.instance_id for item in corrections} == {
        "SWE-Bench-Pro__go__maintenance__bugfix__2cef67df",
        "SWE-Bench-Pro__javascript__maintenance__bugfix__ac8400d9",
        *RESTORED_FULL_IDS,
    }
    empty = hashlib.sha256(b"").hexdigest()
    for correction in corrections:
        assert correction.field == "problem_statement"
        assert re.fullmatch(r"[0-9a-f]{64}", correction.replaces_sha256)
        assert set(correction.source) == {"dataset", "revision", "file", "instance_id"}
        assert re.fullmatch(r"[0-9a-f]{40}", correction.source["revision"])
        assert correction.value.strip()
        assert correction.reason
        rows = [
            published["instances"][correction.instance_id]
            for published in contract["datasets"].values()
            if correction.instance_id in published["instances"]
        ]
        assert {row["original_inst_id"] for row in rows} == {
            correction.source["instance_id"]
        }
        # Only the restored rows lack a statement upstream.
        assert {row["problem_statement_present"] for row in rows} == {
            correction.replaces_sha256 != empty
        }


def test_interrupted_generation_publishes_nothing(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "tasks"
    adapter = ContextBenchAdapter(dataset, output)
    original = adapter._write_task
    calls = 0

    def fail_on_second_task(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected generation failure")
        original(*args, **kwargs)

    monkeypatch.setattr(adapter, "_write_task", fail_on_second_task)

    with pytest.raises(RuntimeError, match="injected generation failure"):
        adapter.run()

    assert list(output.iterdir()) == []


def test_failed_publish_restores_the_replaced_tasks(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "out"
    adapter = ContextBenchAdapter(dataset, output)
    first, second = adapter.run()
    (first / "marker").write_text("original", encoding="utf-8")
    report = (output / REPORT_FILENAME).read_bytes()
    original_rename = Path.rename

    def rename(self: Path, target: Any) -> Path:
        staged = self.parent.parent.name.startswith(".contextbench-staging-")
        if staged and self.parent.name == "tasks" and self.name == second.name:
            raise PermissionError("injected publish failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", rename)

    with pytest.raises(PermissionError, match="injected publish failure"):
        adapter.run(overwrite=True)

    assert (first / "marker").read_text(encoding="utf-8") == "original"
    assert (second / "task.toml").is_file()
    assert (output / REPORT_FILENAME).read_bytes() == report
    assert sorted(path.name for path in output.iterdir()) == sorted(
        [first.name, second.name, "metric.py", REPORT_FILENAME]
    )


def test_any_publish_failure_restores_every_original(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "out"
    adapter = ContextBenchAdapter(dataset, output)
    first, _ = adapter.run()
    (first / "marker").write_text("original", encoding="utf-8")
    (output / "metric.py").write_text("# original metric\n", encoding="utf-8")
    report = (output / REPORT_FILENAME).read_bytes()
    original_rename = Path.rename

    def rename(self: Path, target: Any) -> Path:
        staged = self.parent.name.startswith(".contextbench-staging-")
        if staged and self.name == REPORT_FILENAME:
            raise RuntimeError("injected report failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", rename)

    with pytest.raises(RuntimeError, match="injected report failure"):
        adapter.run(overwrite=True)

    assert (first / "marker").read_text(encoding="utf-8") == "original"
    assert (output / "metric.py").read_text(encoding="utf-8") == "# original metric\n"
    assert (output / REPORT_FILENAME).read_bytes() == report
    assert not list(output.glob(".contextbench-staging-*"))


def test_report_drops_tasks_deleted_from_disk(dataset: Path, tmp_path: Path) -> None:
    output = tmp_path / "tasks"
    first, second = ContextBenchAdapter(dataset, output).run()
    other = _write_dataset(tmp_path / "other.parquet", [_row("third", 3)])
    [third] = ContextBenchAdapter(other, output).run()
    shutil.rmtree(second)
    shutil.rmtree(third)

    ContextBenchAdapter(dataset, output).run(task_ids=["first"], overwrite=True)

    datasets = _report(output)["datasets"]
    assert list(datasets) == [_dataset_label_of(dataset)]
    assert datasets[_dataset_label_of(dataset)]["tasks"] == {"first": first.name}


def test_subset_regeneration_keeps_the_dataset_report(
    dataset: Path, tmp_path: Path
) -> None:
    output = tmp_path / "tasks"
    first, second = ContextBenchAdapter(dataset, output).run()
    other = _write_dataset(tmp_path / "other.parquet", [_row("third", 3)])

    ContextBenchAdapter(dataset, output).run(task_ids=["first"], overwrite=True)
    [third] = ContextBenchAdapter(other, output).run()

    report = _report(output)
    assert report["contextbench_commit"] == CONTEXTBENCH_COMMIT
    assert report["datasets"] == {
        _dataset_label_of(dataset): {
            "dataset_file": "contextbench.parquet",
            "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            "rows": 2,
            "invalid_rows": [],
            "corrections": [],
            "decoded_problem_statements": [],
            "tasks": {"first": first.name, "second": second.name},
        },
        _dataset_label_of(other): {
            "dataset_file": "other.parquet",
            "dataset_sha256": hashlib.sha256(other.read_bytes()).hexdigest(),
            "rows": 1,
            "invalid_rows": [],
            "corrections": [],
            "decoded_problem_statements": [],
            "tasks": {"third": third.name},
        },
    }


def test_existing_selected_task_requires_overwrite(
    dataset: Path, tmp_path: Path
) -> None:
    output = tmp_path / "tasks"
    adapter = ContextBenchAdapter(dataset, output)
    [task] = adapter.run(task_ids=["first"])
    marker = task / "user-marker"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists.*--overwrite"):
        adapter.run(task_ids=["first"])

    adapter.run(task_ids=["first"], overwrite=True)
    assert not marker.exists()
    assert not list(output.glob(".contextbench-staging-*"))


def test_existing_task_preflight_writes_nothing(dataset: Path, tmp_path: Path) -> None:
    output = tmp_path / "tasks"
    adapter = ContextBenchAdapter(dataset, output)
    [first] = adapter.run(task_ids=["first"])
    report = (output / REPORT_FILENAME).read_bytes()

    with pytest.raises(RuntimeError, match="already exists"):
        adapter.run(task_ids=["first", "second"])

    assert first.is_dir()
    assert not (output / _task_name(dataset, "second")).exists()
    assert (output / REPORT_FILENAME).read_bytes() == report


def test_generated_task_isolated_and_fully_rendered(
    dataset: Path, tmp_path: Path
) -> None:
    [task] = ContextBenchAdapter(dataset, tmp_path / "tasks").run(task_ids=["first"])

    config = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
    assert config["verifier"]["environment_mode"] == "separate"
    assert "network_mode" not in config["verifier"]["environment"]
    assert config["metadata"]["primary_metric"] == "contextbench_file_coverage"
    assert config["metadata"]["source"] == "Verified"
    assert config["metadata"]["language"] == "python"
    assert config["metadata"]["original_instance_id"] == "owner__repo-1"
    assert config["metadata"]["native_image"] == (
        "docker.io/swebench/sweb.eval.x86_64.owner_1776_repo-1:latest"
    )
    assert config["metadata"]["native_repository_path"] == "/testbed"
    assert config["artifacts"] == ["/logs/agent"]
    assert (tmp_path / "tasks/metric.py").read_bytes() == (
        ADAPTER_ROOT / "src/contextbench/aggregation.py"
    ).read_bytes()

    environment_files = {
        path.relative_to(task / "environment").as_posix()
        for path in (task / "environment").rglob("*")
        if path.is_file()
    }
    assert environment_files == {"Dockerfile"}

    expected_hidden = {
        "tests/gold.json",
        "tests/score.py",
        "solution/oracle-trajectory.json",
        "solution/solution.patch",
    }
    assert all((task / relative).is_file() for relative in expected_hidden)
    package = task / "tests/harbor_contextbench"
    assert {
        path.relative_to(package).as_posix()
        for path in package.rglob("*.py")
        if path.relative_to(package).parts[0] != "vendor"
    } == {
        "__init__.py",
        "attribution/__init__.py",
        "attribution/receipts.py",
        "attribution/rules.py",
        "attribution/trajectory.py",
        "attribution/types.py",
        "scoring.py",
        "vendor_api.py",
    }
    gold = json.loads((task / "tests/gold.json").read_text(encoding="utf-8"))
    assert all("content" not in annotation for annotation in gold["gold_context"])
    assert not list(task.rglob("__pycache__"))
    assert not list(task.rglob("*.pyc"))
    assert (package / "vendor/LICENSE").is_file()
    manifest = (package / "vendor/MANIFEST.sha256").read_text(encoding="utf-8")
    for line in manifest.splitlines():
        digest, relative = line.split("  ", 1)
        copy = package / "vendor" / relative
        assert hashlib.sha256(copy.read_bytes()).hexdigest() == digest, relative

    for path in task.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "__BASE_COMMIT__" not in text
            assert "__REPOSITORY_URL__" not in text


@pytest.mark.usefixtures("windows_newlines")
def test_generation_writes_the_same_bytes_where_text_mode_translates_newlines(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.txt"
    probe.write_text("line\n", encoding="utf-8")
    assert probe.read_bytes() == b"line\r\n"
    crlf = _row("second", 2)
    crlf["patch"] = crlf["patch"].replace("\n", "\r\n")
    path = _write_dataset(tmp_path / "rows.parquet", [_row("first", 1), crlf])
    output = tmp_path / "tasks"

    _, second = ContextBenchAdapter(path, output).run()

    # The reference patch keeps its own line endings, byte for byte.
    patch = second / "solution/solution.patch"
    assert patch.read_bytes() == crlf["patch"].encode()
    written = [file for file in output.rglob("*") if file.is_file() and file != patch]
    assert len(written) > 30
    assert [file for file in written if b"\r\n" in file.read_bytes()] == []


@pytest.mark.parametrize("relative", ["environment/Dockerfile", "tests/Dockerfile"])
def test_generated_repositories_are_sanitized_to_one_commit(
    dataset: Path, tmp_path: Path, relative: str
) -> None:
    [task] = ContextBenchAdapter(dataset, tmp_path / "tasks").run(task_ids=["first"])
    dockerfile = (task / relative).read_text(encoding="utf-8")

    assert "fetch --depth=1" in dockerfile
    assert "checkout --detach" in dockerfile
    assert "remote remove origin" in dockerfile
    assert "reflog expire --expire=now --all" in dockerfile
    assert "gc --prune=now" in dockerfile


def _agent_dockerfile(tmp_path: Path, source: str) -> tuple[str, list[str]]:
    row = _row("first", 1, source)
    path = _write_dataset(tmp_path / f"{source}.parquet", [row])
    [task] = ContextBenchAdapter(path, tmp_path / source).run()
    dockerfile = (task / "environment/Dockerfile").read_text(encoding="utf-8")
    [removal] = [
        line for line in dockerfile.splitlines() if line.startswith("RUN rm -rf ")
    ]
    return dockerfile, shlex.split(removal)[3:]


def test_agent_image_keeps_the_native_tree_and_swaps_its_history(
    tmp_path: Path,
) -> None:
    dockerfile, removed = _agent_dockerfile(tmp_path, "Verified")
    commit = f"{1:040x}"

    image = "docker.io/swebench/sweb.eval.x86_64.owner_1776_repo-1:latest"
    assert (
        f"FROM --platform=linux/amd64 {image}@{synthetic_digest(image)}\n" in dockerfile
    )
    # Only the history is replaced, so ignored build state survives, and only
    # after the native checkout is found where expected.
    assert removed == ["/workspace", "/testbed/.git"]
    assert dockerfile.index('RUN test -e "/testbed/.git"\n') < dockerfile.index(
        "RUN rm -rf "
    )
    assert "COPY --from=source /repository/.git /testbed/.git" in dockerfile
    assert f'git reset --quiet "{commit}"' in dockerfile
    assert "--hard" not in dockerfile
    assert "clean" not in dockerfile
    assert 'ln -s "/testbed" /workspace' in dockerfile


def _git(cwd: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-c", "protocol.file.allow=always", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ["PATH"],
            "HOME": str(cwd),
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        },
    )
    return result.stdout.strip()


# Untracked build output that no .gitignore covers, with names that are
# patterns or comments in an exclude file.
UNTRACKED_IMAGE_FILES = ["[x]*?.txt", "#notes", "!bang", "trailing ", "back\\slash"]
# 2025-03-18 09:26:25 UTC, a native image file's mtime.
IMAGE_MTIME_NS = 1_742_289_985 * 10**9


def _swapped_native_tree(tmp_path: Path) -> tuple[Path, str, str]:
    """Run the agent Dockerfile's swap on a native tree with build output.

    Returns the swapped tree, its base commit, and the task's collect command
    with its paths moved into `tmp_path`.
    """
    library = tmp_path / "library"
    library.mkdir()
    (library / "lib.c").write_text("lib\n", encoding="utf-8")
    _git(library, "init", "-q")
    _git(library, "add", ".")
    _git(library, "commit", "-qm", "library")
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "main.c").write_text("main\n", encoding="utf-8")
    (upstream / "notes.txt").write_text("notes\n", encoding="utf-8")
    (upstream / ".gitignore").write_text("*.o\n", encoding="utf-8")
    _git(upstream, "init", "-q")
    _git(upstream, "add", ".")
    _git(upstream, "commit", "-qm", "first")
    _git(upstream, "submodule", "add", "-q", str(library), "modules/library")
    _git(upstream, "commit", "-qm", "base")
    base = _git(upstream, "rev-parse", "HEAD")
    # The native tree has build output, a populated submodule, one more local
    # commit, like the SWE-bench images, and an uncommitted build-time edit.
    native = tmp_path / "native"
    _git(tmp_path, "clone", "-q", "--recurse-submodules", str(upstream), "native")
    (native / "main.o").write_text("object\n", encoding="utf-8")
    (native / "modules/library/lib.o").write_text("object\n", encoding="utf-8")
    (native / "main.c").write_text("patched by the image build\n", encoding="utf-8")
    _git(native, "commit", "-qam", "native setup")
    (native / "notes.txt").unlink()
    for name in UNTRACKED_IMAGE_FILES:
        (native / name).write_text("generated\n", encoding="utf-8")
    (native / "build output").mkdir()
    (native / "build output/data.bin").write_bytes(b"\0generated")
    # Image files predate the agent image build, as in a native image.
    for path in native.rglob("*"):
        if ".git" not in path.relative_to(native).parts:
            os.utime(path, ns=(IMAGE_MTIME_NS, IMAGE_MTIME_NS), follow_symlinks=False)
    stripped = tmp_path / "stripped"
    stripped.mkdir()
    _git(stripped, "init", "-q")
    _git(stripped, "fetch", "-q", "--depth=1", f"file://{upstream}", base)
    _git(stripped, "checkout", "-q", "--detach", base)

    row = {**_row("first", 1), "base_commit": base}
    path = _write_dataset(tmp_path / "source.parquet", [row])
    [task] = ContextBenchAdapter(path, tmp_path / "tasks").run()
    dockerfile = (task / "environment/Dockerfile").read_text(encoding="utf-8")
    # The RUN step after `cd /workspace`, up to its last continued line.
    lines = dockerfile.split("&& cd /workspace \\\n", 1)[1].splitlines()
    end = next(i for i, line in enumerate(lines) if not line.endswith("\\"))
    swap = "\n".join(lines[: end + 1]).strip().removeprefix("&& ")
    shutil.rmtree(native / ".git")
    shutil.copytree(stripped / ".git", native / ".git")
    subprocess.run(["sh", "-c", swap], cwd=native, check=True)
    config = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
    collect = (
        str(config["verifier"]["collect"][0]["command"])
        .replace("/logs/artifacts", str(tmp_path / "artifacts"))
        .replace("cd /workspace", f"cd {shlex.quote(str(native))}")
    )
    return native, base, collect


def test_history_swap_keeps_build_state_and_submodule_files(tmp_path: Path) -> None:
    native, base, _ = _swapped_native_tree(tmp_path)

    assert (native / "main.o").is_file()
    assert (native / "modules/library/lib.c").is_file()
    assert (native / "modules/library/lib.o").is_file()
    assert all((native / name).is_file() for name in UNTRACKED_IMAGE_FILES)
    # The image's edits to tracked files stay in the working tree.
    assert (native / "main.c").read_text(encoding="utf-8") == (
        "patched by the image build\n"
    )
    assert not (native / "notes.txt").exists()
    assert _git(native, "status", "--porcelain") == "M main.c\n D notes.txt"
    # HEAD and the index are the one-commit base, with no refs or remotes.
    assert _git(native, "rev-parse", "HEAD") == base
    assert _git(native, "diff", "--cached", "--quiet", base) == ""
    assert _git(native, "rev-list", "--all", "--count") == "1"
    assert _git(native, "for-each-ref") == ""
    assert _git(native, "remote") == ""


def test_model_patch_holds_only_the_agents_changes(tmp_path: Path) -> None:
    """The export leaves out the image's own edits and untracked files."""
    native, _, collect = _swapped_native_tree(tmp_path)
    patch = tmp_path / "artifacts/contextbench-model.patch"
    error = tmp_path / "artifacts/contextbench-collect-error.txt"

    subprocess.run(["sh", "-c", collect], check=True)
    assert patch.read_text(encoding="utf-8") == ""
    assert error.read_text(encoding="utf-8") == ""

    with (native / "main.c").open("a", encoding="utf-8") as stream:
        stream.write("edited\n")
    subprocess.run(["sh", "-c", collect], check=True)
    exported = patch.read_text(encoding="utf-8")
    assert re.findall(r"^diff --git .*$", exported, re.MULTILINE) == [
        "diff --git a/main.c b/main.c"
    ]
    assert re.findall(r"^[+-](?![+-]).*$", exported, re.MULTILINE) == ["+edited"]
    assert error.read_text(encoding="utf-8") == ""


def test_history_swap_records_the_images_stat_data_for_minimal_checks(
    tmp_path: Path,
) -> None:
    """Git compares size and mtime second, as the image recorded them."""
    native, _, _ = _swapped_native_tree(tmp_path)

    assert _git(native, "config", "core.checkStat") == "minimal"
    assert _git(native, "config", "core.trustctime") == "false"
    for index in ("index", "contextbench-baseline-index"):
        debug = subprocess.run(
            ["git", "ls-files", "--debug", "--", ".gitignore"],
            cwd=native,
            env={**os.environ, "GIT_INDEX_FILE": str(native / ".git" / index)},
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert f"mtime: {IMAGE_MTIME_NS // 10**9}:0" in debug, index


def test_collect_ignores_the_agents_index(tmp_path: Path) -> None:
    """A same-size edit in the second the agent's index recorded still shows.

    Git compares only size and mtime second, so with the agent's index the
    `git add -A` of the images' Git releases (2.20 to 2.39) misses this edit.
    The collect step compares against the image's baseline index instead.
    """
    native, _, collect = _swapped_native_tree(tmp_path)
    patch = tmp_path / "artifacts/contextbench-model.patch"
    error = tmp_path / "artifacts/contextbench-collect-error.txt"
    edited = native / "main.c"
    # A past second, so Git does not treat the entry as racily clean.
    second = 1_780_000_000 * 10**9
    edited.write_text("first agent edit\n", encoding="utf-8")
    os.utime(edited, ns=(second, second + 100))
    _git(native, "add", "main.c")
    _git(native, "status", "--porcelain")
    edited.write_text("other agent edit\n", encoding="utf-8")
    os.utime(edited, ns=(second, second + 900))
    # A Git command the agent interrupted leaves the index locked.
    (native / ".git/index.lock").write_text("", encoding="utf-8")

    subprocess.run(["sh", "-c", collect], check=True)

    exported = patch.read_text(encoding="utf-8")
    assert re.findall(r"^[+-](?![+-]).*$", exported, re.MULTILINE) == [
        "-patched by the image build",
        "+other agent edit",
    ]
    assert error.read_text(encoding="utf-8") == ""
    assert not (native / ".git/contextbench-collect-index").exists()


def test_interrupted_collect_leaves_its_incomplete_marker(tmp_path: Path) -> None:
    """Harbor's timeout can stop the collect step while it writes the patch."""
    native, _, collect = _swapped_native_tree(tmp_path)
    patch = tmp_path / "artifacts/contextbench-model.patch"
    error = tmp_path / "artifacts/contextbench-collect-error.txt"
    with (native / "main.c").open("a", encoding="utf-8") as stream:
        stream.write("edited\n")
    # A `git` that writes part of the diff and then kills the collect shell.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real_git = shutil.which("git")
    assert real_git is not None
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/bin/sh\n"
        'for argument; do if [ "$argument" = diff ]; then\n'
        "    printf 'diff --git a/main.c b/main.c\\n'; kill -9 $PPID; exit 1\n"
        "fi; done\n"
        f'exec {shlex.quote(real_git)} "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    patch.parent.mkdir()
    patch.write_text("stale patch from an earlier run\n", encoding="utf-8")

    result = subprocess.run(
        ["sh", "-c", collect],
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
        check=False,
    )

    assert result.returncode == -9
    assert error.read_text(encoding="utf-8") == "collect_incomplete\n"
    assert not patch.exists()
    assert patch.with_name(f"{patch.name}.partial").read_text(encoding="utf-8") == (
        "diff --git a/main.c b/main.c\n"
    )


def test_collect_reports_a_damaged_repository(tmp_path: Path) -> None:
    native, _, collect = _swapped_native_tree(tmp_path)
    (native / ".git/contextbench-baseline-index").unlink()

    subprocess.run(["sh", "-c", collect], check=True)

    artifacts = tmp_path / "artifacts"
    assert (artifacts / "contextbench-collect-error.txt").read_text(
        encoding="utf-8"
    ) == "git_state_invalid\n"
    assert sorted(path.name for path in artifacts.iterdir()) == [
        "contextbench-collect-error.txt"
    ]


@pytest.mark.parametrize("source", ["Verified", "Poly", "Multi"])
def test_agent_image_removes_the_source_grading_files(
    tmp_path: Path, source: str
) -> None:
    _, removed = _agent_dockerfile(tmp_path, source)

    repository_path = "/home/repo" if source == "Multi" else "/testbed"
    assert removed[:2] == ["/workspace", f"{repository_path}/.git"]
    assert set(removed[2:]) == (MULTI_SWE_BENCH_HARNESS if source == "Multi" else set())


@pytest.mark.parametrize(
    ("source", "native_path"),
    [("Verified", "/testbed"), ("Poly", "/testbed"), ("Multi", "/home/repo")],
)
def test_verifier_resolves_paths_under_the_workspace_and_the_native_path(
    tmp_path: Path, source: str, native_path: str
) -> None:
    """The agent sees the repository at /workspace, a link to the native path."""
    row = _row("first", 1, source)
    path = _write_dataset(tmp_path / f"{source}.parquet", [row])
    [task] = ContextBenchAdapter(path, tmp_path / source).run()

    configuration = json.loads(
        (task / "tests/attribution.json").read_text(encoding="utf-8")
    )

    assert configuration == {"repository_roots": ["/workspace", native_path]}


def test_swe_bench_images_activate_the_testbed_environment(tmp_path: Path) -> None:
    verified, _ = _agent_dockerfile(tmp_path, "Verified")
    multi, _ = _agent_dockerfile(tmp_path, "Multi")

    assert "PATH=/opt/miniconda3/envs/testbed/bin:$PATH" in verified
    assert "CONDA_DEFAULT_ENV=testbed" in verified
    assert 'test "$(command -v python)" = /opt/miniconda3/envs/testbed/bin/python' in (
        verified
    )
    assert "testbed" not in multi


@pytest.mark.parametrize(
    ("source", "original_id", "repository", "image", "repository_path"),
    [
        (
            "Verified",
            "django__django-15104",
            "django/django",
            ("docker.io/swebench/sweb.eval.x86_64.django_1776_django-15104:latest"),
            "/testbed",
        ),
        (
            "Pro",
            "instance_NodeBB__NodeBB-abc-vnan",
            "NodeBB/NodeBB",
            "docker.io/jefzda/sweap-images:nodebb.nodebb-NodeBB__NodeBB-abc",
            "/app",
        ),
        (
            "Pro",
            "instance_element-hq__element-web-4fec436883b601a3cac2d4a58067e597f737b817-vnan",
            "element-hq/element-web",
            (
                "docker.io/jefzda/sweap-images:element-hq.element-element-hq__"
                "element-web-4fec436883b601a3cac2d4a58067e597f737b817"
            ),
            "/app",
        ),
        (
            "Pro",
            "instance_element-hq__element-web-ec0f940ef0e8e3b61078f145f34dc40d1938e6c5-vnan",
            "element-hq/element-web",
            (
                "docker.io/jefzda/sweap-images:element-hq.element-web-element-hq__"
                "element-web-ec0f940ef0e8e3b61078f145f34dc40d1938e6c5-vnan"
            ),
            "/app",
        ),
        (
            "Poly",
            "keras-team__keras-18553",
            "keras-team/keras",
            (
                "ghcr.io/timesler/"
                "swe-polybench.eval.x86_64.keras-team__keras-18553:latest"
            ),
            "/testbed",
        ),
        (
            "Multi",
            "fasterxml__jackson-core-183",
            "fasterxml/jackson-core",
            "docker.io/mswebench/fasterxml_m_jackson-core:pr-183",
            "/home/jackson-core",
        ),
    ],
)
def test_native_environment_matches_source_benchmark(
    source: str,
    original_id: str,
    repository: str,
    image: str,
    repository_path: str,
) -> None:
    native = native_environment(source, original_id, repository)

    assert (native.image, native.repository_path) == (image, repository_path)


_FROM = re.compile(r"^FROM (?P<arguments>.+)$", re.MULTILINE)
_PINNED = re.compile(
    r"--platform=linux/amd64 (?P<image>[^\s@]+:[^\s@]+)@(?P<digest>sha256:[0-9a-f]{64})"
    r"(?: AS \w+)?"
)


def _pinned_digests() -> dict[str, str]:
    pinned = json.loads(IMAGE_DIGESTS_PATH.read_text(encoding="utf-8"))
    return {str(image): str(digest) for image, digest in pinned.items()}


def test_every_dataset_rows_image_has_a_pinned_digest() -> None:
    """image-digests.json covers exactly the images the pinned datasets use."""
    images = {GIT_IMAGE, VERIFIER_IMAGE}
    for dataset_name in DATASETS:
        for row in _contract_rows(dataset_name):
            if row["instance_id"] not in MALFORMED_FULL_IDS:
                images.add(prepare_row(_restored(row)).native.image)

    digests = _pinned_digests()
    assert len(images) == 1_135
    assert set(digests) == images
    assert all(
        re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in digests.values()
    )


def test_every_generated_dockerfile_from_pins_a_digest(tmp_path: Path) -> None:
    """Every FROM keeps its tag and pins the image's linux/amd64 digest."""
    contract = _corpus_contract()
    corrected = {correction.instance_id for correction in load_corrections()}
    first_of_each_source: dict[str, dict[str, Any]] = {}
    for instance_id in contract["datasets"]["verified"]["instance_ids"]:
        if instance_id not in corrected:
            row = _contract_row(contract, "verified", instance_id)
            first_of_each_source.setdefault(row["source"], row)
    path = _write_dataset(
        tmp_path / "rows.parquet", list(first_of_each_source.values())
    )
    tasks = ContextBenchAdapter(path, tmp_path / "tasks").run()
    digests = _pinned_digests()

    assert len(tasks) == 4
    for task in tasks:
        native = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))[
            "metadata"
        ]["native_image"]
        expected = {
            "environment/Dockerfile": [GIT_IMAGE, native],
            "tests/Dockerfile": [GIT_IMAGE, VERIFIER_IMAGE],
        }
        for relative, images in expected.items():
            pins = [
                _PINNED.fullmatch(match["arguments"])
                for match in _FROM.finditer(
                    (task / relative).read_text(encoding="utf-8")
                )
            ]
            assert all(pins), relative
            assert [(pin["image"], pin["digest"]) for pin in pins if pin] == [
                (image, digests[image]) for image in images
            ]


def test_generation_without_an_image_digest_writes_nothing(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pinned = "docker.io/swebench/sweb.eval.x86_64.owner_1776_repo-1:latest"
    unpinned = "docker.io/swebench/sweb.eval.x86_64.owner_1776_repo-2:latest"
    digests = json.loads(IMAGE_DIGESTS_PATH.read_text(encoding="utf-8"))
    digests[pinned] = synthetic_digest(pinned)
    monkeypatch.setattr(adapter_module, "_image_digests", lambda: digests)
    output = tmp_path / "tasks"

    message = f"no digest for 1 image(s): {unpinned};"
    with pytest.raises(RuntimeError, match=re.escape(message)):
        ContextBenchAdapter(dataset, output).run()

    assert not output.exists()


def test_oracle_is_a_static_trajectory_of_gold_reads(
    dataset: Path, tmp_path: Path
) -> None:
    [task] = ContextBenchAdapter(dataset, tmp_path / "tasks").run(task_ids=["first"])
    solve = (task / "solution/solve.sh").read_text(encoding="utf-8")
    trajectory = json.loads(
        (task / "solution/oracle-trajectory.json").read_text(encoding="utf-8")
    )

    # The image needs no interpreter: solve.sh only copies the trajectory.
    assert "cp /solution/oracle-trajectory.json /logs/agent/trajectory.json" in solve
    assert "python" not in solve
    assert sorted(path.name for path in (task / "solution").iterdir()) == [
        "oracle-trajectory.json",
        "solution.patch",
        "solve.sh",
    ]
    [step] = trajectory["steps"]
    assert step["tool_calls"] == [
        {
            "tool_call_id": "oracle-read-1",
            "function_name": "Read",
            "arguments": {
                "file_path": "/workspace/src/example_1.py",
                "offset": 2,
                "limit": 3,
            },
        }
    ]
    assert step["observation"] == {"results": [{"source_call_id": "oracle-read-1"}]}
    assert (task / "solution/solution.patch").read_text(encoding="utf-8") == (
        _row("first", 1)["patch"]
    )


def test_oracle_trajectory_is_valid_atif() -> None:
    trajectories = pytest.importorskip("harbor.models.trajectories")

    trajectories.Trajectory.model_validate(
        oracle_trajectory("task", [OracleRead("a.py", 1, 2), OracleRead("b", 3, 3)])
    )


def test_verifier_credits_every_oracle_read_of_a_base_file(tmp_path: Path) -> None:
    """Ranges past the end of a file still earn it; absent files earn nothing."""
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "short.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
    (repository / "other.py").write_text("one\ntwo\n", encoding="utf-8")
    trajectory = oracle_trajectory(
        "task",
        [
            OracleRead("short.py", 2, 9),
            OracleRead("other.py", 5, 6),
            OracleRead("absent.py", 1, 2),
        ],
    )

    prediction, evidence = project_atif(trajectory, repository, roots=("/workspace",))

    assert sorted(prediction["pred_files"]) == ["other.py", "short.py"]
    assert [item["result"] for item in evidence] == ["credit", "credit", "no_credit"]


def test_oracle_spans_are_the_gold_ranges(dataset: Path, tmp_path: Path) -> None:
    [task] = ContextBenchAdapter(dataset, tmp_path / "tasks").run(task_ids=["first"])
    repository = tmp_path / "repository"
    source = repository / "src/example_1.py"
    source.parent.mkdir(parents=True)
    source.write_text("one\ntwo\nthree\nfour\nfive\n", encoding="utf-8")

    prediction, _ = project_atif(
        json.loads(
            (task / "solution/oracle-trajectory.json").read_text(encoding="utf-8")
        ),
        repository,
        roots=("/workspace",),
    )

    assert prediction["pred_spans"] == {
        "src/example_1.py": [{"type": "line", "start": 2, "end": 4}]
    }


def test_gold_json_keeps_raw_paths_and_the_oracle_reads_normalized_ones(
    tmp_path: Path,
) -> None:
    raw_files = [
        "/workspace/owner__repo__0.1/.mocharc.js",
        ".github/workflows/ci.yml",
        "/testbed/src/app.py",
    ]
    row = _row("first", 1)
    row["gold_context"] = json.dumps(
        [{"file": file, "start_line": 1, "end_line": 2} for file in raw_files]
    )
    path = _write_dataset(tmp_path / "source.parquet", [row])

    [task] = ContextBenchAdapter(path, tmp_path / "tasks").run()

    gold = json.loads((task / "tests/gold.json").read_text(encoding="utf-8"))
    assert [item["file"] for item in gold["gold_context"]] == raw_files
    assert Gold({"gold_ctx": gold["gold_context"]}).files() == [
        ".mocharc.js",
        "github/workflows/ci.yml",
        "src/app.py",
    ]
    trajectory = json.loads(
        (task / "solution/oracle-trajectory.json").read_text(encoding="utf-8")
    )
    assert [
        call["arguments"]["file_path"] for call in trajectory["steps"][0]["tool_calls"]
    ] == [
        "/workspace/.mocharc.js",
        "/workspace/github/workflows/ci.yml",
        "/workspace/src/app.py",
    ]


@pytest.mark.parametrize("dataset_name", sorted(DATASETS))
def test_verifier_gold_equals_upstream_gold_for_every_row(dataset_name: str) -> None:
    """`Gold(gold.json)` must see exactly what `Gold` sees on the upstream row."""
    checked = 0
    for row in _contract_rows(dataset_name):
        if row["instance_id"] in MALFORMED_FULL_IDS:
            continue
        payload = json.loads(
            json.dumps(_gold_payload(row["instance_id"], prepare_row(_restored(row))))
        )
        verifier = Gold({"gold_ctx": payload["gold_context"]})
        upstream = Gold({"gold_ctx": row["gold_context"]})
        assert verifier.files() == upstream.files(), row["instance_id"]
        assert verifier.line_spans_init() == upstream.line_spans_init()
        checked += 1

    assert checked == DATASETS[dataset_name].rows - (
        len(MALFORMED_FULL_IDS) if dataset_name == "full" else 0
    )


def test_generated_verifier_entrypoint_imports_its_embedded_package(
    dataset: Path, tmp_path: Path
) -> None:
    [task] = ContextBenchAdapter(dataset, tmp_path / "tasks").run(task_ids=["first"])

    result = subprocess.run(
        [sys.executable, str(task / "tests/score.py"), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--trajectory" in result.stdout


def test_vendored_evaluator_matches_pinned_hash_manifest() -> None:
    expected: dict[str, str] = {}
    for line in (
        (VENDOR_ROOT / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines()
    ):
        digest, relative = line.split("  ", 1)
        expected[relative] = digest

    actual_files = {
        path.relative_to(VENDOR_ROOT).as_posix()
        for path in (VENDOR_ROOT / "contextbench_source/contextbench").rglob("*.py")
    }
    assert actual_files == set(expected)
    for relative, digest in expected.items():
        assert hashlib.sha256((VENDOR_ROOT / relative).read_bytes()).hexdigest() == (
            digest
        )
