"""Compute the paper's Table 2 numbers from Harbor job directories.

One job directory is one run of the benchmark: four scenarios times three seed pairs for one
agent. With --pool, the given job directories together are one run. The aggregate is only
reported for a complete run, in which every cell has exactly one graded trial.

A trial is graded if the verifier wrote a reward after the integrity judge returned two valid
verdicts. A graded trial that failed counts as 1x, as in the paper. A trial without valid
verdicts is ungraded, a trial without any verifier outcome is an error, and a run that recomputes
the PyTorch quality reference is not a benchmark trial; all of them are listed and none enters a
mean.
"""

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

TASK_RE = re.compile(
    r"(?:^|/)inferencebench-(?P<scenario>[a-d])-[a-z0-9-]+-(?P<agent>\d+)-(?P<eval>\d+)$"
)
SCENARIOS = ("a", "b", "c", "d")
# The benchmark's development:evaluation seed pairs (DEFAULT_SEED_PAIRS upstream).
SEED_PAIRS = ("21:1337", "248:428", "999:777")
STATUSES = ("valid", "failed", "ungraded", "error", "reference")


def sample_sem(values: list[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    center = mean(values)
    return math.sqrt(sum((value - center) ** 2 for value in values) / (n * (n - 1)))


def geomean(values: list[float]) -> float:
    return math.exp(mean(math.log(value) for value in values))


def read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load_trials(job_dir: Path) -> list[dict]:
    """Return one record per InferenceBench trial of a Harbor job.

    Harbor writes a trial's result to <job>/<trial>/result.json, and the verifier's own files
    to <job>/<trial>/verifier/. Files of the same names deeper in a trial directory are the
    agent's, so they are not read.
    """
    records = []
    for path in sorted(job_dir.glob("*/result.json")):
        result = read_json(path)
        if result is None:
            print(f"{path}: not a trial result, skipped", file=sys.stderr)
            continue
        match = TASK_RE.search(str(result.get("task_name") or ""))
        if match is None:
            continue
        agent = result.get("agent_info") or {}
        model = (agent.get("model_info") or {}).get("name")
        record = {
            "trial": str(path.parent),
            "agent": " ".join(str(part) for part in (agent.get("name"), model) if part),
            "scenario": match["scenario"],
            "seed_pair": f"{match['agent']}:{match['eval']}",
            "status": "error",
            "reward": None,
            "note": str((result.get("exception_info") or {}).get("exception_type") or "no reward"),
        }
        rewards = (result.get("verifier_result") or {}).get("rewards")
        if not isinstance(rewards, dict) or not isinstance(rewards.get("reward"), (int, float)):
            rewards = None
        ungraded = read_json(path.parent / "verifier" / "ungraded.json")
        agent_env = ((result.get("config") or {}).get("agent") or {}).get("env") or {}
        if agent_env.get("INFERENCE_BENCH_ORACLE") == "pytorch-reference":
            record.update(status="reference", note="recomputes the PyTorch quality reference")
        elif rewards is not None and rewards.get("judge_valid") == 1:
            valid = rewards.get("valid") == 1
            record.update(
                status="valid" if valid else "failed",
                reward=float(rewards["reward"]),
                speedup=rewards.get("speedup"),
                note="" if valid else "counted as 1x",
            )
        elif rewards is not None:
            # No verifier of this adapter writes such a reward any more.
            record.update(
                status="ungraded",
                speedup=rewards.get("speedup"),
                note="the reward was written without a valid judge verdict",
            )
        elif ungraded is not None:
            record.update(
                status="ungraded",
                speedup=ungraded.get("speedup"),
                note=str(ungraded.get("reason") or ungraded.get("judge") or "no valid judge verdict"),
            )
        records.append(record)
    return records


def summarize(records: list[dict]) -> dict:
    """Aggregate one agent's trials as Table 2 does.

    A scenario's value is the mean over seed pairs, and the aggregate is the geometric mean of the
    four scenario values. The aggregate's SEM is computed over seed pairs, from each seed pair's
    geometric mean over scenarios. Only graded trials enter; if a cell of the grid has no graded
    trial or more than one, the cell is named and no aggregate is reported.
    """
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    seed_pairs = sorted({*SEED_PAIRS, *(record["seed_pair"] for record in records)})
    for record in records:
        if record["reward"] is not None:
            cells[record["seed_pair"], record["scenario"]].append(record["reward"])
    count = {status: sum(record["status"] == status for record in records) for status in STATUSES}
    summary = {
        "n_trials": len(records),
        "n_graded": count["valid"] + count["failed"],
        "n_valid": count["valid"],
        "n_failed": count["failed"],
        "n_ungraded": count["ungraded"],
        "n_errors": count["error"],
        "n_reference": count["reference"],
        "missing": [
            f"{scenario} {pair}"
            for pair in seed_pairs
            for scenario in SCENARIOS
            if not cells[pair, scenario]
        ],
        "repeated": [
            f"{scenario} {pair}"
            for pair in seed_pairs
            for scenario in SCENARIOS
            if len(cells[pair, scenario]) > 1
        ],
        "scenarios": {},
        "trials": [
            {
                "trial": record["trial"],
                "cell": f"{record['scenario']} {record['seed_pair']}",
                **{key: record.get(key) for key in ("status", "reward", "speedup", "note")},
            }
            for record in records
        ],
    }
    for scenario in SCENARIOS:
        values = [value for pair in seed_pairs for value in cells[pair, scenario]]
        if values:
            summary["scenarios"][scenario] = {
                "mean": mean(values),
                "sem": sample_sem(values),
                "runs": values,
            }
    if not summary["missing"] and not summary["repeated"]:
        per_seed = [geomean([cells[pair, scenario][0] for scenario in SCENARIOS]) for pair in seed_pairs]
        summary["aggregate"] = {
            "mean": geomean([summary["scenarios"][scenario]["mean"] for scenario in SCENARIOS]),
            "sem": sample_sem(per_seed),
            "seed_pairs": per_seed,
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("job_dirs", nargs="+", type=Path, help="Harbor job directories")
    parser.add_argument(
        "--pool",
        action="store_true",
        help="treat the job directories together as one run, for a run that was launched in stages",
    )
    args = parser.parse_args()
    runs = (
        [(" + ".join(str(job_dir) for job_dir in args.job_dirs), args.job_dirs)]
        if args.pool
        else [(str(job_dir), [job_dir]) for job_dir in args.job_dirs]
    )
    complete = True
    for name, job_dirs in runs:
        by_agent: dict[str, list[dict]] = defaultdict(list)
        for job_dir in job_dirs:
            for record in load_trials(job_dir):
                by_agent[record["agent"]].append(record)
        if not by_agent:
            print(f"{name}: no InferenceBench trials found", file=sys.stderr)
            complete = False
        for agent, records in sorted(by_agent.items()):
            summary = summarize(records)
            print(json.dumps({"job": name, "agent": agent, **summary}, indent=2))
            for key, problem in (
                ("missing", "have no graded trial"),
                ("repeated", "have more than one graded trial"),
            ):
                if summary[key]:
                    complete = False
                    print(
                        f"{name} {agent}: no aggregate, because these cells {problem}: "
                        f"{', '.join(summary[key])}",
                        file=sys.stderr,
                    )
            for row in summary["trials"]:
                if row["status"] in ("ungraded", "error", "reference"):
                    print(f"{name} {agent}: {row['status']}: {row['trial']}: {row['note']}", file=sys.stderr)
    sys.exit(0 if complete else 1)


if __name__ == "__main__":
    main()
