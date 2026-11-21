"""Self-check for aggregate.py (run: python3 -I parity/test_aggregate.py)."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def harbor_trial(job: Path, name: str, task_dir: str, run: int, reward: float | None, exc: bool = False) -> None:
    t = job / name
    (t / "verifier").mkdir(parents=True)
    (t / "config.json").write_text(json.dumps(
        {"task": {"path": f"/x/{task_dir}"}, "agent": {"kwargs": {"vita_trial_index": run}}}))
    (t / "result.json").write_text(json.dumps(
        {"exception_info": {"exception_type": "NonZeroAgentExitCodeError"} if exc else None}))
    if reward is not None:
        (t / "verifier" / "reward.txt").write_text(str(reward))


def run(args: list[str]) -> str:
    return subprocess.run([sys.executable, "-I", str(HERE / "aggregate.py"), *args],
                          capture_output=True, text=True, check=True).stdout


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    orig = d / "orig.json"
    sims = [{"task_id": tid, "trial": tr, "reward_info": {"reward": r}}
            for tr in (0, 1) for tid, r in (("A0812003", 1.0), ("10711002", 0.0))]
    orig.write_text(json.dumps({"simulations": sims}))
    job = d / "job"
    # Run 0 has both tasks; in run 1 the second task errored, and its leftover reward 0 must be ignored.
    harbor_trial(job, "a__0", "vita-cross-a0812003", 0, 1.0)
    harbor_trial(job, "b__0", "vita-delivery-10711002", 0, 0.0)
    harbor_trial(job, "a__1", "vita-cross-a0812003", 1, 1.0)
    harbor_trial(job, "b__1", "vita-delivery-10711002", 1, 0.0, exc=True)

    out = run(["--original", str(orig), "--harbor", str(job)])
    metrics = json.loads(out[out.index("{"):out.rindex("}") + 1])
    # Uppercase upstream id matched the lowercased Harbor dir, and only the common cohort counts.
    assert metrics["original_runs"] == [100.0, 100.0], metrics
    assert metrics["harbor_runs"] == [100.0, 100.0], metrics
    assert "missing" in out and "cohort: 1 tasks" in out, out

    # --tasks with the canonical (uppercase) id keeps both sides.
    out = run(["--original", str(orig), "--harbor", str(job), "--tasks", "A0812003"])
    assert "cohort: 1 tasks" in out and '"harbor_runs": [\n    100.0,\n    100.0' in out, out

    # --strict refuses mismatched cohorts.
    r = subprocess.run([sys.executable, "-I", str(HERE / "aggregate.py"), "--original", str(orig),
                        "--harbor", str(job), "--strict"], capture_output=True, text=True)
    assert r.returncode != 0 and "cohorts differ" in (r.stderr + r.stdout), r

print("aggregate.py self-check OK")
