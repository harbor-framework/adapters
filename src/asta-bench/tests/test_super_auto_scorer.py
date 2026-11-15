"""Controls for the SUPER-Auto verifier (asta_bench/benchmarks/super_auto.py).

The verifier re-runs the submitted command for a 15 s window and applies
upstream's `evaluate_entrypoints` rule to what it observes.  These tests run
the generated scorer against small synthetic "repositories".  The passing
cases take the full window (~15 s each).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from asta_bench.benchmarks import super_auto
from asta_bench.benchmarks.base import VERIFIER_TEST_SH
from test_verifier_contract import Sandbox

ENTRYPOINT = "scripts/train.py"

LONG_RUNNING = "import time\nprint('training...', flush=True)\ntime.sleep(60)\n"
QUICK = "print('done')\n"
CRASH_LATE = (
    "import time\nprint('start', flush=True)\ntime.sleep(3)\n"
    "raise RuntimeError('boom')\n"
)
# A wrapper that swallows a child's failure and exits 0 (as some SUPER
# entrypoints do): only the printed Traceback reveals it.
CRASH_SWALLOWED = (
    "import time, traceback\n"
    "try:\n    raise ValueError('child failed')\n"
    "except Exception:\n    traceback.print_exc()\n"
    "time.sleep(60)\n"
)
ARGPARSE_ERROR = (
    "import sys, time\nprint('train.py: error: bad args', file=sys.stderr)\ntime.sleep(60)\n"
)


def _task(tmp_path: Path, script: str) -> tuple[Sandbox, Path]:
    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    (task / "tests" / "test.sh").write_text(VERIFIER_TEST_SH)
    (task / "tests" / "run_scorer.py").write_text(super_auto.RUN_SCORER_PY)
    (task / "tests" / "config.json").write_text(json.dumps({"entrypoint": ENTRYPOINT}))
    sb = Sandbox(task, tmp_path / "root")
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "train.py").write_text(script)
    return sb, repo


def _submit(sb: Sandbox, command: str, cwd: Path | str) -> None:
    sb.answer.write_text(json.dumps({"command": command, "cwd": str(cwd)}))


PY = sys.executable


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        (LONG_RUNNING, 1.0),
        (QUICK, 0.0),
        (CRASH_LATE, 0.0),
        (CRASH_SWALLOWED, 0.0),
        (ARGPARSE_ERROR, 0.0),
    ],
    ids=["runs-past-10s", "exits-early", "traceback", "swallowed-traceback", "argparse-error"],
)
def test_rerun_applies_upstream_rule(tmp_path: Path, script: str, expected: float) -> None:
    sb, repo = _task(tmp_path, script)
    sb.plant_reward("1")
    _submit(sb, f"{PY} scripts/train.py", repo)
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == expected, result.stderr


def test_python_dash_m_form_is_accepted(tmp_path: Path) -> None:
    sb, repo = _task(tmp_path, LONG_RUNNING)
    (repo / "scripts" / "__init__.py").write_text("")
    _submit(sb, f"{PY.replace('python3', 'python')} -m scripts.train", repo)
    if "python -m" not in json.loads(sb.answer.read_text())["command"]:
        pytest.skip("interpreter path does not end in `python`")
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == 1.0, result.stderr


@pytest.mark.parametrize(
    "answer",
    [
        json.dumps({"command": "python other.py", "cwd": "/"}),
        json.dumps({"command": "", "cwd": "/"}),
        json.dumps({"command": "python scripts/train.py", "cwd": "/no/such/dir"}),
        json.dumps({"command": "python scripts/train.py", "cwd": "relative/dir"}),
        json.dumps({"command": ["python", "scripts/train.py"], "cwd": "/"}),
        json.dumps({"cwd": "/"}),
        # The pre-fix exploit: a self-reported history is no longer evidence.
        json.dumps(
            {
                "submitted": 1,
                "history": [
                    {
                        "action": {"content": "python scripts/train.py", "type": "execute"},
                        "observation": "Run completed successfully.",
                        "execution_start_time": "2026-01-01T00:00:00",
                        "execution_end_time": "2026-01-01T00:00:11",
                    }
                ],
            }
        ),
        "not json",
        "[1, 2]",
    ],
    ids=[
        "wrong-script", "empty-command", "missing-cwd", "relative-cwd",
        "command-not-string", "no-command", "fabricated-history", "prose", "array",
    ],
)
def test_invalid_submissions_score_zero_without_running(tmp_path: Path, answer: str) -> None:
    sb, _ = _task(tmp_path, LONG_RUNNING)
    sb.plant_reward("1")
    sb.answer.write_text(answer)
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == 0.0, result.stderr


def test_missing_answer_scores_zero(tmp_path: Path) -> None:
    sb, _ = _task(tmp_path, LONG_RUNNING)
    sb.plant_reward("1")
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == 0.0


def test_broken_config_records_no_reward(tmp_path: Path) -> None:
    sb, repo = _task(tmp_path, LONG_RUNNING)
    sb.plant_reward("1")
    _submit(sb, f"{PY} scripts/train.py", repo)
    (sb.root / "tests" / "config.json").write_text("{ not json")
    result = sb.verify()
    assert result.returncode != 0
    assert sb.reward() is None


def test_reference_solutions_and_exclusions_are_well_formed():
    """Every shipped Auto solution loads, and none is also listed as excluded."""
    from asta_bench.benchmarks import super_auto

    excluded = super_auto.load_excluded()
    assert all(isinstance(v, str) and v.strip() for v in excluded.values())
    solved = sorted(p.name for p in super_auto.SOLUTIONS_DIR.iterdir() if p.is_dir())
    assert solved, "no reference solutions shipped"
    assert not set(solved) & set(excluded)
    assert len(solved) + len(excluded) == super_auto.AUTO_SAMPLE_LIMIT
    for task_id in solved:
        solve_sh, answer = super_auto.load_solution(task_id)
        assert solve_sh.startswith("#!"), task_id
        assert "set -euo pipefail" in solve_sh, task_id
        assert "/workspace/venv" in solve_sh, task_id
        assert "SUPER_AUTO_ANSWER_EOF" not in solve_sh, task_id
