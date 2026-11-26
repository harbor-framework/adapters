"""Re-grade a Harbor parity job's saved answers with the adapter's own grade.py.

The agent phase is not re-run. For every trial, ``agent/answer.txt`` (the exact
file the wrapper uploaded to ``/workspace/answer.txt``) is graded by the same
``tests/grade.py`` the verifier runs, with the judge settings taken from the
current environment (``DSQA_JUDGE_*``, ``OPENAI_*``). Output goes to
``<trial>/verifier_regrade/`` next to the original ``verifier/``.

Why: judge settings must be identical for every graded answer. If they change
after a run (e.g. ``DSQA_JUDGE_MAX_TOKENS``), the whole run is re-graded.

Which trials are graded:

* normal trials and verifier failures (timeout, no reward written): the saved
  answer is graded;
* agent timeouts (``AgentTimeoutError``): no answer was produced, so the trial
  is graded as an empty answer (F1 = 0), as the verifier does;
* other agent exceptions (no trajectory: worker crash or pipeline error):
  excluded, reported as infrastructure failures.

Usage::

    python -m deepsearchqa.parity.regrade_harbor <job_dir> [--concurrency 8]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Verifier-side failures (judge timeout / no reward written) still have a valid
# agent answer, so they are re-graded rather than excluded.
SCORED_EXCEPTIONS = {None, "AgentTimeoutError", "VerifierTimeoutError", "RewardFileNotFoundError"}


def _task_dir(trial: Path) -> Path:
    cfg = json.loads((trial / "config.json").read_text(encoding="utf-8"))
    task = cfg.get("task", {})
    return Path(task.get("path") if isinstance(task, dict) else task)


def regrade_trial(trial: Path) -> dict:
    result = json.loads((trial / "result.json").read_text(encoding="utf-8"))
    exc = (result.get("exception_info") or {}).get("exception_type")
    name = trial.name.split("__")[0]
    if exc not in SCORED_EXCEPTIONS:
        return {"task": name, "trial": trial.name, "f1": None, "excluded": exc}

    task_dir = _task_dir(trial)
    out_dir = trial / "verifier_regrade"
    out_dir.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "DSQA_GROUND_TRUTH": str(task_dir / "tests" / "ground_truth.json"),
        "DSQA_ANSWER_PATH": str(trial / "agent" / "answer.txt"),
        "DSQA_LOG_DIR": str(out_dir),
        "JUDGE_MODEL": os.environ.get("DSQA_JUDGE_MODEL", "gemini-2.5-flash"),
    }
    proc = subprocess.run(
        [sys.executable, str(task_dir / "tests" / "grade.py")],
        env=env, capture_output=True, text=True,
    )
    (out_dir / "test-stdout.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    reward = out_dir / "reward.json"
    if proc.returncode != 0 or not reward.exists():
        return {"task": name, "trial": trial.name, "f1": None, "excluded": "judge_error"}
    details = json.loads((out_dir / "grading_details.json").read_text(encoding="utf-8"))
    rewards = json.loads(reward.read_text(encoding="utf-8"))
    return {"task": name, "trial": trial.name, "f1": rewards["f1"],
            "fully_correct": rewards["fully_correct"], "source": details["source"],
            "agent_exception": exc, "judge_params": details.get("judge_params"),
            "judge_model": details.get("judge_model")}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("job_dir", type=Path)
    p.add_argument("--concurrency", type=int, default=8)
    args = p.parse_args()

    trials = sorted(t for t in args.job_dir.iterdir()
                    if t.is_dir() and (t / "result.json").exists() and (t / "config.json").exists())
    with ThreadPoolExecutor(args.concurrency) as ex:
        rows = list(ex.map(regrade_trial, trials))
    scored = [r for r in rows if r["f1"] is not None]
    summary = {
        "job_dir": str(args.job_dir),
        "n_trials": len(rows),
        "n_scored": len(scored),
        "excluded": {r["task"]: r["excluded"] for r in rows if r["f1"] is None},
        "mean_f1": statistics.fmean(r["f1"] for r in scored) if scored else None,
        "fully_correct_rate": statistics.fmean(r["fully_correct"] for r in scored) if scored else None,
        "judge_model": os.environ.get("DSQA_JUDGE_MODEL"),
        "judge_params": next((r["judge_params"] for r in scored if r.get("judge_params") is not None), None),
        "trials": rows,
    }
    (args.job_dir / "regrade_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "trials"}, indent=2))


if __name__ == "__main__":
    main()
