"""Validate Harbor reference artifacts, preserving partial native scores."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def score_value(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
            f"Invalid {label}")
    return float(value)


def same_score(actual, expected):
    return math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12)


def serialized_score(actual, expected, label):
    actual = score_value(actual, label)
    # Earlier smoke verifiers wrote :g (six significant digits). Permit exactly
    # that known representation, rather than a broad numerical tolerance.
    legacy = not same_score(actual, expected)
    require(not legacy or actual == float(format(expected, ".6g")), f"{label} mismatch")
    return legacy


def timestamp(value, label, naive_timezone=None):
    require(isinstance(value, str) and bool(value), f"Missing {label}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None and naive_timezone is not None:
            parsed = parsed.replace(tzinfo=naive_timezone)
        # Harbor 0.26 writes local naive job times and UTC-aware trial times.
        # With no override, Python interprets naive times in this host timezone.
        return parsed.astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(f"Invalid {label}") from exc


def check_trial(path, trial, episode, reference, reference_status, job, naive_timezone=None):
    task_id = episode["task_id"]
    prefix = task_id + ": "
    require(trial.get("task_name") == "balrog/" + task_id, prefix + "Harbor task name mismatch")
    require(trial.get("agent_info", {}).get("name") == "oracle", prefix + "unexpected agent")
    require(trial.get("exception_info") is None, prefix + "trial exception")
    require(trial.get("reward_valid") is True, prefix + "Harbor reward is not valid")
    times = [timestamp(obj.get(key), prefix + key, naive_timezone) for obj, key in (
        (job, "started_at"), (trial, "started_at"), (trial, "finished_at"), (job, "finished_at"))]
    require(times == sorted(times), prefix + "trial timestamps fall outside this completed job")
    if job.get("id") is not None:
        require(trial.get("config", {}).get("job_id") == job["id"], prefix + "trial belongs to another job")
    require(isinstance(reference, dict), prefix + "missing reference")
    actions = reference.get("actions")
    require(isinstance(actions, list) and actions and all(isinstance(a, str) for a in actions),
            prefix + "invalid reference actions")
    expected_score = score_value(reference.get("expected_progression"), prefix + "native reference score")
    result = read_json(path / "verifier/result.json")
    for field, expected in (
        ("schema_version", 1), ("task_id", task_id), ("task", episode["task"]),
        ("seed", episode["seed"]), ("max_steps", episode["expected_max_steps"]),
        ("initial_observation_sha256", episode["expected_initial_observation_sha256"]),
    ):
        require(result.get(field) == expected, prefix + f"native {field} mismatch")
    env_name = episode.get("env_name", "babyai")
    require(result.get("env_name", "babyai") == env_name, prefix + "environment mismatch")
    require(result.get("replay_verified") is True and result.get("finalized") is True,
            prefix + "replay not finalized and verified")
    score = score_value(result.get("progression"), prefix + "progression")
    replay_score = score_value(result.get("replay_progression"), prefix + "replay progression")
    require(same_score(score, expected_score) and same_score(score, replay_score),
            prefix + "native/Harbor reference score mismatch")
    rewards = trial.get("verifier_result", {}).get("rewards")
    require(isinstance(rewards, dict) and set(rewards) == {"reward"}, prefix + "missing Harbor reward")
    legacy_rounding = serialized_score(rewards["reward"], score, prefix + "Harbor reward")
    reward_found = False
    for filename in ("reward.json", "reward.txt"):
        reward_path = path / "verifier" / filename
        if not reward_path.exists():
            continue
        reward_found = True
        if filename.endswith(".json"):
            payload = read_json(reward_path)
            require(isinstance(payload, dict) and set(payload) == {"reward"}, prefix + "invalid reward.json")
            value = payload["reward"]
        else:
            value = float(reward_path.read_text(encoding="utf-8"))
        legacy_rounding |= serialized_score(value, score, prefix + filename)
    require(reward_found, prefix + "reward file missing")
    actual = result.get("transitions")
    require(isinstance(actual, list) and type(result.get("steps")) is int
            and result["steps"] == len(actual) == len(actions)
            and result["steps"] <= episode["expected_max_steps"], prefix + "transition count mismatch")
    for key in ("terminated", "truncated"):
        require(type(result.get(key)) is bool, prefix + f"invalid {key}")
        if "expected_" + key in reference:
            require(result[key] == reference["expected_" + key], prefix + f"native {key} mismatch")
    expected_transitions = reference.get("expected_transitions")
    if "expected_transitions" in reference:
        require(isinstance(expected_transitions, list) and len(expected_transitions) == len(actions),
                prefix + "native transition count mismatch")
    for index, transition in enumerate(actual):
        require(transition.get("step") == index and transition.get("raw_action") == actions[index],
                prefix + f"reference action/index mismatch at {index}")
        require(type(transition.get("budget_exhausted")) is bool
                and transition["budget_exhausted"] == (index + 1 >= episode["expected_max_steps"]),
                prefix + f"step budget mismatch at {index}")
        for key in ("terminated", "truncated"):
            require(type(transition.get(key)) is bool, prefix + f"invalid transition {key}")
        require(index == len(actual) - 1 or not (transition["terminated"] or transition["truncated"]),
                prefix + "trajectory continues after termination")
        if expected_transitions is not None:
            for key, value in expected_transitions[index].items():
                target = "observation_sha256" if key == "observation" else key
                require(transition.get(target) == value, prefix + f"native {key} mismatch at {index}")
    require(result["terminated"] == actual[-1]["terminated"]
            and result["truncated"] == (actual[-1]["truncated"] or
                 (actual[-1]["budget_exhausted"] and not actual[-1]["terminated"])),
            prefix + "final termination mismatch")
    if reference_status is not None:
        require(type(reference_status.get("full_oracle_available")) is bool,
                prefix + "invalid reference status")
        declared_oracle = reference_status["full_oracle_available"]
    else:
        declared_oracle = reference.get("kind", "oracle") == "oracle" and expected_score == 1.0
    require(not declared_oracle or expected_score == 1.0, prefix + "partial reference marked as full oracle")
    return {"task_id": task_id, "env_name": env_name, "progression": score,
            "full_reward": score == 1.0, "full_oracle": declared_oracle and score == 1.0,
            "steps": result["steps"], "replay_verified": True,
            "native_transitions_checked": expected_transitions is not None,
            "validation_level": "native_transitions_and_server_replay" if expected_transitions is not None
                else "server_replay_and_native_final_score_only",
            "legacy_reward_rounding": legacy_rounding}


def check_job(dataset, job_path, naive_timezone=None):
    job = read_json(job_path / "result.json")
    require(bool(job.get("finished_at")), "Job is incomplete")
    expected = {}
    for path in sorted(dataset.iterdir()):
        if not (path / "task.toml").exists():
            continue
        episode = read_json(path / "environment/episode.json")
        task_id = episode["task_id"]
        require(task_id not in expected, "Duplicate dataset task ID")
        status = path / "solution/reference_status.json"
        expected[task_id] = (episode, read_json(path / "solution/oracle_actions.json"),
                             read_json(status) if status.exists() else None)
    require(bool(expected), "Dataset contains no tasks")
    stats = job["stats"]
    require(job.get("n_total_trials") == stats.get("n_completed_trials") == len(expected),
            "Job total/completed counts differ from selected dataset")
    for state in ("errored", "cancelled", "running", "pending"):
        require(stats.get(f"n_{state}_trials", 0) == 0, f"Job contains {state} trials")
    paths = sorted(job_path.glob("*/result.json"))
    require(len(paths) == len(expected), "Trial artifact count differs from selected dataset")
    verifier_paths = list(job_path.glob("*/verifier/result.json"))
    require({p.parent.parent for p in verifier_paths} == {p.parent for p in paths},
            "Missing or orphan verifier artifact")
    checks, seen = [], set()
    for path in paths:
        trial = read_json(path)
        name = trial.get("task_name", "")
        require(name.startswith("balrog/"), "Unexpected task namespace")
        task_id = name.removeprefix("balrog/")
        require(task_id in expected and task_id not in seen, "Duplicate or unexpected task result")
        seen.add(task_id)
        checks.append(check_trial(path.parent, trial, *expected[task_id], job, naive_timezone))
    require(seen == set(expected), "Incomplete task coverage")
    by_env = {}
    for check in checks:
        group = by_env.setdefault(check["env_name"], {
            "count": 0, "full_reward_count": 0, "full_oracle_count": 0, "score_sum": 0.0})
        group["count"] += 1
        group["full_reward_count"] += int(check["full_reward"])
        group["full_oracle_count"] += int(check["full_oracle"])
        group["score_sum"] += check["progression"]
    for group in by_env.values():
        group["mean_progression"] = group.pop("score_sum") / group["count"]
    naive_start = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
    interpreted_start = naive_start.replace(tzinfo=naive_timezone) if naive_start.tzinfo is None and naive_timezone else naive_start.astimezone()
    return {"status": "reference_scores_and_replay_verified", "count": len(checks),
            "job_started_at_utc": timestamp(job["started_at"], "job started_at", naive_timezone).isoformat(),
            "naive_timestamp_interpretation": {
                "source": "explicit offset" if naive_timezone else "checker host local timezone",
                "job_start_utc_offset_seconds": int(interpreted_start.utcoffset().total_seconds())},
            "all_full_oracles": all(c["full_oracle"] for c in checks), "by_environment": by_env,
            "job_result_sha256": hashlib.sha256((job_path / "result.json").read_bytes()).hexdigest(),
            "note": "Partial and diagnostic traces are not complete oracles. Missing native transition fixtures are explicitly marked. No model parity was run.",
            "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--naive-utc-offset", help="Original job host offset for naive timestamps, e.g. -08:00; default: this host local timezone")
    args = parser.parse_args()
    try:
        naive_timezone = None
        if args.naive_utc_offset:
            value = args.naive_utc_offset
            require(len(value) == 6 and value[0] in "+-" and value[3] == ":", "Expected UTC offset +/-HH:MM")
            hours, minutes = int(value[1:3]), int(value[4:6])
            require(hours < 24 and minutes < 60, "Invalid UTC offset")
            naive_timezone = timezone((1 if value[0] == "+" else -1) * timedelta(hours=hours, minutes=minutes))
        report = check_job(args.dataset, args.job, naive_timezone)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        args.output.write_text(json.dumps({"status": "failed", "error": str(exc)}, indent=2) + "\n",
                               encoding="utf-8")
        parser.exit(1, f"Suite reference verification FAILED: {exc}\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, indent=2))


if __name__ == "__main__":
    main()
