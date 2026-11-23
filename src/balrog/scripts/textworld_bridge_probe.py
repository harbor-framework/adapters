"""Compare the Harbor game bridge against every frozen native TextWorld trace."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("balrog_game_bridge", args.server)
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    manifest = json.loads(args.manifest.read_text())
    results = []
    for case in manifest["cases"]:
        oracle = case["oracle"]
        if oracle is None:
            raise ValueError(f"No native oracle: {case['episode']['task_id']}")
        episode = server.Episode(case["episode"], Path("/opt/balrog/balrog/config/config.yaml"))
        try:
            assert episode.max_steps == 80
            for index, action in enumerate(oracle["actions"]):
                episode.action(action, index)
            result = episode.result()
            normalized = [{
                "observation": step["observation_sha256"],
                "executed_action": step["executed_action"], "reward": step["reward"],
                "terminated": step["terminated"], "truncated": step["truncated"],
            } for step in result["transitions"]]
            assert normalized == oracle["expected_transitions"]
            assert result["progression"] == result["replay_progression"] == oracle["expected_progression"]
            assert result["replay_verified"] is True
            results.append({"task_id": result["task_id"], "steps": result["steps"], "progression": result["progression"], "native_trace_identical": True})
            print(json.dumps(results[-1]), flush=True)
        finally:
            episode.close()
    controls = []
    for case in manifest["cases"]:
        reference = case["reference"]
        if reference["within_native_budget"]:
            continue
        episode = server.Episode(case["episode"], Path("/opt/balrog/balrog/config/config.yaml"))
        try:
            for index, action in enumerate(reference["actions"][:80]):
                episode.action(action, index)
            result = episode.result()
            assert result["progression"] == reference["native_progression"]
            assert result["progression"] < 1.0
            assert result["max_steps"] == result["steps"] == 80
            controls.append({"task_id": result["task_id"], "steps": 80, "native_partial_progression": result["progression"], "replay_verified": result["replay_verified"]})
        finally:
            episode.close()
    report = {"passed": len(results), "total": len(manifest["cases"]), "uid": os.getuid(), "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(), "game_server_sha256": hashlib.sha256(args.server.read_bytes()).hexdigest(), "matched_transitions": sum(result["steps"] for result in results), "cases": results, "unshortened_walkthrough_budget_controls": controls}
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
