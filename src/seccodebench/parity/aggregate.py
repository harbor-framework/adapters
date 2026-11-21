"""Aggregate SecCodeBench parity runs into the parity_experiment.json `metrics` structure.

usage (from src/seccodebench):
  uv run python parity/aggregate.py \
      --harbor-jobs JOB_DIR [JOB_DIR ...]   # one Harbor job dir per run
      --original-runs RUN_DIR [RUN_DIR ...] # one run_original.sh output dir per run
      [--tasks TASK_ID ...] [--per-task-csv out.csv] [--json out.json]

Per task, reward = 1 iff functional AND security passed (Harbor: verifier reward; original:
`function.result and security.result` in the e2e per-case JSON). A run's score is the mean
reward over the task set (the union of tasks seen on either side unless --tasks is given;
a task missing from a run counts as 0). Each side is reported as mean ± sample SEM over
runs (adapters spec, ADP-STATS).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

from seccodebench.adapter import slug

PREFIX = "alibaba/seccodebench__"


def harbor_rewards(job_dir: Path) -> dict[str, float]:
    out = {}
    for f in job_dir.glob("*/result.json"):
        r = json.loads(f.read_text())
        name = (r.get("task_name") or "").removeprefix(PREFIX)
        rewards = (r.get("verifier_result") or {}).get("rewards") or {}
        if name:
            out[name] = float(rewards.get("reward", 0.0))
    return out


def harbor_cost_usd(job_dir: Path) -> float:
    """Sum of Claude Code's own `total_cost_usd` (last stream-json result event per trial).
    Harbor 0.3.0 leaves result.json agent_result.cost_usd = None for claude-code."""
    total = 0.0
    for log in job_dir.glob("*/agent/claude-code.txt"):
        last = None
        for line in log.read_text(errors="replace").splitlines():
            if '"total_cost_usd"' in line:
                try:
                    last = float(json.loads(line).get("total_cost_usd") or 0.0)
                except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
                    continue
        total += last or 0.0
    return total


def original_rewards(run_dir: Path) -> dict[str, float]:
    out = {}
    for f in run_dir.rglob("*.json"):
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        tc = d.get("testcase") if isinstance(d, dict) else None
        if not isinstance(tc, dict) or "name" not in tc or "language" not in tc:
            continue
        for key, scenarios in d.items():
            if not key.isdigit() or not isinstance(scenarios, dict):
                continue  # per-cycle entries are keyed "0", "1", ...
            for scenario, res in scenarios.items():
                ok = bool(res.get("function", {}).get("result")) and bool(res.get("security", {}).get("result"))
                out[f"{tc['language']}-{slug(tc['name'])}-{scenario}"] = 1.0 if ok else 0.0
    return out


def mean_sem(xs: list[float]) -> tuple[float, float | None]:
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, None
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) * (len(xs) - 1)))


def fmt(xs: list[float]) -> str:
    m, sem = mean_sem(xs)
    return f"{m:.2f} ± {sem:.2f}" if sem is not None else f"{m:.2f} (n=1, SEM undefined)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harbor-jobs", nargs="+", type=Path, required=True)
    ap.add_argument("--original-runs", nargs="+", type=Path, required=True)
    ap.add_argument("--tasks", nargs="*", default=None, help="task ids (without org prefix)")
    ap.add_argument("--per-task-csv", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None, help="write the metrics entry here")
    a = ap.parse_args()

    h_runs = [harbor_rewards(j) for j in a.harbor_jobs]
    o_runs = [original_rewards(r) for r in a.original_runs]
    tasks = sorted(a.tasks or set().union(*h_runs, *o_runs))
    if not tasks:
        sys.exit("no tasks found")
    score = lambda run: 100.0 * sum(run.get(t, 0.0) for t in tasks) / len(tasks)  # noqa: E731
    h_scores = [round(score(r), 4) for r in h_runs]
    o_scores = [round(score(r), 4) for r in o_runs]
    metric = {
        "benchmark_name": "SecCodeBench",
        "metric": "func_and_sec_pass_rate (%)",
        "original": fmt(o_scores),
        "harbor": fmt(h_scores),
        "original_runs": o_scores,
        "harbor_runs": h_scores,
    }
    overlap = max(o_scores) >= min(h_scores) and max(h_scores) >= min(o_scores)
    print(json.dumps(metric, indent=2, ensure_ascii=False))
    print(f"tasks={len(tasks)} runs: original={len(o_scores)} harbor={len(h_scores)} ranges_overlap={overlap}")
    print("harbor agent cost (claude-code total_cost_usd): $%.4f" % sum(harbor_cost_usd(j) for j in a.harbor_jobs))
    if a.json:
        a.json.write_text(json.dumps(metric, indent=2, ensure_ascii=False) + "\n")
    if a.per_task_csv:
        with a.per_task_csv.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["task"] + [f"original_run{i + 1}" for i in range(len(o_runs))]
                       + [f"harbor_run{i + 1}" for i in range(len(h_runs))])
            for t in tasks:
                w.writerow([t] + [r.get(t, "") for r in o_runs] + [r.get(t, "") for r in h_runs])


if __name__ == "__main__":
    main()
