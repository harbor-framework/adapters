"""Recompute native G/P/F in a fresh verifier container from sidecar evidence."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


def grade(evidence, source, upstream):
    for key in ("task_id", "upstream_commit", "archive_sha256"):
        expected = source["commit"] if key == "upstream_commit" else source[key]
        if evidence.get(key) != expected:
            raise ValueError(f"Evidence identity mismatch: {key}")
    if evidence.get("schema_version") != 1:
        raise ValueError("Unsupported evidence schema")
    sys.path[:0] = [str(upstream), str(upstream / "third_party/tau2-bench/src")]
    from payment.runtime.tasks.contracts import read_contract
    from payment.runtime.evaluation.runner import verify
    result = evidence["result"]
    # Compare the complete verdict in its transport representation. Native
    # evidence can contain tuples, which JSON necessarily transports as lists.
    verdict = json.loads(json.dumps(verify(
        evidence["world"], read_contract(source["task_id"], upstream / "payment/data")
    )))
    if verdict != result.get("verification"):
        raise ValueError("Native sidecar/verifier scoring mismatch")
    if result.get("task_id") != source["task_id"]:
        raise ValueError("Native result belongs to a different task")
    if verdict.get("valid_run") is False or result.get("reward") is None:
        raise ValueError("Unscored upstream run: " + result.get("classification", "unknown"))
    if result.get("classification") == "evaluator_replay_mismatch":
        raise ValueError("Upstream replay mismatch")
    reward = result["reward"]
    if type(reward) not in (int, float) or not math.isfinite(reward):
        raise ValueError("Invalid native reward")
    if reward != float(verdict["strict_success"]):
        raise ValueError("Native reward differs from Strict")
    return float(reward), verdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=Path("/private/runs/evidence.json"))
    parser.add_argument("--source", type=Path, default=Path("/tests/source.json"))
    parser.add_argument("--upstream", type=Path, default=Path("/opt/bizagentbench"))
    parser.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for filename in ("reward.txt", "reward.json", "error.json", "result.json"):
        (args.output / filename).unlink(missing_ok=True)
    try:
        evidence = json.loads(args.evidence.read_text("utf-8"))
        source = json.loads(args.source.read_text("utf-8"))
        reward, verdict = grade(evidence, source, args.upstream)
        (args.output / "result.json").write_text(json.dumps({
            "reward": reward, "verification": verdict,
            "classification": evidence["result"]["classification"],
            "task_id": source["task_id"],
        }, indent=2), "utf-8")
        (args.output / "reward.txt").write_text(f"{reward:g}\n", "utf-8")
        return 0
    except Exception as exc:
        (args.output / "error.json").write_text(json.dumps({
            "error_class": type(exc).__name__, "error": str(exc),
        }, indent=2), "utf-8")
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
