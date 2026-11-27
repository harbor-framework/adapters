"""Aggregate complete AgentDojo runs by clean utility, attacked utility and ASR."""

import argparse
import json
import math
import statistics
from pathlib import Path


def stage(root, repetition):
    manifest = json.loads((root / "manifest.json").read_text())
    ids = manifest["sanity_ids"] if repetition == "sanity" else manifest["task_ids"]
    folder = root / "runs" / repetition
    records = {"original": {}, "harbor": {}}
    trials = {"original": {}, "harbor": {}}
    for task in ids:
        p = folder / "original" / task
        v = json.loads((p / "result.json").read_text())
        if v.get("status") != "completed":
            raise ValueError(f"Incomplete native trial: {task}")
        records["original"][task] = {k: v[k] for k in ("utility", "security")}
        trials["original"][task] = p
    for f in (folder / "harbor/job").glob("*/result.json"):
        v = json.loads(f.read_text())
        task = Path(v["task_id"]["path"]).name
        if v.get("exception_info") or v.get("reward_valid") is False or task in records["harbor"]:
            raise ValueError(f"Unscored or duplicate Harbor task: {task}")
        scores = v["verifier_result"]["rewards"]
        records["harbor"][task] = {"utility": scores["utility"], "security": scores.get("security")}
        trials["harbor"][task] = f.parent / "agent"
    for side, tasks in records.items():
        if set(tasks) != set(ids):
            raise ValueError(f"Task set mismatch: {side}")
    for task in ids:
        requests = []
        for side in ("original", "harbor"):
            p = trials[side][task]
            requests.append(json.loads((p / "requests.jsonl").read_text().splitlines()[0]))
            for line in (p / "responses.jsonl").read_text().splitlines():
                model = json.loads(line)["model"]
                if model not in {"deepseek-v4.1-flash", "deepseek-v4-1-flash-261017"}:
                    raise ValueError(f"Unexpected model: {model}")
        if requests[0] != requests[1]:
            raise ValueError(f"Initial model inputs differ: {task}")
    metrics = {}
    for side, tasks in records.items():
        groups = {
            "utility": [r["utility"] for r in tasks.values() if r["security"] is None],
            "utility_under_attack": [r["utility"] for r in tasks.values() if r["security"] is not None],
            "targeted_asr": [r["security"] for r in tasks.values() if r["security"] is not None],
        }
        if not all(values and all(v in (0, 1) for v in values) for values in groups.values()):
            raise ValueError("Missing or invalid stratum scores")
        metrics[side] = {name: statistics.mean(values) for name, values in groups.items()}
    return {"per_task": records, "metrics": metrics, "task_count": len(ids)}


def aggregate(root, rounds):
    runs = [stage(root, repetition) for repetition in rounds]
    result = {"rounds": rounds, "runs": runs, "metrics": {}}
    for metric in ("utility", "utility_under_attack", "targeted_asr"):
        by_side = {}
        for side in ("original", "harbor"):
            values = [r["metrics"][side][metric] for r in runs]
            by_side[side] = {"runs": values, "mean": statistics.mean(values),
                             "sample_sem": statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None}
        a, b = by_side["original"]["runs"], by_side["harbor"]["runs"]
        by_side["run_ranges_overlap"] = max(a) >= min(b) and max(b) >= min(a)
        result["metrics"][metric] = by_side
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--rounds", nargs="+", choices=["sanity", "1", "2", "3"], required=True)
    args = parser.parse_args()
    if len(set(args.rounds)) != len(args.rounds) or ("sanity" in args.rounds and len(args.rounds) > 1):
        parser.error("Use distinct formal rounds, or sanity alone")
    print(json.dumps(aggregate(args.workspace, args.rounds), indent=2))
