"""Score trusted runtime progress; transport failures are verifier errors, not zero scores."""

import argparse
import json
import os
from pathlib import Path
from urllib.request import urlopen


def reward(progress, baseline_actions, total_levels, start_level=0):
    actions_per_level = progress.get("actions_per_level", [])
    n_levels = max(total_levels, len(actions_per_level))
    efficiency = 0.0
    if n_levels > 0 and actions_per_level:
        denom = sum(range(1, n_levels + 1))
        numer = 0.0
        for idx, actions in enumerate(actions_per_level):
            baseline = baseline_actions[idx] if idx < len(baseline_actions) else 1
            ratio = min(baseline / max(actions, 1), 1.0)
            numer += (idx + 1) * ratio**2
        efficiency = numer / denom
    return {
        "score": max(0, progress.get("levels_completed", 0) - start_level),
        "is_win": int(str(progress.get("state", "")).strip().lower() == "win"),
        "efficiency": round(efficiency, 4),
    }


def verify(runtime_url, scoring_path, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    # Never leave stale success behind after a failed verification.
    for name in ("reward.json", "reward.txt"):
        (output_dir / name).unlink(missing_ok=True)
    try:
        scoring = json.loads(scoring_path.read_text())

        def get(path):
            with urlopen(f"{runtime_url.rstrip('/')}/{path}", timeout=10) as response:
                payload = json.load(response)
            if payload.get("ok") is not True:
                raise ValueError(f"Runtime rejected {path}")
            return payload

        health = get("health")
        if health.get("game_id") != scoring["game_id"]:
            raise ValueError("Verifier and runtime game IDs differ")
        log = get("action_log")["action_log"]
        progress = log[-1] if log else get("progress")
        if progress.get("state") not in {"not_finished", "game_over", "win"}:
            raise ValueError("Missing or invalid game state")
        if "levels_completed" not in progress or "total_actions" not in progress:
            raise ValueError("Missing runtime progress")
        result = reward(
            progress,
            scoring["baseline_actions"],
            len(scoring["baseline_actions"]),
            int(os.environ.get("ARC_START_LEVEL", "0")),
        )
    except Exception as exc:
        (output_dir / "metrics.json").write_text(
            json.dumps({"state": "error", "error": f"{type(exc).__name__}: {exc}"}) + "\n"
        )
        raise
    (output_dir / "reward.json").write_text(json.dumps(result, indent=2) + "\n")
    (output_dir / "metrics.json").write_text(
        json.dumps({"state": progress["state"], "total_actions": progress["total_actions"]}) + "\n"
    )
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-url", default=os.environ.get("ARC_RUNTIME_API_BASE", "http://game:8000")
    )
    parser.add_argument("--scoring", type=Path, default=Path(__file__).with_name("scoring.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    verify(args.runtime_url, args.scoring, args.output_dir)
