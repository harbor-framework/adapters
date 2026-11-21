"""Self-check for build_oracle.py (run: python3 -I scripts/test_build_oracle.py).

Offline: fake Harbor trials (verifier/reward.txt + verifier/vita_runtime_state.json),
no API calls. Covers the two-round oracle flow from the README.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def trial(job: Path, name: str, task_id: str, reward: float, text: str, stamp: str) -> None:
    v = job / name / "verifier"
    v.mkdir(parents=True)
    v.joinpath("reward.txt").write_text(str(reward))
    v.joinpath("vita_runtime_state.json").write_text(json.dumps({
        "task_set": "delivery",
        "task_id": task_id,
        "termination_reason": "user_stop",
        # Live runs differ (fresh timestamps); a replay reproduces the stored messages.
        "messages": [{"role": "assistant", "content": text, "timestamp": stamp},
                     {"role": "user", "content": "thanks ###STOP###", "timestamp": stamp}],
    }))


def run(script: Path, *args: str) -> str:
    return subprocess.run([sys.executable, "-I", str(script), *map(str, args)],
                          capture_output=True, text=True, check=True).stdout


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "scripts").mkdir()
    script = d / "scripts" / "build_oracle.py"
    shutil.copy2(HERE / "build_oracle.py", script)
    staging, oracle = d / "staging", d / "oracle"

    # Live job: three independent passing trajectories for task 1, one for task 2.
    live = d / "jobs" / "live"
    trial(live, "t1a", "1", 1.0, "plan A", "10:00")
    trial(live, "t1b", "1", 1.0, "plan B", "10:05")
    trial(live, "t1c", "1", 1.0, "plan C", "10:09")
    trial(live, "t2a", "2", 1.0, "plan X", "11:00")

    # README pitfall: independent live runs never confirm each other.
    out = run(script, live, "--min-passes", "2", "--out", staging, "--dry-run")
    assert "Wrote 0 oracle" in out, out

    # Round 1: harvest one candidate per task into a staging dir (not oracle/).
    run(script, live, "--min-passes", "1", "--out", staging)
    assert sorted(p.name for p in (staging / "delivery").iterdir()) == ["1.json", "2.json"]
    assert not oracle.exists(), "round 1 must not touch the oracle dir"

    # Replay job: the staged task-1 trajectory passes again, task 2's fails.
    s1 = json.loads((staging / "delivery" / "1.json").read_text())
    replay = d / "jobs" / "replay"
    trial(replay, "r1", "1", 1.0, s1["messages"][0]["content"], s1["messages"][0]["timestamp"])
    trial(replay, "r2", "2", 0.0, "plan X", "11:00")

    # A stale candidate already sitting in oracle/ (e.g. from an earlier round).
    (oracle / "delivery").mkdir(parents=True)
    (oracle / "delivery" / "2.json").write_text("{}")

    # Round 2: only trajectories that passed twice (live + replay) land in a clean oracle/.
    out = run(script, live, replay, "--min-passes", "2", "--out", oracle, "--clean")
    got = sorted(p.name for p in (oracle / "delivery").iterdir())
    assert got == ["1.json"], f"oracle/ should hold only confirmed task 1, got {got}\n{out}"
    kept = json.loads((oracle / "delivery" / "1.json").read_text())
    assert kept["messages"] == s1["messages"], "must keep the replay-confirmed trajectory"

print("test_build_oracle: OK")
