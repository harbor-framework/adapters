"""Strict offline aggregation of paired native BALROG runs and Harbor jobs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys


class ValidationError(ValueError):
    """An input cannot support a complete, comparable parity measurement."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def canonical_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def read_json(path):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # Do not echo arbitrary file contents or provider error messages.
        raise ValidationError(f"Cannot read valid JSON: {path}") from exc


def number(value, label):
    require(type(value) in (float, int) and math.isfinite(value), f"Invalid finite number: {label}")
    return float(value)


def score(value, label):
    value = number(value, label)
    require(0.0 <= value <= 1.0, f"BALROG progression must be in [0, 1]: {label}")
    return value


def summary(values):
    require(len(values) >= 2, "At least two complete runs per side are required")
    values = [number(value, "run mean") for value in values]
    mean = statistics.mean(values)
    sem = math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) * (len(values) - 1)))
    return {"runs": values, "mean": mean, "sample_sem": sem, "min": min(values), "max": max(values)}


def load_manifest(path, split):
    path = Path(path).resolve()
    manifest = read_json(path)
    require(isinstance(manifest, dict) and manifest.get("schema_version") == 1, "Unsupported manifest schema")
    splits = manifest.get("splits")
    require(isinstance(splits, dict) and split in splits, f"Manifest has no split: {split}")
    task_ids = splits[split]
    require(isinstance(task_ids, list) and task_ids, "Manifest split must not be empty")
    require(all(isinstance(task, str) and task for task in task_ids), "Invalid task IDs in manifest")
    require(len(task_ids) == len(set(task_ids)), "Manifest split contains duplicate tasks")
    cases = manifest.get("cases")
    require(isinstance(cases, list), "Manifest cases must be a list")
    episodes = {}
    for case in cases:
        require(isinstance(case, dict) and isinstance(case.get("episode"), dict), "Invalid manifest case")
        episode = case["episode"]
        task_id = episode.get("task_id")
        require(isinstance(task_id, str) and task_id, "Manifest case lacks task_id")
        require(task_id not in episodes, f"Duplicate manifest case: {task_id}")
        for key in ("task", "seed", "expected_max_steps", "expected_initial_observation_sha256"):
            require(key in episode, f"Manifest case {task_id} lacks {key}")
        require(type(episode["seed"]) is int and 0 <= episode["seed"] < 2**32, f"Invalid manifest seed: {task_id}")
        require(type(episode["expected_max_steps"]) is int and episode["expected_max_steps"] > 0,
                f"Invalid manifest step budget: {task_id}")
        require(isinstance(episode["expected_initial_observation_sha256"], str)
                and re.fullmatch(r"[0-9a-f]{64}", episode["expected_initial_observation_sha256"]),
                f"Invalid manifest observation checksum: {task_id}")
        episodes[task_id] = episode
    require(set(task_ids) <= episodes.keys(), "Manifest split references missing cases")
    pins = manifest.get("source_commits")
    require(isinstance(pins, dict) and pins.get("balrog"), "Manifest lacks benchmark version pins")
    env_names = {episodes[t].get("env_name", "babyai") for t in task_ids}
    require(len(env_names) == 1, "Analyze each environment separately before equal-environment suite aggregation")
    if env_names == {"babyai"}:
        require(pins.get("minigrid"), "Manifest lacks Minigrid version pin")
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "split": split,
        "task_ids": task_ids,
        "task_ids_sha256": canonical_hash(task_ids),
        "episodes": {task_id: episodes[task_id] for task_id in task_ids},
        "source_commits": pins,
        "env_name": next(iter(env_names)),
    }


def check_game_result(result, episode, label):
    require(isinstance(result, dict), f"Missing episode result: {label}")
    for key, expected in (("task_id", episode["task_id"]), ("task", episode["task"]),
                          ("seed", episode["seed"]), ("max_steps", episode["expected_max_steps"]),
                          ("initial_observation_sha256", episode["expected_initial_observation_sha256"])):
        require(result.get(key) == expected, f"Manifest mismatch for {label}: {key}")
    steps = result.get("steps")
    require(type(steps) is int and 0 <= steps <= result["max_steps"], f"Invalid step count: {label}")
    for field in ("terminated", "truncated"):
        require(type(result.get(field)) is bool, f"Missing termination state: {label}")
    progression = score(result.get("progression"), label)
    if episode.get("env_name", "babyai") == "babyai":
        require(progression in (0.0, 1.0), f"BabyAI progression must be binary: {label}")
        require(progression == 0 or result["terminated"], f"Positive progression without termination: {label}")
    return progression


def exact_tasks(found, task_ids, label):
    expected = set(task_ids)
    actual = set(found)
    require(actual == expected,
            f"Task coverage differs in {label}; missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")


def no_secret_fields(value):
    """Settings are public provenance; reject accidental credential fields."""
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            require(lowered not in {"api_key", "authorization", "password", "secret", "access_token", "token"}
                    and not lowered.endswith(("_api_key", "_secret", "_password")),
                    "Settings contain a credential field; provide public settings only")
            no_secret_fields(child)
    elif isinstance(value, list):
        for child in value:
            no_secret_fields(child)


def runner_hash(value):
    """The runner deliberately uses json.dumps' default separators/ASCII mode."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def require_int(value, label, minimum=0):
    require(type(value) is int and value >= minimum, f"Invalid integer: {label}")
    return value


def load_episode(path, mode, manifest):
    record = read_json(path)
    label = str(path)
    require(isinstance(record, dict), f"Invalid episode record: {label}")
    require(record.get("status") == "completed", f"Episode did not complete: {label}")
    require(not any(record.get(key) for key in ("error", "error_type", "exception_info")), f"Episode reports an error: {label}")
    require(record.get("mode") == mode, f"Wrong runner mode: {label}")
    task_id = record.get("task_id")
    require(isinstance(task_id, str) and task_id in manifest["episodes"], f"Unexpected task in {label}")
    settings = record.get("settings")
    require(isinstance(settings, dict), f"Missing public model settings: {label}")
    no_secret_fields(settings)
    require(isinstance(settings.get("client"), dict) and settings["client"].get("model_id"), f"Missing model identifier: {label}")
    require(record.get("settings_sha256") == runner_hash(settings), f"Model settings checksum mismatch: {label}")
    require(record.get("source_commits") == manifest["source_commits"], f"Benchmark version pins differ: {label}")
    require(isinstance(record.get("runner_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", record["runner_sha256"]),
            f"Missing runner code checksum: {label}")
    versions = record.get("runtime_versions")
    require(isinstance(versions, dict) and isinstance(versions.get("python"), str)
            and isinstance(versions.get("packages"), dict) and versions["packages"], f"Missing runtime version pins: {label}")
    require(isinstance(record.get("session_id"), str) and record["session_id"], f"Missing episode session ID: {label}")
    require_int(record.get("model_calls"), f"model calls in {label}", 1)
    require_int(record.get("input_tokens"), f"input tokens in {label}")
    require_int(record.get("output_tokens"), f"output tokens in {label}")
    calls = read_json(path.parent / "model_calls.json")
    require(isinstance(calls, list) and len(calls) == record["model_calls"], f"Incomplete model-call log: {label}")
    sums = {"input_tokens": 0, "output_tokens": 0}
    for index, call in enumerate(calls):
        require(isinstance(call, dict) and call.get("call") == index, f"Invalid model-call sequence: {label}")
        require(not call.get("error_type") and not call.get("error"), f"Model-call log reports an error: {label}")
        require(isinstance(call.get("messages"), list), f"Missing raw model prompt: {label}")
        require(call.get("prompt_sha256") == runner_hash(call["messages"]), f"Prompt checksum mismatch: {label}")
        require(isinstance(call.get("raw_completion"), str), f"Missing raw completion: {label}")
        for key in sums:
            sums[key] += require_int(call.get(key), f"{key} in model-call log {label}")
    require(all(record[key] == value for key, value in sums.items()), f"Token totals differ from raw model calls: {label}")
    require(record.get("steps") == len(calls), f"Action/model-call counts differ: {label}")
    return {"record": record, "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "model_calls_sha256": hashlib.sha256((path.parent / "model_calls.json").read_bytes()).hexdigest(),
            "first_prompt_sha256": calls[0]["prompt_sha256"]}


def reject_error_files(root):
    require(not (root / "OFFLINE_TEST_ONLY.json").exists(),
            f"Offline/mock integration outputs are not model parity evidence: {root}")
    # A failed attempt cannot disappear just because a later result looks valid.
    require(not any(root.rglob("error.json")), f"Run contains an infrastructure-error artifact: {root}")
    require(not any(root.rglob("exception.txt")), f"Run contains a Harbor exception artifact: {root}")


def load_native(root, manifest):
    require(root.is_dir(), f"Native run directory is missing: {root}")
    reject_error_files(root)
    if (root / "run_status.json").exists():
        status = read_json(root / "run_status.json")
        require(status.get("status") == "completed", f"Native batch did not complete: {root}")
        for key in ("task_ids", "completed"):
            require(status.get(key) == manifest["task_ids"], f"Native batch {key} differs from frozen split: {root}")
    found = {}
    for path in sorted(root.rglob("episode_result.json")):
        item = load_episode(path, "native", manifest)
        record = item["record"]
        task_id = record["task_id"]
        require(task_id not in found, f"Duplicate native episode {task_id} in {root}")
        result = {**record, "progression": record.get("native_progression")}
        item["score"] = check_game_result(result, manifest["episodes"][task_id], str(path))
        found[task_id] = item
    exact_tasks(found, manifest["task_ids"], str(root))
    return found


def load_harbor(root, manifest):
    require(root.is_dir(), f"Harbor job directory is missing: {root}")
    reject_error_files(root)
    job = read_json(root / "result.json")
    require(isinstance(job, dict) and job.get("finished_at"), f"Harbor job did not finish: {root}")
    stats = job.get("stats")
    require(isinstance(stats, dict), f"Harbor job lacks statistics: {root}")
    for key in ("n_errored_trials", "n_running_trials", "n_pending_trials", "n_cancelled_trials", "n_retries"):
        require(type(stats.get(key)) is int and stats[key] == 0, f"Harbor job has nonzero or unrecorded {key}: {root}")
    require(type(stats.get("n_completed_trials")) is int and stats["n_completed_trials"] == len(manifest["task_ids"]),
            f"Harbor completed count differs from manifest: {root}")
    found = {}
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        trial = read_json(directory / "result.json")
        require(isinstance(trial, dict) and trial.get("finished_at"), f"Harbor trial did not finish: {directory}")
        require("exception_info" in trial and trial["exception_info"] is None, f"Harbor trial has an exception: {directory}")
        require(trial.get("reward_valid") is True, f"Harbor reward is not valid: {directory}")
        item = load_episode(directory / "agent" / "episode_result.json", "http", manifest)
        record = item["record"]
        task_id = record["task_id"]
        require(task_id not in found, f"Duplicate Harbor episode {task_id} in {root}")
        require(trial.get("task_name") == f"balrog/{task_id}", f"Harbor trial/agent task IDs differ: {directory}")
        verified = read_json(directory / "verifier" / "result.json")
        item["score"] = check_game_result(verified, manifest["episodes"][task_id], str(directory))
        require(verified.get("finalized") is True, f"Harbor result was not finalized: {directory}")
        require(isinstance(verified.get("transitions"), list) and len(verified["transitions"]) == verified["steps"],
                f"Harbor verifier trajectory is incomplete: {directory}")
        if verified.get("replay_verified") is True:
            require(score(verified.get("replay_progression"), str(directory)) == item["score"], f"Harbor replay score differs: {directory}")
            item["verification_mode"] = "deterministic_replay"
        else:
            diagnostic = verified.get("replay_diagnostic") or {}
            divergence = diagnostic.get("first_divergent_step")
            require(manifest["env_name"] == verified.get("env_name") == "crafter"
                    and verified.get("replay_verified") is False
                    and verified.get("scoring_mode") == "authoritative_native_state"
                    and "replay_progression" in verified
                    and verified.get("replay_progression") is None
                    and diagnostic.get("code") == "crafter_native_object_order_nondeterminism"
                    and type(divergence) is int and 0 <= divergence <= verified["steps"],
                    f"Missing verified replay or explicit Crafter native-state evidence: {directory}")
            item["verification_mode"] = "authoritative_native_state"
            item["replay_diagnostic"] = diagnostic
        rewards = (trial.get("verifier_result") or {}).get("rewards")
        require(isinstance(rewards, dict) and score(rewards.get("reward"), str(directory)) == item["score"],
                f"Harbor reported reward differs from trusted verifier: {directory}")
        for key in ("steps", "max_steps", "initial_observation_sha256", "terminated", "truncated"):
            require(record.get(key) == verified.get(key), f"Harbor agent/verifier disagree on {key}: {directory}")
        agent_result = trial.get("agent_result") or {}
        for harbor_key, record_key in (("n_input_tokens", "input_tokens"), ("n_output_tokens", "output_tokens")):
            if agent_result.get(harbor_key) is not None:
                require(agent_result[harbor_key] == record[record_key], f"Harbor runner token totals disagree: {directory}")
        exit_path = directory / "agent" / "exit-code.txt"
        if exit_path.exists():
            require(exit_path.read_text(encoding="utf-8").strip() == "0", f"Harbor agent process failed: {directory}")
        item["harbor_agent_info"] = trial.get("agent_info")
        item["task_checksum"] = trial.get("task_checksum")
        item["trial_result_sha256"] = hashlib.sha256((directory / "result.json").read_bytes()).hexdigest()
        item["verifier_result_sha256"] = hashlib.sha256((directory / "verifier" / "result.json").read_bytes()).hexdigest()
        found[task_id] = item
    exact_tasks(found, manifest["task_ids"], str(root))
    return found


def tokens(episodes):
    records = [item["record"] for item in episodes.values()]
    return {key: sum(record[key] for record in records) for key in ("input_tokens", "output_tokens", "model_calls")}


def analyze(manifest_path, pairs, split="parity"):
    require(len(pairs) >= 2, "At least two explicit native/Harbor run pairs are required")
    manifest = load_manifest(manifest_path, split)
    paths = [(Path(native).resolve(), Path(harbor).resolve()) for native, harbor in pairs]
    flattened = [path for pair in paths for path in pair]
    require(len(flattened) == len(set(flattened)), "Each run directory must occur exactly once")
    expected_provenance = None
    expected_runtime = {}
    expected_prompts = {}
    sessions = set()
    paired_runs, native_means, harbor_means = [], [], []
    task_scores = {task_id: {"native": [], "harbor": []} for task_id in manifest["task_ids"]}
    totals = {side: {key: 0 for key in ("input_tokens", "output_tokens", "model_calls")} for side in ("native", "harbor")}
    for index, (native_path, harbor_path) in enumerate(paths, 1):
        sides = {"native": load_native(native_path, manifest), "harbor": load_harbor(harbor_path, manifest)}
        evidence = {"native": {}, "harbor": {}}
        for side, episodes in sides.items():
            for task_id in manifest["task_ids"]:
                item, record = episodes[task_id], episodes[task_id]["record"]
                provenance = {key: record[key] for key in ("settings_sha256", "runner_sha256", "source_commits")}
                if expected_provenance is None:
                    expected_provenance = {**provenance, "settings": record["settings"]}
                require(provenance == {key: expected_provenance[key] for key in provenance},
                        f"Agent/model settings or version pins drift in pair {index}, {side}, {task_id}")
                if side not in expected_runtime:
                    expected_runtime[side] = record["runtime_versions"]
                require(record["runtime_versions"] == expected_runtime[side], f"Runtime versions drift within {side}")
                # Python/platform can differ across native and container sides; record
                # both. Model SDK package versions must be identical on both sides.
                if len(expected_runtime) == 2:
                    require(expected_runtime["native"]["packages"] == expected_runtime["harbor"]["packages"],
                            "Model SDK package versions differ between sides")
                expected_prompts.setdefault(task_id, item["first_prompt_sha256"])
                require(item["first_prompt_sha256"] == expected_prompts[task_id], f"Initial model prompt differs for {task_id}")
                require(record["session_id"] not in sessions, "Episode session ID reused; independent runs are required")
                sessions.add(record["session_id"])
                task_scores[task_id][side].append(item["score"])
                evidence[side][task_id] = {key: value for key, value in item.items() if key != "record"}
            counts = tokens(episodes)
            for key in counts:
                totals[side][key] += counts[key]
        native_scores = {task: sides["native"][task]["score"] for task in manifest["task_ids"]}
        harbor_scores = {task: sides["harbor"][task]["score"] for task in manifest["task_ids"]}
        native_means.append(statistics.mean(native_scores.values()))
        harbor_means.append(statistics.mean(harbor_scores.values()))
        paired_runs.append({
            "pair": index, "native_directory": str(native_path), "harbor_directory": str(harbor_path),
            "native_mean": native_means[-1], "harbor_mean": harbor_means[-1],
            "native_tokens": tokens(sides["native"]), "harbor_tokens": tokens(sides["harbor"]),
            "native_only": [task for task in manifest["task_ids"] if native_scores[task] > harbor_scores[task]],
            "harbor_only": [task for task in manifest["task_ids"] if harbor_scores[task] > native_scores[task]],
            "evidence": evidence,
        })
    native_stats, harbor_stats = summary(native_means), summary(harbor_means)
    overlap = native_stats["max"] >= harbor_stats["min"] and harbor_stats["max"] >= native_stats["min"]
    per_task = []
    for task_id, values in task_scores.items():
        per_task.append({"task_id": task_id, **values,
                         "native_only_pairs": [i + 1 for i, (a, b) in enumerate(zip(values["native"], values["harbor"])) if a > b],
                         "harbor_only_pairs": [i + 1 for i, (a, b) in enumerate(zip(values["native"], values["harbor"])) if b > a]})
    return {
        "schema_version": 1, "kind": manifest["env_name"] + "_parity_analysis", "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_only": True,
        "note": "Validated local measurements only; no claim of team approval, publication, or Ready for Review.",
        "metric": manifest["env_name"] + " native progression", "units": "fraction", "number_of_runs_per_side": len(pairs),
        "manifest": {key: value for key, value in manifest.items() if key != "episodes"},
        "provenance": {**expected_provenance, "runtime_versions_by_side": expected_runtime,
                       "initial_prompt_sha256_by_task": expected_prompts},
        "native": native_stats, "harbor": harbor_stats, "run_score_ranges_overlap": overlap,
        "token_totals": totals, "paired_runs": paired_runs, "per_task": per_task,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", default="parity")
    parser.add_argument("--pair", nargs=2, action="append", required=True, metavar=("NATIVE_RUN", "HARBOR_JOB"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        require(args.output.name != "parity_experiment.json", "Write an analysis artifact; assemble formal parity_experiment.json separately")
        result = analyze(args.manifest, args.pair, args.split)
        require(not args.output.exists(), "Output already exists; choose a new analysis path to avoid stale evidence")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        print(json.dumps({"output": str(args.output.resolve()), "native": result["native"], "harbor": result["harbor"],
                          "run_score_ranges_overlap": result["run_score_ranges_overlap"]}, ensure_ascii=False))
        return 0
    except (ValidationError, OSError) as exc:
        print(f"Parity analysis rejected: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
