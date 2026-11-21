#!/usr/bin/env python3
"""Aggregate VitaBench parity runs into the `metrics` entry of parity_experiment.json.

Original side: one or more upstream simulation batch files written by run_original.sh
(`simulations[*].{task_id, trial, reward_info.reward}`); each upstream trial is one run.
Harbor side: one or more Harbor job dirs; each trial's run index is the agent kwarg
`vita_trial_index`, and its reward is `verifier/reward.txt`. Trials that recorded an exception
(agent crash, infrastructure error) or have no reward file are reported and excluded, never
counted as 0. Note that Harbor's own job mean does count them as 0.

Per run, the score is mean reward over tasks x 100 (success rate in %). Prints both sides
as mean ± sample SEM, the run-range overlap check from the adapter spec, and a ready-to-paste
metrics object.

Usage:
  python3 aggregate.py --original <batch.json> [...] --harbor <job_dir> [...] [--tasks <id> ...]
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path


def sem(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n * (n - 1)))


def fmt(xs: list[float]) -> str:
    return f"{sum(xs) / len(xs):.2f} ± {sem(xs):.4f}" if xs else "n/a"


def original_runs(paths: list[Path], keep: set[str] | None) -> dict[int, dict[str, float]]:
    runs: dict[int, dict[str, float]] = defaultdict(dict)
    for p in paths:
        for s in json.loads(p.read_text())["simulations"]:
            tid = str(s["task_id"]).lower()  # Harbor dir names are lowercased; compare canonically
            if keep and tid not in keep:
                continue
            reward = (s.get("reward_info") or {}).get("reward")
            if reward is None:
                continue
            runs[int(s.get("trial") or 0)][tid] = float(reward)
    return runs


def harbor_runs(job_dirs: list[Path], keep: set[str] | None) -> tuple[dict[int, dict[str, float]], list[str]]:
    runs: dict[int, dict[str, float]] = defaultdict(dict)
    errored: list[str] = []
    for job in job_dirs:
        for trial in sorted(p for p in job.iterdir() if (p / "config.json").is_file()):
            cfg = json.loads((trial / "config.json").read_text())
            task_dir = Path(cfg["task"]["path"]).name  # e.g. vita-cross-10804001
            tid = re.sub(r"^vita-[a-z]+-", "", task_dir).lower()
            if keep and tid not in keep:
                continue
            idx = int(((cfg.get("agent") or {}).get("kwargs") or {}).get("vita_trial_index") or 0)
            reward_file = trial / "verifier" / "reward.txt"
            result_file = trial / "result.json"
            exc = json.loads(result_file.read_text()).get("exception_info") if result_file.is_file() else None
            if exc or not reward_file.is_file():
                # Agent crash / infra failure: exclude (re-run it), never count as 0.
                why = (exc or {}).get("exception_type") or "no reward"
                errored.append(f"{trial.name} (run {idx}, {why})")
                continue
            runs[idx][tid] = float(reward_file.read_text().strip())
    return runs, errored


def per_run_scores(runs: dict[int, dict[str, float]]) -> list[float]:
    return [round(100 * sum(r.values()) / len(r), 4) for _, r in sorted(runs.items()) if r]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", nargs="+", type=Path, required=True)
    ap.add_argument("--harbor", nargs="+", type=Path, required=True)
    ap.add_argument("--tasks", nargs="*", default=None, help="restrict to these upstream task ids")
    ap.add_argument("--benchmark-name", default="VitaBench")
    ap.add_argument("--metric", default="success_rate")
    ap.add_argument("--strict", action="store_true",
                    help="fail instead of restricting to the common task cohort when runs differ")
    args = ap.parse_args()
    keep = {t.lower() for t in args.tasks} if args.tasks else None

    orig = original_runs(args.original, keep)
    harb, errored = harbor_runs(args.harbor, keep)

    # Every run on both sides must score the same task population, otherwise the runs are
    # not comparable repetitions. Restrict to the cohort present in all runs (or fail).
    all_runs = [("original", i, r) for i, r in sorted(orig.items())] + [("harbor", i, r) for i, r in sorted(harb.items())]
    cohort = set.intersection(*(set(r) for _, _, r in all_runs)) if all_runs else set()
    union = set().union(*(set(r) for _, _, r in all_runs)) if all_runs else set()
    if cohort != union:
        print(f"WARNING: task sets differ across runs/sides: {len(union) - len(cohort)} of {len(union)} tasks "
              "are missing from at least one run (re-run them).")
        for side, i, r in all_runs:
            missing = sorted(union - set(r))
            if missing:
                print(f"  {side} run {i} missing {len(missing)}: {', '.join(missing[:10])}")
        if args.strict:
            raise SystemExit("aborting (--strict): task cohorts differ")
        print(f"  -> scoring only the {len(cohort)} tasks present in every run")
        orig = {i: {t: v for t, v in r.items() if t in cohort} for i, r in orig.items()}
        harb = {i: {t: v for t, v in r.items() if t in cohort} for i, r in harb.items()}
    o, h = per_run_scores(orig), per_run_scores(harb)

    for name, runs in (("original", orig), ("harbor", harb)):
        for idx, r in sorted(runs.items()):
            print(f"{name} run {idx}: {len(r)} tasks, success {100 * sum(r.values()) / len(r):.2f}%")
    if errored:
        print(f"harbor trials excluded (no reward, infra error): {len(errored)}: {', '.join(errored[:10])}")

    overlap = bool(o and h and max(o) >= min(h) and max(h) >= min(o))
    print(f"original {fmt(o)}  runs={o}")
    print(f"harbor   {fmt(h)}  runs={h}")
    print(f"run ranges overlap (spec matching criterion): {overlap}")
    print(json.dumps({
        "benchmark_name": args.benchmark_name,
        "metric": args.metric,
        "original": fmt(o),
        "harbor": fmt(h),
        "original_runs": o,
        "harbor_runs": h,
    }, indent=2, ensure_ascii=False))
    print(f"cohort: {len(cohort)} tasks")


if __name__ == "__main__":
    main()
