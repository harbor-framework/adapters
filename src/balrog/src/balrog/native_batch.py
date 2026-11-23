"""Run frozen native episodes sequentially inside the pinned game image."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def write_status(path, status):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--episode-timeout", type=int, default=1800)
    args = parser.parse_args()
    episodes = json.loads(args.episodes.read_text(encoding="utf-8"))
    if not isinstance(episodes, list) or not episodes or args.episode_timeout < 1:
        parser.error("A nonempty episode list and a positive timeout are required")
    seen = set()
    for episode in episodes:
        task_id = episode.get("task_id", "")
        if (not task_id or task_id in seen
                or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in task_id)):
            parser.error("Task IDs must be safe, nonempty and unique")
        seen.add(task_id)
        env_name = episode.get("env_name", "babyai")
        if env_name not in {"babyai", "babaisai", "textworld", "crafter", "nle", "minihack"}:
            parser.error("Invalid frozen environment")
        if (env_name == "babyai" and episode.get("task") not in {
            "BabyAI-MixedTrainLocal-v0/" + kind
            for kind in ("goto", "pickup", "open", "putnext", "pick_up_seq_go_to")
        }) or type(episode.get("seed")) is not int or not 0 <= episode["seed"] < 2**32:
            parser.error("Invalid frozen BabyAI task or seed")
        budgets = {"babyai": (64, 128), "babaisai": (100,), "textworld": (80,), "crafter": (2000,), "nle": (100000,), "minihack": (100,)}
        if type(episode.get("expected_max_steps")) is not int or episode["expected_max_steps"] not in budgets[env_name]:
            parser.error("Invalid frozen step budget")
        if env_name == "babyai" and (not isinstance(episode.get("expected_mission"), str) or not episode["expected_mission"].strip()):
            parser.error("Invalid frozen mission")
        observation_hash = episode.get("expected_initial_observation_sha256")
        if not isinstance(observation_hash, str) or not re.fullmatch("[0-9a-f]{64}", observation_hash):
            parser.error("Invalid frozen observation hash")
        if env_name == "babyai" and episode.get("babyai_kwargs") != {"num_dists": 0}:
            parser.error("Unexpected BabyAI parameters for this frozen subset")
    # Validate all settings before any paid request or per-task subprocess.
    from parity_runner import load_config
    settings = json.loads(args.settings.read_text(encoding="utf-8"))
    load_config(Path("/opt/balrog/balrog/config/config.yaml"), settings)
    if args.output_dir.exists() and any(path.name != "run_plan.json" for path in args.output_dir.iterdir()):
        parser.error("Output contains previous artifacts; use a new run directory")
    runner_bytes = Path(__file__).with_name("parity_runner.py").read_bytes()
    settings_text = json.dumps(settings, sort_keys=True, ensure_ascii=True)
    status = {"status": "running", "task_ids": [item["task_id"] for item in episodes], "completed": [],
              "episodes_sha256": hashlib.sha256(json.dumps(episodes, sort_keys=True).encode()).hexdigest(),
              "input_settings_sha256": hashlib.sha256(settings_text.encode()).hexdigest(),
              "runner_sha256": hashlib.sha256(runner_bytes).hexdigest()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    status_path = args.output_dir / "run_status.json"
    # Exclusive creation prevents two batch processes from sharing a run.
    with status_path.open("x", encoding="utf-8") as handle:
        json.dump(status, handle, indent=2)
    inputs = args.output_dir / "inputs"
    inputs.mkdir()
    snapshot_settings = inputs / "settings.json"
    snapshot_settings.write_text(settings_text, encoding="utf-8")
    snapshot_runner = inputs / "parity_runner.py"
    snapshot_runner.write_bytes(runner_bytes)
    for episode in episodes:
        task_id = episode["task_id"]
        episode_path = inputs / (task_id + ".json")
        episode_path.write_text(json.dumps(episode, indent=2) + "\n", encoding="utf-8")
        command = [sys.executable, str(snapshot_runner),
                   "--mode", "native", "--episode", str(episode_path),
                   "--settings", str(snapshot_settings), "--output-dir", str(args.output_dir / task_id)]
        try:
            completed = subprocess.run(command, timeout=args.episode_timeout, check=False)
            if completed.returncode:
                raise RuntimeError("Native runner failed")
            report = json.loads((args.output_dir / task_id / "episode_result.json").read_text(encoding="utf-8"))
            if report.get("status") != "completed" or report.get("mode") != "native" or report.get("task_id") != task_id:
                raise RuntimeError("Native runner did not produce a valid fresh result")
        except (subprocess.TimeoutExpired, RuntimeError, OSError, ValueError) as exc:
            status.update(status="error", failed_task=task_id, error_type=type(exc).__name__)
            write_status(status_path, status)
            return 1
        status["completed"].append(task_id)
        write_status(status_path, status)
    status["status"] = "completed"
    write_status(status_path, status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
