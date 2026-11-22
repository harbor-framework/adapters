"""Compare native evidence with Harbor evidence; never label this model parity."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--native", type=Path, required=True)
parser.add_argument("--harbor", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--forgery-probe", action="store_true")
parser.add_argument('--expected-task-ids', nargs='+')
args = parser.parse_args()
rows = []
for evidence_path in args.harbor.glob("*/artifacts/private/runs/evidence.json"):
    evidence = json.loads(evidence_path.read_text("utf-8"))
    task_id = evidence["task_id"]
    native = json.loads((args.native / (task_id + "__trial0") / "result.json").read_text("utf-8"))
    harbor = evidence["result"]
    for key in ("reward", "termination", "actual_tool_calls", "classification", "verification"):
        assert native[key] == harbor[key], (task_id, key, native[key], harbor[key])
    trial = evidence_path.parents[3]
    score = (trial / "verifier/reward.txt").read_text("utf-8").strip()
    assert float(score) == native["reward"]
    assert not (trial / "verifier/reward.json").exists(), "Forged alternate reward survived"
    rows.append({"task_id": task_id, "native_reward": native["reward"], "harbor_reward": float(score),
                 "termination": native["termination"], "tool_calls": native["actual_tool_calls"],
                 "full_verdict_equal": True, "forged_main_evidence_ignored": args.forgery_probe})
assert rows, "No trusted Harbor evidence found"
task_ids = [row['task_id'] for row in rows]
assert len(task_ids) == len(set(task_ids)), 'Duplicate Harbor task evidence'
if args.expected_task_ids:
    assert set(task_ids) == set(args.expected_task_ids), ('Incomplete task coverage', sorted(task_ids), sorted(args.expected_task_ids))
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps({"kind": "offline_trajectory_equivalence_not_model_parity", "tasks": rows}, indent=2) + "\n", "utf-8")
print(f"Matched {len(rows)} complete native/Harbor verdicts and isolated grader rewards")
