"""Optional CPU contract checks against real pinned upstream data/scoring classes.

FIB_UPSTREAM=/path/to/pinned/repo; requires torch, safetensors, pydantic,
and docstring-parser. No CUDA execution or model calls.
"""

import importlib
import os
import subprocess
from pathlib import Path

import pytest

from flashinfer_bench.adapter import UPSTREAM_REVISION


@pytest.fixture(scope="module")
def upstream():
    location = os.environ.get("FIB_UPSTREAM")
    if not location:
        pytest.skip("set FIB_UPSTREAM to enable upstream CPU contract checks")
    root = Path(location)
    assert (
        subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        == UPSTREAM_REVISION
    )
    # Load the upstream data layer only, avoiding CUDA initialization in its top-level __init__.
    import flashinfer_bench

    flashinfer_bench.__path__.append(str(root / "flashinfer_bench"))
    return importlib.import_module("flashinfer_bench.data")


def test_native_scorer_failure_gate_and_equal_definition_weight(upstream):
    d = upstream

    def solution(name, definition, author):
        return d.Solution(
            name=name,
            definition=definition,
            author=author,
            spec=d.BuildSpec(
                language="python", target_hardware=["B200"], entry_point="main.py::run"
            ),
            sources=[d.SourceFile(path="main.py", content="def run(x): return x")],
        )

    def trace(name, definition, uuid, latency, failed=False):
        evaluation = d.Evaluation(
            status="COMPILE_ERROR" if failed else "PASSED",
            environment=d.Environment(hardware="CPU-contract-test"),
            timestamp="test",
            correctness=None if failed else d.Correctness(),
            performance=None if failed else d.Performance(latency_ms=latency),
        )
        return d.Trace(
            definition=definition,
            solution=name,
            workload=d.Workload(uuid=uuid, axes={}, inputs={}),
            evaluation=evaluation,
        )

    sols = {
        k: [solution(k + "base", k, "baseline"), solution(k + "agent", k, "agent")]
        for k in ("a", "b")
    }
    rows = {
        "a": [trace("abase", "a", "w1", 4), trace("aagent", "a", "w1", 1)],
        "b": [
            trace("bbase", "b", "w1", 2),
            trace("bagent", "b", "w1", 1),
            trace("bbase", "b", "w2", 2),
            trace("bagent", "b", "w2", 1),
        ],
    }
    ts = d.TraceSet(definitions={"a": None, "b": None}, solutions=sols, traces=rows)
    assert (
        ts.get_author_score("agent").avg_speedup == 3
    )  # (4 + 2)/2, not workload-weighted
    rows["a"].append(trace("aagent", "a", "w1", 0, failed=True))
    ts = d.TraceSet(definitions={"a": None, "b": None}, solutions=sols, traces=rows)
    assert ts.get_solution_score("aagent").avg_speedup == 0
    assert ts.get_author_score("agent").avg_speedup == 1
    from flashinfer_bench.aggregate import aggregate

    # A definition without a candidate is unscored, not an extra zero. Evaluated
    # failures above still participate in the mean.
    ts = d.TraceSet(
        definitions={"a": None, "b": None, "c": None}, solutions=sols, traces=rows
    )
    wrapped = aggregate(
        [
            {"reward": ts.get_solution_score(name).avg_speedup}
            for name in ("aagent", "bagent")
        ]
        + [None]
    )
    assert wrapped["avg_speedup"] == ts.get_author_score("agent").avg_speedup
    assert (
        wrapped["scored_definitions"] == ts.get_author_score("agent").definitions == 2
    )
    assert ts.get_solution_score("absent") is None


def test_generated_records_validate_upstream(upstream):
    output = os.environ.get("FIB_GENERATED")
    if not output:
        pytest.skip("set FIB_GENERATED to validate generated tasks")
    import json

    tasks = sorted(Path(output).glob("*/task.toml"))
    assert tasks, "FIB_GENERATED must contain generated tasks"
    scope = json.loads((Path(output) / "scope.json").read_text())
    assert len(tasks) == len(scope["selected"])
    for task in tasks:
        root = task.parent
        ts = upstream.TraceSet.from_path(str(root / "tests/data"))
        manifest = json.loads((root / "tests/manifest.json").read_text())
        assert list(ts.definitions) == [manifest["definition"]]
        assert len(ts.workloads[manifest["definition"]]) == len(
            manifest["workload_uuids"]
        )
        upstream.Solution.model_validate_json(
            (root / "tests/baseline.json").read_text()
        )
        upstream.Solution.model_validate_json(
            (root / "solution/solution.json").read_text()
        )


@pytest.mark.parametrize(
    "mode,expected,error",
    [
        ("pass", 2.0, None),
        ("candidate-failure", 0.0, None),
        ("baseline-partial-failure", 2.0, None),
        ("baseline-all-failure", None, "No finite comparable"),
        ("missing", None, "Incomplete"),
        ("no-submission", None, "solution.json"),
        ("malformed", None, "Invalid JSON"),
        ("impersonation", None, "must not impersonate"),
        ("wrong-definition", None, "must target definition 'rmsnorm_h128'"),
        ("benchmark-crash", None, "benchmark crashed"),
    ],
)
def test_verifier_main_with_real_scorer_and_scripted_traces(
    upstream, monkeypatch, tmp_path, mode, expected, error
):
    """Exercise the adapter handoff/writer; GPU execution is deliberately replaced."""
    import json
    import shutil
    import sys
    from types import SimpleNamespace

    import flashinfer_bench

    output = os.environ.get("FIB_GENERATED")
    if not output:
        pytest.skip("set FIB_GENERATED for verifier handoff check")
    source = Path(output) / "rmsnorm-h128"
    if not source.is_dir():
        pytest.skip("generate rmsnorm_h128 for verifier handoff check")
    runtime = Path(__file__).parents[1] / "src/flashinfer_bench/runtime"
    monkeypatch.syspath_prepend(str(runtime))
    import evaluate

    task = tmp_path / "tests"
    shutil.copytree(source / "tests", task)
    candidate_path = tmp_path / "solution.json"
    if mode != "no-submission":
        shutil.copyfile(source / "solution/solution.json", candidate_path)
    if mode == "malformed":
        candidate_path.write_text("not JSON")
    elif mode in {"impersonation", "wrong-definition"}:
        candidate = json.loads(candidate_path.read_text())
        candidate["author" if mode == "impersonation" else "definition"] = (
            "baseline" if mode == "impersonation" else "wrong"
        )
        candidate_path.write_text(json.dumps(candidate))
    manifest = json.loads((task / "manifest.json").read_text())
    calls = []

    class Benchmark:
        def __init__(self, data, config):
            assert not data.traces
            self.data = data
            calls.append(self)

        def close(self):
            self.closed = True

        def run_all(self, dump_traces):
            assert dump_traces is False
            if mode == "benchmark-crash":
                raise RuntimeError("benchmark crashed")
            definition = manifest["definition"]
            rows = []
            for solution in self.data.solutions[definition]:
                baseline = solution.author == "baseline"
                for idx, workload in enumerate(self.data.workloads[definition]):
                    if mode == "missing" and not baseline and idx == 0:
                        continue
                    failed = mode == "candidate-failure" and not baseline and idx == 0
                    failed |= baseline and (
                        mode == "baseline-all-failure"
                        or (mode == "baseline-partial-failure" and idx == 0)
                    )
                    ev = upstream.Evaluation(
                        status="COMPILE_ERROR" if failed else "PASSED",
                        environment=upstream.Environment(hardware="scripted-test"),
                        timestamp="test",
                        correctness=None if failed else upstream.Correctness(),
                        performance=None
                        if failed
                        else upstream.Performance(latency_ms=4 if baseline else 2),
                    )
                    rows.append(
                        upstream.Trace(
                            definition=definition,
                            solution=solution.name,
                            workload=workload.workload,
                            evaluation=ev,
                        )
                    )
            return upstream.TraceSet(
                definitions=self.data.definitions,
                solutions=self.data.solutions,
                traces={definition: rows},
            )

    monkeypatch.setattr(flashinfer_bench, "Benchmark", Benchmark, raising=False)
    config = SimpleNamespace(model_dump_json=lambda **kw: "{}")
    monkeypatch.setattr(
        flashinfer_bench,
        "BenchmarkConfig",
        SimpleNamespace(default=lambda: config),
        raising=False,
    )
    monkeypatch.setattr(flashinfer_bench, "Solution", upstream.Solution, raising=False)
    monkeypatch.setattr(flashinfer_bench, "TraceSet", upstream.TraceSet, raising=False)
    monkeypatch.setattr(evaluate, "check_gpu", lambda target: None)
    logs = tmp_path / "logs"
    logs.mkdir()
    # Stale rewards must not survive a new attempt.
    for name in ("reward.txt", "reward.json", "score.json"):
        (logs / name).write_text("999")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate.py",
            "--task",
            str(task),
            "--solution",
            str(candidate_path),
            "--output",
            str(logs),
        ],
    )
    if expected is None:
        with pytest.raises((RuntimeError, ValueError, FileNotFoundError), match=error):
            evaluate.main()
        assert not (logs / "reward.txt").exists()
        assert not (logs / "score.json").exists()
    else:
        evaluate.main()
        assert float((logs / "reward.txt").read_text()) == expected
        score = json.loads((logs / "score.json").read_text())
        assert score["workloads"] == len(manifest["workload_uuids"]) - (
            mode == "baseline-partial-failure"
        )
    assert not (logs / "reward.json").exists()
    if calls:
        assert calls[0].closed
        assert (logs / "traces.jsonl").exists() == (mode != "benchmark-crash")
