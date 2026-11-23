"""Map an SREGym conductor result row to Harbor rewards.

Field semantics follow SREGym's own reporting (sregym/results/report.py):
``Diagnosis.success`` is the LLM-judge verdict on the diagnosis submission,
``Mitigation.success`` the problem's mitigation oracle, and an attempt passes
overall only if both pass. A stage the agent never submitted counts as failed.

Infrastructure failures (the app never deployed, the fault never injected, or
the bridge lost the campaign) raise an error instead of scoring 0. That way
Harbor records them as errored trials, not as agent failures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


AGENT_CAUSED_INCOMPLETE = {"agent_exited_before_all_stages_completed", "agent_timeout"}


def as_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def main() -> int:
    result_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    if not result_path.is_file():
        print("no result from the SREGym sidecar", file=sys.stderr)
        return 2
    payload = json.loads(result_path.read_text())
    if payload.get("phase") not in {"done", "scored"}:
        print(f"SREGym attempt did not finish (phase={payload.get('phase')})", file=sys.stderr)
        return 2
    row = payload.get("results")
    if not row:
        print(f"SREGym produced no result row: {payload.get('error')}", file=sys.stderr)
        return 2
    if as_bool(row.get("deploy_failed")) or as_bool(row.get("fault_injection_failed")):
        print(f"SREGym infrastructure failure: {json.dumps(row)[:2000]}", file=sys.stderr)
        return 2

    # Incomplete attempts: a stage the agent never submitted (it exited or ran
    # out of time) is a genuine failure and scores 0. Anything else that left
    # a stage unscored (evaluation timeout or failure, cleanup problems) is an
    # infrastructure error, as sregym/results/report.py treats it.
    reason = row.get("incomplete_reason") or ""
    if row.get("run_status") == "incomplete" and reason not in AGENT_CAUSED_INCOMPLETE:
        print(f"SREGym attempt incomplete for a non-agent reason: {reason}", file=sys.stderr)
        return 2
    if row.get("unscored_stages"):
        print(f"SREGym left stages unscored: {row.get('unscored_stages')}", file=sys.stderr)
        return 2

    diagnosis = as_bool(row.get("Diagnosis.success"))
    mitigation = as_bool(row.get("Mitigation.success"))
    if mitigation is None and "Mitigation.success" in row:
        print("mitigation oracle returned no verdict", file=sys.stderr)
        return 2
    if diagnosis is None and "Diagnosis.success" in row:
        print("diagnosis judge returned no verdict", file=sys.stderr)
        return 2
    rewards = {"mitigation": float(bool(mitigation))}
    # Report diagnosis only when the stage ran (a debug SREGYM_STAGES run may skip it).
    if "Diagnosis.success" in row or reason in AGENT_CAUSED_INCOMPLETE:
        rewards["diagnosis"] = float(bool(diagnosis))
        rewards["overall"] = float(bool(diagnosis) and bool(mitigation))
    # Primary reward: mitigation success. This is pending confirmation with
    # the Harbor team (see README Notes).
    rewards["reward"] = rewards["mitigation"]
    (out_dir / "reward.json").write_text(json.dumps(rewards))
    print(json.dumps({"rewards": rewards, "run_status": row.get("run_status"),
                      "incomplete_reason": row.get("incomplete_reason")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
