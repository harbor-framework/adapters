"""Write the verifier's outcome: reward.json for a judged trial, ungraded.json otherwise.

A trial gets a reward only if the integrity judge returned two valid verdicts. Without them the
measurement is kept in ungraded.json, which Harbor does not read, so the trial has no reward.
test.sh puts the verifier's copy of upstream's evaluator, /tests/ib, on PYTHONPATH.
"""

import json
import math
import sys
from pathlib import Path

from src.eval.inference.hpo_search_baselines import (
    FAILURE_SCORE,
    SCENARIO_TO_SHORT,
    primary_metric,
)

# PyTorch baseline in the units of primary_metric, from Table 12 of the paper: 840 ms TTFT,
# 41 ms TPOT, 0.132 req/s, and 1.68 for the scenario D score. These constants reproduce the
# paper's Table 2 from its Table 12.
PYTORCH_BASELINE = {"a": 1 / 0.840, "b": 1 / 0.041, "c": 0.132, "d": 1.68}
VERDICTS = {
    "contamination_detected": (
        "contamination_judgement.txt",
        "contamination detected",
        "no contamination detected",
    ),
    "disallowed_use_detected": (
        "disallowed_model_judgement.txt",
        "disallowed use detected",
        "only allowed use detected",
    ),
}
# Why test.sh has no valid verdict: the judge was off for a diagnostic run, the run had no
# judge credential, or the judge could not run or failed.
UNGRADED_STATES = ("off", "no_credential", "failed")
# The final evaluation's status when test.sh skipped it.
NOT_RUN = "not_run"


def read_verdict(path: Path, flagged: str, clean: str) -> bool | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return None
    return lines == [flagged] if lines in ([flagged], [clean]) else None


def measurement(logs: Path, scenario: str, eval_rc: str) -> dict[str, float]:
    """Return the evaluation's gates and the speedup over the PyTorch baseline."""
    try:
        metrics = json.loads((logs / "metrics.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        metrics = {}
    metrics = metrics if isinstance(metrics, dict) else {}

    def check(name: str) -> bool:
        return isinstance(metrics.get(name), dict) and metrics[name].get("pass") is True

    gates = {
        "eval_valid": eval_rc == "0",
        "speed_pass": check("speed_check"),
        "quality_pass": check("quality_check"),
    }
    primary = 0.0
    if all(gates.values()) and metrics.get("score") != 0:
        value = primary_metric(metrics, scenario)[0]
        primary = value if math.isfinite(value) and value > FAILURE_SCORE else 0.0
    return {
        "speedup": primary / PYTORCH_BASELINE[SCENARIO_TO_SHORT[scenario]],
        "primary_metric": primary,
        **{key: int(value) for key, value in gates.items()},
    }


def rewards_for(logs: Path, scenario: str, eval_rc: str) -> dict[str, float]:
    """Return the reward keys of a trial whose judge returned two valid verdicts."""
    verdicts = {
        key: read_verdict(logs / name, flagged, clean)
        for key, (name, flagged, clean) in VERDICTS.items()
    }
    if None in verdicts.values():
        raise SystemExit("the judge's verdict files are missing or invalid")
    measured = measurement(logs, scenario, eval_rc)
    # A run that fails a gate, ships no working server, or is flagged by the judge is worth
    # the PyTorch baseline (1x), as in the paper's Table 2.
    valid = measured["primary_metric"] > 0 and not any(verdicts.values())
    return {
        "reward": measured["speedup"] if valid else 1.0,
        "valid": int(valid),
        **measured,
        "judge_valid": 1,
        **{key: int(value) for key, value in verdicts.items()},
    }


def ungraded_for(logs: Path, scenario: str, eval_rc: str, judge: str, note: str) -> dict:
    """Return the record of a trial without a valid judge verdict. It has no reward key."""
    record = {"status": "ungraded", "judge": judge, "reason": note, "judge_valid": 0}
    if eval_rc == NOT_RUN:
        return {**record, "evaluated": 0}
    measured = measurement(logs, scenario, eval_rc)
    return {**record, "evaluated": 1, "gates_passed": int(measured["primary_metric"] > 0), **measured}


def main() -> None:
    logs, scenario, eval_rc, judge = Path(sys.argv[1]), *sys.argv[2:5]
    note = sys.argv[5] if len(sys.argv) > 5 else ""
    for name in ("reward.json", "reward.txt", "ungraded.json"):
        (logs / name).unlink(missing_ok=True)
    if judge == "valid" and eval_rc == NOT_RUN:
        raise SystemExit("a judged trial was not evaluated")
    if judge == "valid":
        name, outcome = "reward.json", rewards_for(logs, scenario, eval_rc)
    elif judge in UNGRADED_STATES:
        name, outcome = "ungraded.json", ungraded_for(logs, scenario, eval_rc, judge, note)
    else:
        raise SystemExit(f"unknown judge state: {judge!r}")
    (logs / name).write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
    print(f"{name}: {json.dumps(outcome)}")


if __name__ == "__main__":
    main()
