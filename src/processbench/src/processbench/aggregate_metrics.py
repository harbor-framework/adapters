"""
Compute ProcessBench metrics from a Harbor job directory.

ProcessBench reports, per subset, accuracy on erroneous samples (label != -1),
accuracy on correct samples (label == -1), and their harmonic mean (F1), matching
code/run_eval.py in QwenLM/ProcessBench. Harbor rewards are per task, so this
script regroups the per-trial verifier/metrics.json files written by grade.py.

Usage:
    uv run python -m processbench.aggregate_metrics <job_dir> \
        [--dataset-dir datasets/processbench] [--output results.json]

Wrong, missing, or unparsable answers are scored 0 by grade.py and count as
wrong. With --dataset-dir, any expected task without a metrics.json (agent,
infrastructure, or verifier failure) is listed and the script exits non-zero
without reporting F1, since the job is not a complete run.
"""

import argparse
import json
import sys
from pathlib import Path


def load_trials(job_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(job_dir.glob("*/verifier/metrics.json")):
        row = json.loads(path.read_text())
        row["trial"] = path.parents[1].name
        rows.append(row)
    return rows


def load_expected(dataset_dir: Path) -> dict[str, dict]:
    expected = {}
    for path in sorted(dataset_dir.glob("*/tests/ground_truth.json")):
        gt = json.loads(path.read_text())
        expected[gt["id"]] = gt
    return expected


def subset_metrics(rows: list[dict]) -> dict:
    error = [r["match"] for r in rows if r["label"] != -1]
    correct = [r["match"] for r in rows if r["label"] == -1]
    acc1 = 100 * sum(error) / len(error) if error else 0.0
    acc2 = 100 * sum(correct) / len(correct) if correct else 0.0
    f1 = 2 * acc1 * acc2 / (acc1 + acc2) if acc1 + acc2 else 0.0
    return {
        "n_error": len(error),
        "n_correct": len(correct),
        "error_acc": acc1,
        "correct_acc": acc2,
        "f1": f1,
    }


def aggregate(rows: list[dict]) -> dict:
    subsets = sorted({r["subset"] for r in rows})
    per_subset = {
        s: subset_metrics([r for r in rows if r["subset"] == s]) for s in subsets
    }
    avg_f1 = sum(m["f1"] for m in per_subset.values()) / len(per_subset)
    return {"per_subset": per_subset, "avg_f1": avg_f1, "n_tasks": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--dataset-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.job_dir.is_dir():
        sys.exit(f"Job directory not found: {args.job_dir}")
    if args.dataset_dir is not None and not args.dataset_dir.is_dir():
        sys.exit(f"Dataset directory not found: {args.dataset_dir}")

    rows = load_trials(args.job_dir)
    seen = [r["id"] for r in rows]
    duplicates = sorted({i for i in seen if seen.count(i) > 1})
    if duplicates:
        sys.exit(
            f"Found multiple trials for {len(duplicates)} tasks (e.g. {duplicates[0]}); "
            "run one attempt per task and aggregate each job separately."
        )

    if args.dataset_dir is not None:
        expected = load_expected(args.dataset_dir)
        if not expected:
            sys.exit(f"No tasks (*/tests/ground_truth.json) found under {args.dataset_dir}")
        missing = sorted(set(expected) - set(seen))
        if missing:
            sys.exit(
                f"{len(missing)} of {len(expected)} tasks have no verifier/metrics.json "
                f"(agent, infrastructure, or verifier failure): {', '.join(missing)}\n"
                "The job is incomplete; not reporting F1."
            )
    if not rows:
        sys.exit(f"No verifier/metrics.json files found under {args.job_dir}")

    result = aggregate(rows)

    for subset, m in result["per_subset"].items():
        print(
            f"{subset} error acc: {m['error_acc']:.1f}, "
            f"correct acc: {m['correct_acc']:.1f}, f1: {m['f1']:.1f}"
        )
    print(f"average f1: {result['avg_f1']:.1f} over {result['n_tasks']} tasks")

    if args.output is not None:
        args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
