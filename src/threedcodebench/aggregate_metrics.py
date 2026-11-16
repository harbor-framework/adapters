#!/usr/bin/env python3
"""Aggregate 3DCodeBench metrics from Harbor job directories.

Harbor's own job summary reports the mean of reward.txt (= executability).
The shape metric needs per-trial raw values, so each trial's verifier writes
/logs/verifier/metrics.json; this script turns those into the numbers the
paper reports (Table 2, coding-agent rows):

  executability     fraction of tasks whose script ran, produced >= 1 mesh and
                    rendered 4 views (trials without metrics count as 0)
  cd / cd_yawmin    conditional mean Chamfer distance over tasks whose
                    generated GLB loaded (upstream `conditional_mean`)
  *_penalized       failures scored as 1.5 x the worst valid CD of the run
                    (upstream `penalized_mean`)

Usage:
  python aggregate_metrics.py <job_dir> [<job_dir> ...] [--expected-tasks 212]
With several job dirs (one per run), it also prints mean ± sample SEM
across runs, the format required for parity_experiment.json.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load_job(job_dir: Path) -> list[dict]:
    rows = []
    for trial in sorted(p for p in job_dir.iterdir() if p.is_dir()):
        m = trial / "verifier" / "metrics.json"
        if m.is_file():
            rows.append(json.loads(m.read_text()))
        else:
            rows.append({"instance": trial.name.split("__")[0], "executability": 0, "missing_metrics": True})
    return rows


def summarize(rows: list[dict], expected: int | None) -> dict:
    n = expected or len(rows)
    exec_rate = sum(int(r.get("executability") == 1) for r in rows) / n
    out = {"n_trials": len(rows), "n_tasks": n, "executability": exec_rate}
    for key in ("cd", "cd_yawmin"):
        valid = [r[key] for r in rows if r.get("chamfer_status") == "OK" and r.get(key) is not None]
        out[f"{key}_n_valid"] = len(valid)
        out[f"{key}_conditional"] = sum(valid) / len(valid) if valid else None
        if valid:
            penalty = 1.5 * max(valid)
            out[f"{key}_penalized"] = (sum(valid) + penalty * (n - len(valid))) / n
        else:
            out[f"{key}_penalized"] = None
    out["missing_metrics"] = sum(1 for r in rows if r.get("missing_metrics"))
    return out


def mean_sem(xs: list[float]) -> tuple[float, float | None]:
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, None
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) * (len(xs) - 1)))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("job_dirs", nargs="+", type=Path)
    p.add_argument("--expected-tasks", type=int, default=None,
                   help="Denominator for rates (default: number of trials found)")
    p.add_argument("--json", action="store_true", help="Print machine-readable output")
    args = p.parse_args()

    per_run = {str(j): summarize(load_job(j), args.expected_tasks) for j in args.job_dirs}
    result: dict = {"runs": per_run}
    if len(per_run) > 1:
        across = {}
        for key in ("executability", "cd_conditional", "cd_yawmin_conditional"):
            vals = [r[key] for r in per_run.values() if r[key] is not None]
            if vals:
                m, sem = mean_sem(vals)
                across[key] = {"runs": vals, "mean": m, "sem": sem}
        result["across_runs"] = across

    if args.json:
        print(json.dumps(result, indent=2))
        return
    for job, s in per_run.items():
        print(f"{job}")
        print(f"  trials={s['n_trials']} tasks={s['n_tasks']} missing_metrics={s['missing_metrics']}")
        print(f"  executability={s['executability']:.4f}")
        for key in ("cd", "cd_yawmin"):
            c, pen = s[f"{key}_conditional"], s[f"{key}_penalized"]
            print(f"  {key:<9} conditional={c if c is None else f'{c:.4f}'} "
                  f"(n={s[f'{key}_n_valid']})  penalized={pen if pen is None else f'{pen:.4f}'}")
    for key, v in result.get("across_runs", {}).items():
        sem = "n/a" if v["sem"] is None else f"{v['sem']:.4f}"
        print(f"{key}: {v['mean']:.4f} ± {sem}  runs={['%.4f' % x for x in v['runs']]}")


if __name__ == "__main__":
    main()
