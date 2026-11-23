"""Unit tests for adapter.py's generation flow.

Covers the behaviors a batch generation run depends on:
- atomic task rendering: a mid-render failure leaves NO partially-written
  task directory behind (every later non---overwrite run would silently
  skip one as "already exists"), and stale render-temp dirs from an
  interrupted earlier run are cleaned up on the next run;
- --task-ids normalization (zero-padded ids match) and a warning when a
  requested id matches nothing;
- the generated runbook's coverage note, including the narrowed-snapshot
  case where a --task-ids run must not claim whole-corpus coverage.

Runnable standalone:
    python3 src/itbench-aa/tests/test_adapter.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ADAPTER_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ADAPTER_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from itbench_aa import adapter as adapter_module
from itbench_aa.adapter import ITBenchAAAdapter
from itbench_aa.runbook import _runbook_text
from itbench_aa.scenarios import _enumerate_items

_VALID_GT = """
groups:
  - id: pod-a-1
    kind: Pod
    namespace: otel-demo
    filter:
      - pod-a-.*
    root_cause: true
"""


def _make_dataset(root: Path, numbers: tuple[int, ...] = (1,)) -> Path:
    """A local --dataset-path-style tree of valid Scenario-N/ dirs."""
    for n in numbers:
        scenario_dir = root / f"Scenario-{n}"
        (scenario_dir / "alerts").mkdir(parents=True)
        (scenario_dir / "alerts" / "a.json").write_text("[]")
        (scenario_dir / "metrics").mkdir()
        (scenario_dir / "metrics" / "m.tsv").write_text("m\n")
        for sub in (
            "k8s_events_raw.tsv",
            "k8s_objects_raw.tsv",
            "otel_logs_raw.tsv",
            "otel_traces_raw.tsv",
        ):
            (scenario_dir / sub).write_text("x\n")
        (scenario_dir / "ground_truth.yaml").write_text(_VALID_GT)
    return root


def _item(dataset: Path, number: int = 1):
    items = {it.task_id: it for it in _enumerate_items(dataset)}
    return items[f"scenario-{number}"]


# ---------------------------------------------------------------------------
# Atomic rendering
# ---------------------------------------------------------------------------


def test_render_failure_leaves_no_partial_task():
    """A failure after the template copytree (here: staging blows up) must
    not leave a half-built task dir that a later run would skip as
    'already exists', nor a lingering render-temp dir."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dataset = _make_dataset(root)
        item = _item(dataset)
        out = root / "out"
        adapter = ITBenchAAAdapter(out, dataset_path=dataset)

        def boom(task_dir, item):
            raise RuntimeError("staging exploded")

        original = adapter_module.stage_input_data
        adapter_module.stage_input_data = boom
        try:
            adapter._render_task(out / item.task_id, item)
        except RuntimeError as e:
            assert "staging exploded" in str(e)
        else:
            raise AssertionError("expected the render failure to propagate")
        finally:
            adapter_module.stage_input_data = original

        assert not (out / item.task_id).exists()
        assert list(out.glob(".scenario-*.render-*")) == []


def test_run_generates_tasks_and_cleans_stale_render_temps():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dataset = _make_dataset(root)
        out = root / "out"
        # a render-temp dir abandoned by an interrupted earlier run
        stale = out / ".scenario-1.render-abandoned"
        stale.mkdir(parents=True)
        (stale / "junk").write_text("x")

        adapter = ITBenchAAAdapter(out, dataset_path=dataset)
        adapter.run()

        assert (out / "scenario-1" / "task.toml").is_file()
        assert (out / "scenario-1" / "tests" / "ground_truth.yaml").is_file()
        assert (out / "scenario-1" / "environment" / "workspace").is_dir()
        assert not stale.exists()
        # no temp dirs left beside the tasks
        assert list(out.glob(".scenario-*.render-*")) == []
        # re-run without --overwrite skips, not re-renders
        adapter.run()


def test_second_run_after_failure_renders_the_task():
    """The recovery path the atomic render exists for: after a failed
    render, a plain re-run (no --overwrite) must render the task instead
    of skipping a half-built directory."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dataset = _make_dataset(root)
        out = root / "out"

        def boom(task_dir, item):
            raise RuntimeError("staging exploded")

        original = adapter_module.stage_input_data
        adapter_module.stage_input_data = boom
        try:
            ITBenchAAAdapter(out, dataset_path=dataset).run()
        except RuntimeError:
            pass
        finally:
            adapter_module.stage_input_data = original

        assert not (out / "scenario-1").exists()
        ITBenchAAAdapter(out, dataset_path=dataset).run()
        assert (out / "scenario-1" / "task.toml").is_file()


# ---------------------------------------------------------------------------
# --task-ids normalization + warnings
# ---------------------------------------------------------------------------


def test_task_ids_zero_padded_request_matches():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dataset = _make_dataset(root, numbers=(1, 2))
        out = root / "out"
        adapter = ITBenchAAAdapter(out, dataset_path=dataset, task_ids=["scenario-001"])
        adapter.run()
        assert (out / "scenario-1" / "task.toml").is_file()
        assert not (out / "scenario-2").exists()


def test_task_ids_matching_nothing_warns():
    with tempfile.TemporaryDirectory() as td:
        import contextlib
        import io

        root = Path(td)
        dataset = _make_dataset(root)
        out = root / "out"
        adapter = ITBenchAAAdapter(out, dataset_path=dataset, task_ids=["scenario-99"])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            adapter.run()
        assert "scenario-99" in stderr.getvalue()
        assert "matched no valid scenario" in stderr.getvalue()
        assert not (out / "scenario-99").exists()


# ---------------------------------------------------------------------------
# Runbook coverage note
# ---------------------------------------------------------------------------


def test_runbook_full_coverage_note():
    text = _runbook_text(
        Path("/snap/x"), total_valid_scenarios=40, existing_task_count=40
    )
    assert "All 40 valid scenario(s)" in text
    assert "not whole-corpus coverage" not in text


def test_runbook_partial_coverage_note():
    text = _runbook_text(
        Path("/snap/x"), total_valid_scenarios=40, existing_task_count=5
    )
    assert "5 of 40 valid scenario(s)" in text


def test_runbook_narrowed_snapshot_note():
    """A --task-ids-narrowed HF fetch must not present its subset count as
    whole-corpus coverage, however many tasks already exist."""
    text = _runbook_text(
        Path("/snap/x"),
        total_valid_scenarios=1,
        existing_task_count=40,
        snapshot_narrowed=True,
    )
    assert "40 task(s) are currently present" in text
    assert "not whole-corpus coverage" in text
    assert "All 1 valid scenario(s)" not in text


def test_run_narrowed_fetch_writes_narrowed_note():
    """End-to-end: a --task-ids run whose dataset root came from the
    narrowed HF fetch (no --dataset-path) writes the narrowed note."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dataset = _make_dataset(root)
        out = root / "out"

        original = adapter_module.resolve_dataset_root
        adapter_module.resolve_dataset_root = lambda *a, **k: dataset
        try:
            ITBenchAAAdapter(out, task_ids=["scenario-1"]).run()
        finally:
            adapter_module.resolve_dataset_root = original

        readme = (out / "README.md").read_text()
        assert "not whole-corpus coverage" in readme
        assert "All 1 valid scenario(s)" not in readme


_TESTS = [
    test_render_failure_leaves_no_partial_task,
    test_run_generates_tasks_and_cleans_stale_render_temps,
    test_second_run_after_failure_renders_the_task,
    test_task_ids_zero_padded_request_matches,
    test_task_ids_matching_nothing_warns,
    test_runbook_full_coverage_note,
    test_runbook_partial_coverage_note,
    test_runbook_narrowed_snapshot_note,
    test_run_narrowed_fetch_writes_narrowed_note,
]


def main() -> int:
    failures = 0
    for test in _TESTS:
        try:
            test()
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failures += 1
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: {test.__name__}: {e!r}")
            failures += 1
        else:
            print(f"PASS: {test.__name__}")
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
