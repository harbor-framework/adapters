#!/usr/bin/env python3
"""
Collect oracle trajectories for the VitaBench adapter from Harbor job outputs.

VitaBench has no reference solutions (reward is a rubric-based LLM judge over
the conversation), so oracle solutions are built the way the adapter spec
describes for such benchmarks: run capable agents over the tasks, keep the
trajectories that score 1.0, then fill the remaining tasks with stronger
models / more trials under human review.

This script scans one or more Harbor `jobs/` directories, finds trials whose
verifier reward is 1.0, and copies the runtime state file
(`verifier/vita_runtime_state.json`, saved by the verifier) to `src/vita-bench/oracle/<task_set>/<id>.json`
so the adapter can ship it as `solution/oracle_trajectory.json`.

A trajectory is only accepted when it has been scored 1.0 at least
`--min-passes` times across the scanned trials, which guards against single
lucky judgments from the stochastic evaluator. Independent live runs never
confirm each other (each conversation is different), so oracles are built in
two rounds (from the adapters repo root):

    # 1. harvest one passing candidate per task into a staging dir (not oracle/)
    python src/vita-bench/scripts/build_oracle.py jobs/<live-job> --min-passes 1 \
        --out jobs/oracle-candidates --clean
    # 2. generate tasks with the candidates and replay them: `-a oracle` re-scores each
    #    stored conversation once more (see README "Oracle solutions")
    # 3. keep only trajectories scored 1.0 twice (live + replay) in a clean oracle/
    python src/vita-bench/scripts/build_oracle.py jobs/<live-job> jobs/<replay-job> \
        --min-passes 2 --clean

`--clean` empties the output dir's trajectory files first, so candidates that
failed the replay never linger there (`--overwrite` alone only replaces files of
accepted tasks).
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parents[1] / "oracle"


def _reward(trial_dir: Path) -> float | None:
    reward_path = trial_dir / "verifier" / "reward.txt"
    if not reward_path.exists():
        return None
    try:
        return float(reward_path.read_text().strip())
    except ValueError:
        return None


def _task_identity(state: dict) -> tuple[str, str] | None:
    task_set = state.get("task_set")
    task_id = state.get("task_id")
    if not task_set or not task_id:
        return None
    return str(task_set), str(task_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dirs", nargs="+", type=Path)
    parser.add_argument("--min-passes", type=int, default=1)
    parser.add_argument("--out", type=Path, default=ORACLE_DIR, help="output dir (default: oracle/)")
    parser.add_argument("--overwrite", action="store_true", help="replace files of accepted tasks")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="delete existing trajectory files in --out first, so it holds only this run's accepted set",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out_dir: Path = args.out

    # (task_set, task_id) -> list of (passes, state_path)
    candidates: dict[tuple[str, str], list[tuple[int, Path]]] = defaultdict(list)
    pass_counts: dict[str, int] = defaultdict(int)

    for job_dir in args.job_dirs:
        for state_path in job_dir.rglob("verifier/vita_runtime_state.json"):
            trial_dir = state_path.parent.parent
            reward = _reward(trial_dir)
            if reward is None or reward < 1.0:
                continue
            state = json.loads(state_path.read_text(encoding="utf-8"))
            identity = _task_identity(state)
            if identity is None:
                continue
            if state.get("termination_reason") not in {"agent_stop", "user_stop"}:
                continue
            key = json.dumps(state["messages"], sort_keys=True, ensure_ascii=False)
            pass_counts[key] += 1
            candidates[identity].append((pass_counts[key], state_path))

    if args.clean and not args.dry_run and out_dir.is_dir():
        stale = sorted(out_dir.glob("*/*.json"))
        for path in stale:
            path.unlink()
        print(f"Removed {len(stale)} existing trajectories from {out_dir}")

    written = 0
    skipped: list[str] = []
    for (task_set, task_id), entries in sorted(candidates.items()):
        best = max(entries, key=lambda item: item[0])
        if best[0] < args.min_passes:
            skipped.append(f"{task_set}/{task_id} (best {best[0]} pass(es))")
            continue
        target = out_dir / task_set / f"{task_id}.json"
        if target.exists() and not args.overwrite:
            continue
        print(f"{task_set}/{task_id}: {best[0]} pass(es) <- {best[1]}")
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best[1], target)
        written += 1

    print(f"\nWrote {written} oracle trajectories to {out_dir}")
    if skipped:
        print(f"Skipped {len(skipped)} tasks below --min-passes={args.min_passes}:")
        for item in skipped:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
