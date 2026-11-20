"""The rescore phase: replay agent, in-process cells, and rescored reports."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, cast

import pytest

from contextbench.adapter import _VERIFIER_MODULES
from parity.files import load_json, write_json
from parity.report import (
    CONFIG_PATH,
    report,
    runtime_digest,
    score_record,
)
from tests.helpers import commit_files

pytest.importorskip("harbor", reason="install the adapter's harbor extra")

from harbor.models.agent.context import AgentContext
from harbor.models.task.config import TaskOS

from parity.replay_agent import ContextBenchReplayAgent
from parity.rescore import PACKAGE_DIR, rescore, retained_run, scorer_sources

TASK_ID = "Context__python__bugfix__1"
KEY = hashlib.sha256(TASK_ID.encode()).hexdigest()[:16]
DIRECTORY = f"custom-00000000-{KEY}"
WORKSPACE = "/workspace/owner__repo__1.0"
EXAMPLE = "".join(f"line_{number} = {number}\n" for number in range(1, 11))
GRANULARITIES = ("file", "line", "span", "symbol")


class _Environment:
    os = TaskOS.LINUX

    def __init__(self) -> None:
        self.uploads: list[tuple[str, str]] = []
        self.commands: list[str] = []

    async def upload_file(self, source_path: Path, target_path: str) -> None:
        self.uploads.append((Path(source_path).name, target_path))

    async def exec(self, command: str, timeout_sec: int | None = None) -> Any:
        self.commands.append(command)
        return type("Result", (), {"return_code": 0, "stdout": "", "stderr": ""})


def _retained_trial(
    job: Path, name: str, patch: str = "contextbench-model.patch"
) -> Path:
    trial = job / name
    (trial / "agent").mkdir(parents=True)
    (trial / "agent/trajectory.json").write_text("{}\n")
    (trial / "agent/openhands.trajectory.json").write_text(
        json.dumps(_openhands_read([2, 3]))
    )
    (trial / patch).parent.mkdir(parents=True, exist_ok=True)
    (trial / patch).write_text("diff --git a/x b/x\n")
    return trial


def test_replay_agent_restores_the_retained_trial_of_its_task(tmp_path: Path) -> None:
    source = tmp_path / "retained"
    # A trial name may carry more digest digits than the 16 of the key.
    trial = _retained_trial(source, f"contextbench-{KEY}671__AbCdEfG")
    _retained_trial(
        source,
        f"contextbench-{'0' * 16}__HiJkLmN",
        "artifacts/logs/artifacts/contextbench-model.patch",
    )
    logs = tmp_path / f"job/{DIRECTORY}__xyz/agent"
    logs.mkdir(parents=True)
    agent = ContextBenchReplayAgent(logs_dir=logs, source_job_dir=str(source))
    environment = _Environment()
    context = AgentContext()

    asyncio.run(agent.run("", cast(Any, environment), context))

    assert environment.uploads == [
        ("trajectory.json", "/logs/agent/trajectory.json"),
        ("openhands.trajectory.json", "/logs/agent/openhands.trajectory.json"),
        ("contextbench-model.patch", "/tmp/contextbench-replay.patch"),
    ]
    assert environment.commands == [
        (
            "git apply --binary --whitespace=nowarn /tmp/contextbench-replay.patch "
            "&& rm -f /tmp/contextbench-replay.patch"
        )
    ]
    assert context.metadata is not None
    assert context.metadata["replay_source_trial"] == str(trial)


def _openhands_read(view_range: list[int]) -> list[dict[str, Any]]:
    """A native OpenHands file-editor view: the action and its observation."""
    path = f"{WORKSPACE}/src/example.py"
    call = {"command": "view", "path": path, "view_range": view_range}
    metadata = {
        "function_name": "str_replace_editor",
        "tool_call_id": "call-1",
        "model_response": {
            "id": "response-1",
            "choices": [
                {
                    "message": {
                        "content": "",
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "str_replace_editor",
                                    "arguments": json.dumps(call),
                                },
                            }
                        ],
                    }
                }
            ],
        },
        "total_calls_in_response": 1,
    }
    start, end = view_range
    return [
        {
            "id": 1,
            "timestamp": "2026-01-01T00:00:00",
            "source": "agent",
            "message": f"Reading file: {path}",
            "action": "read",
            "tool_call_metadata": metadata,
            "args": {"path": path, "start": 0, "end": -1, "view_range": view_range},
        },
        {
            "id": 2,
            "timestamp": "2026-01-01T00:00:01",
            "source": "agent",
            "message": f"I read the file {path}.",
            "cause": 1,
            "observation": "read",
            "tool_call_metadata": metadata,
            "content": "".join(
                f"{number:6d}\tline_{number} = {number}\n"
                for number in range(start, end + 1)
            ),
            "extras": {"path": path},
        },
    ]


def _prepared_task(work: Path, commit: str) -> Path:
    """A prepared task's verifier inputs, as the adapter and `prepare.py` write them."""
    tests = work / "prepared/harbor-tasks" / DIRECTORY / "tests"
    package = tests / "harbor_contextbench"
    for relative in _VERIFIER_MODULES:
        (package / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PACKAGE_DIR / relative, package / relative)
    (package / "__init__.py").write_text('"""Generated."""\n')
    for name in ("score.py", "test.sh"):
        shutil.copy2(PACKAGE_DIR / "task-template/tests" / name, tests / name)
    write_json(
        tests / "gold.json",
        {
            "instance_id": TASK_ID,
            "base_commit": commit,
            "repository": "owner/repo",
            "contextbench_commit": "pinned",
            "gold_context": [
                {"file": "src/example.py", "start_line": 2, "end_line": 5}
            ],
        },
    )
    write_json(
        tests / "attribution.json", {"repository_roots": [WORKSPACE, "/testbed"]}
    )
    write_json(
        work / "prepared/task-map.json",
        {
            TASK_ID: {
                "task_name": f"contextbench/{DIRECTORY}",
                "directory": DIRECTORY,
                "repository": "owner/repo",
                "base_commit": commit,
                "workspace": WORKSPACE,
                "swebench_instance_id": "owner__repo-1",
                "contextbench_instance_id": TASK_ID,
            }
        },
    )
    return tests


def _retained_runs(retained: Path, work: Path, runs: int) -> None:
    """Three retained runs in the bundle layout, and their finished replays."""
    contract = {"runtime_contract_sha256": runtime_digest(load_json(CONFIG_PATH))}
    rewards: dict[str, float] = {"contextbench_file_coverage": 0.5}
    for granularity in GRANULARITIES:
        rewards |= {
            f"contextbench_final_{granularity}_intersection": 1.0,
            f"contextbench_final_{granularity}_gold_size": 2.0,
            f"contextbench_final_{granularity}_pred_size": 4.0,
        }
    for number in range(1, runs + 1):
        job = retained / "harbor_parity" / f"run{number}"
        _retained_trial(job, f"contextbench-{KEY}__run{number}")
        write_json(job / "score.json", contract)
        native = retained / "original_parity" / f"run{number}"
        native.mkdir(parents=True)
        row = {"instance_id": "owner__repo-1", "history": _openhands_read([2, 3])}
        (native / "output.jsonl").write_text(json.dumps(row) + "\n")
        write_json(native / "score.json", contract)

        replay = work / "rescore/jobs" / f"contextbench-rescore-{number:02d}"
        write_json(
            replay / "result.json",
            {
                "finished_at": "2026-01-01T00:00:00",
                "stats": {"n_completed_trials": 1, "n_errored_trials": 0},
            },
        )
        write_json(
            replay / f"{DIRECTORY}__replay/result.json",
            {
                "task_name": f"contextbench/{DIRECTORY}",
                "exception_info": None,
                "verifier_result": {"rewards": rewards},
            },
        )


def test_retained_runs_are_found_in_a_work_directory_or_the_bundle(
    tmp_path: Path,
) -> None:
    work = tmp_path / "work"
    (work / "harbor/run-02/jobs/contextbench-parity-02").mkdir(parents=True)
    bundle = tmp_path / "bundle"
    (bundle / "harbor_parity/run2").mkdir(parents=True)

    from_work = retained_run(work, 2)
    from_bundle = retained_run(bundle, 2)

    assert from_work.harbor_job == work / "harbor/run-02/jobs/contextbench-parity-02"
    assert from_work.harbor_record == work / "harbor/run-02/score.json"
    assert from_work.native_output == work / "original/run-02/raw/output.jsonl"
    assert from_work.native_record == work / "original/run-02/score.json"
    assert from_bundle.harbor_job == bundle / "harbor_parity/run2"
    assert from_bundle.harbor_record == bundle / "harbor_parity/run2/score.json"
    assert from_bundle.native_output == bundle / "original_parity/run2/output.jsonl"
    assert from_bundle.native_record == bundle / "original_parity/run2/score.json"


def test_rescore_scores_every_harness_and_extractor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without Docker: finished replay jobs stand in for Harbor's verifier runs."""
    monkeypatch.setenv("CONTEXTBENCH_TMP_ROOT", str(tmp_path / "unused"))
    work = tmp_path / "work"
    commit = commit_files(
        work / "rescore/repositories/github.com__owner__repo",
        {"src/example.py": EXAMPLE, "src/other.py": "x = 1\n"},
    )
    tests = _prepared_task(work, commit)
    runs = load_json(CONFIG_PATH)["number_of_runs"]
    _retained_runs(tmp_path / "retained", work, runs)

    table = rescore(work, tmp_path / "retained")

    by_cell = {
        name: [run["file_coverage"] for run in cell["runs"]]
        for name, cell in table["cells"].items()
    }
    # Every extractor finds the gold file; the replay cell is the verifier's.
    assert by_cell == {
        "native_upstream": [1.0] * runs,
        "native_rule": [1.0] * runs,
        "harbor_upstream": [1.0] * runs,
        "harbor_rule": [0.5] * runs,
    }
    # Both extractors credit the viewed lines 2-3 of gold lines 2-5.
    assert [
        table["cells"][name]["runs"][0]["line_coverage"]
        for name in ("native_upstream", "native_rule", "harbor_upstream")
    ] == [0.5] * 3
    harbor = load_json(work / "rescore/harbor/run-01/score.json")
    assert harbor["method"] == "rescore"
    assert harbor["task_scores"] == {TASK_ID: 0.5}
    assert harbor["attribution_version"] == table["attribution_version"]
    assert harbor["harbor_version"] == "0.26.0"
    assert "src/contextbench/attribution/rules.py" in harbor["source_sha256"]
    assert set(harbor["retained_inputs_sha256"][TASK_ID]) == {
        "trajectory",
        "openhands_log",
        "model_patch",
    }
    # Native 1.0 against Harbor 0.5: the report runs, and finds no overlap.
    assert report(work / "rescore") == 1
    markdown = (work / "rescore/parity-report.md").read_text()
    assert "| ContextBench (rescored) | 1.000000 |" in markdown
    assert "| Harbor (rescored) | 0.500000 |" in markdown
    assert (
        "| ContextBench | 1.000000, 1.000000, 1.000000; 1.000000 ± 0.000000 |"
        in (work / "rescore/harness-extractor.md").read_text()
    )

    # A verifier prepared before an attribution change is refused.
    rules = tests / "harbor_contextbench/attribution/rules.py"
    rules.write_text(rules.read_text() + "# changed\n")
    with pytest.raises(ValueError, match="prepare the tasks again"):
        scorer_sources(work / "prepared/harbor-tasks")


def test_a_run_series_does_not_mix_rescored_and_run_records(tmp_path: Path) -> None:
    config = load_json(CONFIG_PATH)
    counts = {
        granularity: {"intersection": 1.0, "gold_size": 2.0, "pred_size": 2.0}
        for granularity in GRANULARITIES
    }
    for side in ("original", "harbor"):
        for number in range(1, config["number_of_runs"] + 1):
            fields: dict[str, Any] = (
                {} if (side, number) == ("harbor", 2) else {"method": "rescore"}
            )
            write_json(
                tmp_path / side / f"run-{number:02d}/score.json",
                score_record(side, number, {TASK_ID: counts}, config, **fields),
            )

    with pytest.raises(ValueError, match="invalid harbor run 2 score record"):
        report(tmp_path)
