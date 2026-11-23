"""Check a complete Harbor oracle job against every native manifest transition."""

import argparse
import hashlib
import json
from pathlib import Path


DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "src/balrog/fixtures/manifest.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message: str) -> None:
    if not condition:
        raise ValueError(message)


def select_fixtures(manifest: dict, split: str, task_ids: list[str] | None) -> dict:
    require(split in manifest["splits"], f"Unknown manifest split: {split}")
    selected = set(manifest["splits"][split])
    if task_ids:
        require(set(task_ids) <= selected, f"Requested task IDs are outside split {split}")
        selected.intersection_update(task_ids)
    fixtures = {}
    for case in manifest["cases"]:
        task_id = case["episode"]["task_id"]
        require(task_id not in fixtures, f"Duplicate manifest task ID: {task_id}")
        fixtures[task_id] = case
    require(selected and selected <= fixtures.keys(), "Manifest split is empty or references missing fixtures")
    return {task_id: case for task_id, case in fixtures.items() if task_id in selected}


def check_trial(trial_path: Path, trial: dict, case: dict) -> dict:
    episode, oracle = case["episode"], case["oracle"]
    task_id = episode["task_id"]
    prefix = f"{task_id}: "
    require(bool(trial.get("finished_at")), prefix + "trial has not finished")
    require(trial.get("exception_info") is None, prefix + "trial exception")
    require(trial["agent_info"]["name"] == "oracle", prefix + "unexpected agent")
    require(trial["task_name"] == "balrog/" + task_id, prefix + "Harbor task name mismatch")
    require(trial["verifier_result"]["rewards"] == {"reward": 1.0}, prefix + "Harbor score is not 1")
    verifier = trial_path.parent / "verifier"
    require(float((verifier / "reward.txt").read_text()) == 1.0, prefix + "reward.txt is not 1")
    result = read_json(verifier / "result.json")
    for field, value in (
        ("task_id", task_id), ("task", episode["task"]), ("seed", episode["seed"]),
        ("max_steps", episode["expected_max_steps"]),
        ("initial_observation_sha256", episode["expected_initial_observation_sha256"]),
    ):
        require(result[field] == value, prefix + f"native {field} mismatch")
    require(result["replay_verified"] is True and result["finalized"] is True, prefix + "replay was not verified")
    require(result["progression"] == result["replay_progression"] == oracle["expected_progression"] == 1.0,
            prefix + "native progression mismatch")
    require(result["terminated"] is True and result["truncated"] is False, prefix + "mission did not finish")
    expected, actual = oracle["expected_transitions"], result["transitions"]
    require(result["steps"] == len(actual) == len(expected) == len(oracle["actions"]), prefix + "transition count mismatch")
    for index, (native, adapted) in enumerate(zip(expected, actual)):
        require(adapted["step"] == index, prefix + f"step index mismatch at {index}")
        require(adapted["raw_action"] == oracle["actions"][index], prefix + f"raw action mismatch at {index}")
        require(adapted["budget_exhausted"] == (index + 1 >= episode["expected_max_steps"]),
                prefix + f"step-budget status mismatch at {index}")
        for key, value in native.items():
            target = "observation_sha256" if key == "observation" else key
            require(adapted[target] == value, prefix + f"native {key} mismatch at {index}")
    return {
        "task_id": task_id,
        "reward": 1.0,
        "steps": result["steps"],
        "replay_verified": True,
        "native_fixture_matched": True,
        "verifier_result": str((verifier / "result.json").resolve()),
    }


def check_job(path: Path, fixtures: dict) -> list[dict]:
    job = read_json(path / "result.json")
    require(bool(job.get("finished_at")), "Job has not finished")
    stats = job["stats"]
    require(stats["n_completed_trials"] == len(fixtures), "Completed trial count differs from selected manifest")
    require(job["n_total_trials"] == len(fixtures), "Total trial count differs from selected manifest")
    require(stats["n_errored_trials"] == 0, "Harbor reported infrastructure errors; they are not benchmark scores")
    for state in ("running", "pending", "cancelled"):
        require(stats.get(f"n_{state}_trials", 0) == 0, f"Job has {state} trials")
    trials = sorted(path.glob("*/result.json"))
    require(len(trials) == len(fixtures), "Trial artifact count differs from selected manifest")
    checked = {}
    for trial_path in trials:
        trial = read_json(trial_path)
        name = trial["task_name"]
        require(name.startswith("balrog/"), f"Unexpected task namespace: {name}")
        task_id = name.removeprefix("balrog/")
        require(task_id in fixtures, f"Trial outside selected manifest: {task_id}")
        require(task_id not in checked, f"Duplicate trial for task: {task_id}")
        checked[task_id] = check_trial(trial_path, trial, fixtures[task_id])
    require(checked.keys() == fixtures.keys(), "Job is missing selected manifest tasks")
    return [checked[task_id] for task_id in fixtures]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--split", choices=("full", "sanity", "parity"), default="full")
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        manifest = read_json(args.manifest)
        fixtures = select_fixtures(manifest, args.split, args.task_ids)
        checks = check_job(args.job, fixtures)
        report = {
            "status": "passed", "split": args.split, "passed": len(checks), "total": len(fixtures),
            "agent": "oracle", "exceptions": 0,
            "fixture_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
            "source_native_report_sha256": manifest["source_report_sha256"],
            "job_result": str((args.job / "result.json").resolve()), "checks": checks,
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"status": "failed", "error": str(exc), "job": str(args.job)}
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        parser.exit(1, f"Oracle verification FAILED: {exc}\n")
    encoded = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8", newline="\n")
    print(encoded)


if __name__ == "__main__":
    main()
