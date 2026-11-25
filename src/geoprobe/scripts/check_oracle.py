"""Audit a completed Harbor oracle job against all frozen reference annotations."""
import argparse
import json
from pathlib import Path

from geoprobe.metric import aggregate
from geoprobe.sources import ARENA_COMMIT, DATASET_COMMIT, HARBOR_COMMIT, load_cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--recovery-job", type=Path, action="append", default=[], help="Infrastructure-only recovery job; original attempts remain recorded")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = {case["sample_id"]: case for case in load_cases(args.data_root)}
    jobs = [args.job_dir, *args.recovery_job]
    for job_dir in jobs:
        job = json.loads((job_dir / "result.json").read_text())
        assert job.get("finished_at"), f"Job is still running: {job_dir}"
    seen, failures, infrastructure, rewards = set(), [], [], []
    maximum_errors = {}
    for file in sorted(file for job_dir in jobs for file in job_dir.glob("*/result.json")):
        trial = json.loads(file.read_text())
        assert (trial.get("agent_info") or {}).get("name") == "oracle", "Only oracle jobs belong in this audit"
        if trial.get("exception_info"):
            infrastructure.append({"trial": file.parent.name, "job": str(file.parent.parent.resolve()),
                                   "reason": trial["exception_info"]["exception_type"]})
            continue
        native = json.loads((file.parent / "verifier/native-metrics.json").read_text())
        sample = native["sample_id"]
        assert sample in expected and sample not in seen, sample
        seen.add(sample)
        rewards.append(trial["verifier_result"]["rewards"])
        case = expected[sample]
        value = native.get(case["primary_metric"])
        optimal = value is True if case["primary_metric"] == "exact_match" else isinstance(value, (int, float)) and abs(value) <= 2e-6
        if not native.get("submission_valid") or not optimal:
            failures.append({"sample": sample, "metric": case["primary_metric"], "value": value})
        if case["primary_metric"] != "exact_match" and isinstance(value, (int, float)):
            key = case["benchmark"] + "." + case["primary_metric"]
            maximum_errors[key] = max(maximum_errors.get(key, 0), abs(value))
    missing = sorted(set(expected) - seen)
    report = {"scope": "Harbor Docker oracle replay; native primary-metric optimum, not model parity",
              "arena_commit": ARENA_COMMIT, "dataset_commit": DATASET_COMMIT, "harbor_commit": HARBOR_COMMIT,
              "expected_tasks": len(expected), "completed_tasks": len(seen), "failures": failures,
              "infrastructure_attempts": infrastructure, "aggregated_native_metrics": aggregate(rewards),
              "missing_samples": missing, "maximum_native_error_by_protocol": maximum_errors,
              "model_api_calls": 0, "source_jobs": [str(job.resolve()) for job in jobs]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ["expected_tasks", "completed_tasks", "failures", "missing_samples"]}))
    assert not failures and not missing


if __name__ == "__main__":
    main()
