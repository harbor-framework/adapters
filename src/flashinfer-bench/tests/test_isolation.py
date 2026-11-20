"""Security acceptance checks; known upstream violations remain strict xfails."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def probe():
    upstream = os.environ.get("FIB_UPSTREAM")
    generated = os.environ.get("FIB_GENERATED")
    if not upstream or not generated:
        pytest.skip("set FIB_UPSTREAM and FIB_GENERATED for the isolation probe")
    definition = (
        Path(generated)
        / "rmsnorm-h128/tests/data/definitions/rmsnorm/rmsnorm_h128.json"
    )
    if not definition.is_file():
        pytest.skip("generate rmsnorm_h128 for the isolation probe")
    run = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "probes/grading_isolation.py"),
            "--upstream",
            upstream,
            "--definition",
            str(definition),
        ],
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    return json.loads(run.stdout)


def test_isolation_probe_controls(probe):
    assert probe["cases"]["correct"] == {
        "status": "PASSED",
        "latency_ms": probe["timing_sentinel_ms"],
    }
    assert probe["cases"]["wrong"] == {
        "status": "INCORRECT_NUMERICAL",
        "latency_ms": None,
    }
    assert probe["gpu_timing_exercised"] is False


def test_separate_checker_rejects_wrong_output_after_worker_tampering(probe):
    assert probe["separate_checker_status"] == "INCORRECT_NUMERICAL"


@pytest.mark.xfail(
    strict=True, reason="Pinned upstream imports candidate inside its checker"
)
def test_candidate_cannot_replace_correctness_checker(probe):
    assert probe["cases"]["checker_tamper"]["status"] == "INCORRECT_NUMERICAL"


@pytest.mark.xfail(
    strict=True, reason="Pinned upstream accepts candidate-mutable timing"
)
def test_candidate_cannot_replace_timer(probe):
    assert probe["cases"]["timer_tamper"]["latency_ms"] == probe["timing_sentinel_ms"]
