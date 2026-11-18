"""Read the protected native score; infrastructure failures produce no reward."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen


def validate_result(result):
    if not isinstance(result, dict) or result.get("schema_version") != 1:
        raise ValueError("Unexpected result schema")
    if result.get("finalized") is not True:
        raise ValueError("Missing finalized")
    env_name = result.get("env_name", "babyai")
    score = result.get("progression")
    if type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError("Invalid progression")
    for key in ("terminated", "truncated"):
        if type(result.get(key)) is not bool:
            raise ValueError(f"Invalid {key}")
    steps, max_steps = result.get("steps"), result.get("max_steps")
    if type(steps) is not int or type(max_steps) is not int or not 0 <= steps <= max_steps:
        raise ValueError("Invalid step counts")
    if not isinstance(result.get("transitions"), list) or len(result["transitions"]) != steps:
        raise ValueError("Invalid transition record")
    if env_name not in {"babyai", "babaisai", "textworld", "crafter", "minihack", "nle"}:
        raise ValueError("Unknown BALROG environment")
    if result.get("replay_verified") is True:
        if score != result.get("replay_progression"):
            raise ValueError("Replay score mismatch")
    else:
        diagnostic = result.get("replay_diagnostic") or {}
        divergence = diagnostic.get("first_divergent_step")
        if not (env_name == "crafter" and result.get("replay_verified") is False
                and result.get("scoring_mode") == "authoritative_native_state"
                and "replay_progression" in result
                and result.get("replay_progression") is None
                and diagnostic.get("code") == "crafter_native_object_order_nondeterminism"
                and type(divergence) is int and 0 <= divergence <= steps):
            raise ValueError("Missing verified replay or explicit Crafter native-state evidence")
    if env_name == "babyai" and score > 0 and not result["terminated"]:
        raise ValueError("Successful BabyAI episode must have terminated")
    return float(score)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=os.environ.get("BALROG_SERVER", "http://game:8080"))
    parser.add_argument("--output-dir", type=Path, default=Path("/logs/verifier"))
    parser.add_argument("--request-timeout", type=float, default=float(os.environ.get("BALROG_VERIFIER_TIMEOUT", "60")))
    args = parser.parse_args()
    if not math.isfinite(args.request_timeout) or args.request_timeout <= 0:
        parser.error("Verifier request timeout must be positive and finite")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reward_path = args.output_dir / "reward.txt"
    reward_path.unlink(missing_ok=True)
    # Harbor also recognizes reward.json; never leave an older/forged alternate
    # reward behind when the current trusted verification fails.
    (args.output_dir / "reward.json").unlink(missing_ok=True)
    try:
        token = os.environ.get("RESULT_TOKEN")
        if not token:
            raise ValueError("RESULT_TOKEN is required by the verifier")
        req = Request(args.server.rstrip("/") + "/result", headers={"Authorization": "Bearer " + token})
        with urlopen(req, timeout=args.request_timeout) as response:
            result = json.load(response)
        score = validate_result(result)
        (args.output_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        reward_path.write_text(f"{score:.17g}\n", encoding="utf-8")
        print(f"BALROG {result.get('env_name', 'babyai')} progression={score:g}; replay_verified={result['replay_verified']}; steps={result['steps']}")
        # A valid failed task is scored 0, not an infrastructure failure.
        return 0
    except Exception as exc:
        (args.output_dir / "error.json").write_text(
            json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, indent=2), encoding="utf-8"
        )
        print(f"BALROG verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
