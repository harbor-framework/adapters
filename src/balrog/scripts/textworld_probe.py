"""Probe all 30 predetermined native BALROG TextWorld cases without model calls."""

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import random
import sys
import traceback

import numpy as np
from omegaconf import OmegaConf
import textworld

from balrog.environments import make_env


FAMILIES = ("treasure_hunter", "the_cooking_game", "coin_collector")
ROOT = Path("/opt/balrog")
ASSET_ROOT = ROOT / "tw_games"
CONFIG = ROOT / "balrog/config/config.yaml"
SOURCE_MANIFEST = Path("/app/source_manifest.json")


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def observation_hash(observation):
    value = {"text": observation["text"], "mission": observation.get("mission")}
    return digest_bytes(json.dumps(value, sort_keys=True).encode())


def catalog():
    # Match TextWorldFactory: globally sorted .ulx games, then sorted .z8 games.
    result = {name: [] for name in FAMILIES}
    for extension in ("*.ulx", "*.z8"):
        for path in sorted(ASSET_ROOT.rglob(extension)):
            if path.parent.name in result:
                result[path.parent.name].append(path)
    return result


def run_episode(task, seed, actions, game_path):
    config = OmegaConf.load(CONFIG)
    config.envs.env_kwargs.seed = seed
    random.seed(seed)
    np.random.seed(seed)
    env = make_env("textworld", task, config)
    try:
        native_files = env.env.gym_env.env.gamefiles
        if native_files != [str(game_path)]:
            raise ValueError(f"Native asset selection differs: {native_files}")
        observation, _ = env.reset(seed=seed)
        result = {
            "initial_observation": observation_hash(observation),
            "initial_progression": float(env.get_stats()["progression"]),
            "max_steps": int(env.max_steps),
            "instruction_sha256": digest_bytes(env.get_instruction_prompt().encode()),
            "actions": [], "transitions": [], "native_infos": [],
        }
        for action in actions[:env.max_steps]:
            executed = env.check_action_validity(action)
            observation, reward, terminated, truncated, info = env.step(executed)
            result["actions"].append(action)
            result["transitions"].append({
                "observation": observation_hash(observation),
                "executed_action": executed, "reward": float(reward),
                "terminated": bool(terminated), "truncated": bool(truncated),
            })
            result["native_infos"].append({
                key: info.get(key) for key in ("score", "max_score", "won")
            })
            if terminated or truncated:
                break
        result["progression"] = float(env.get_stats()["progression"])
        result["success"] = result["progression"] == 1.0
        return result
    finally:
        env.close()


def shorten_walkthrough(actions):
    """Remove only redundant door opens and adjacent drop/take-knife roundtrips.

    This constructs a reference policy; it does not change game code or limits.
    Native successful replay is required before calling it an oracle.
    """
    shortened, removed, opened = [], [], set()
    index = 0
    while index < len(actions):
        command = actions[index]
        if command == "drop knife" and index + 1 < len(actions) and actions[index + 1] == "take knife":
            removed.extend([{"index": index, "action": command, "reason": "adjacent knife roundtrip"},
                            {"index": index + 1, "action": actions[index + 1], "reason": "adjacent knife roundtrip"}])
            index += 2
            continue
        if command.startswith("open "):
            obj = command.removeprefix("open ")
            if obj in opened:
                removed.append({"index": index, "action": command, "reason": "repeated door open without intervening close"})
                index += 1
                continue
            opened.add(obj)
        if command.startswith("close "):
            opened.discard(command.removeprefix("close "))
        shortened.append(command)
        index += 1
    return shortened, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("/results"))
    parser.add_argument("--replay-manifest", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    games = catalog()
    sources = json.loads(SOURCE_MANIFEST.read_text())
    config = OmegaConf.load(CONFIG)
    kwargs = OmegaConf.to_container(config.envs.textworld_kwargs, resolve=True)
    if tuple(config.tasks.textworld_tasks) != FAMILIES or kwargs["max_episode_steps"] != 80:
        raise ValueError("Pinned TextWorld configuration differs")
    replay_manifest = json.loads(args.replay_manifest.read_text()) if args.replay_manifest else None
    replay_cases = {(case["episode"]["task"], case["episode"]["seed"]): case for case in replay_manifest["cases"]} if replay_manifest else {}
    cases, records = [], []
    for seed in range(10):
        for task in FAMILIES:
            task_id = f"textworld-{task.replace('_', '-')}-seed-{seed}"
            selected = games[task][seed % len(games[task])]
            metadata_path = selected.with_suffix(".json")
            metadata = json.loads(metadata_path.read_text())
            actions = metadata["metadata"].get("walkthrough")
            episode = {
                "task_id": task_id, "env_name": "textworld", "task": task, "seed": seed,
                "textworld_kwargs": copy.deepcopy(kwargs), "expected_max_steps": 80,
                "assets": {
                    "source_commit": sources["assets"]["commit"],
                    "catalog_size": len(games[task]), "selected_index": seed % len(games[task]),
                    "game_file": selected.relative_to(ROOT).as_posix(),
                    "game_sha256": digest_bytes(selected.read_bytes()),
                    "metadata_file": metadata_path.relative_to(ROOT).as_posix(),
                    "metadata_sha256": digest_bytes(metadata_path.read_bytes()),
                },
            }
            case = {"episode": episode, "oracle": None}
            record = {"task_id": task_id, "passed": False}
            try:
                if replay_manifest:
                    frozen = replay_cases[(task, seed)]
                    if frozen["oracle"] is None:
                        raise ValueError("Frozen case lacks a validated oracle")
                    replay = run_episode(task, seed, frozen["oracle"]["actions"], selected)
                    assert replay["initial_observation"] == frozen["episode"]["expected_initial_observation_sha256"]
                    assert replay["instruction_sha256"] == frozen["episode"]["expected_instruction_sha256"]
                    assert replay["transitions"] == frozen["oracle"]["expected_transitions"]
                    assert replay["progression"] == frozen["oracle"]["expected_progression"] == 1.0
                    case = frozen
                    record.update(passed=True, cross_process_identical=True, steps=len(replay["actions"]))
                else:
                    if not actions:
                        raise ValueError("Upstream metadata has no walkthrough")
                    original = run_episode(task, seed, actions, selected)
                    episode["expected_initial_observation_sha256"] = original["initial_observation"]
                    episode["expected_instruction_sha256"] = original["instruction_sha256"]
                    case["reference"] = {
                        "source": "upstream game JSON metadata.walkthrough",
                        "walkthrough_length": len(actions),
                        "actions": actions,
                        "native_steps": len(original["actions"]),
                        "native_progression": original["progression"],
                        "native_success": original["success"],
                        "within_native_budget": len(actions) <= original["max_steps"],
                    }
                    chosen, source = original, "upstream_walkthrough"
                    removed = []
                    if not original["success"]:
                        shortened, removed = shorten_walkthrough(actions)
                        chosen = run_episode(task, seed, shortened, selected)
                        source = "upstream_walkthrough_without_redundant_commands"
                    replay = run_episode(task, seed, chosen["actions"], selected)
                    identical = chosen == replay
                    record.update(original_progression=original["progression"], original_walkthrough_length=len(actions),
                                  progression=chosen["progression"], steps=len(chosen["actions"]), replay_identical=identical)
                    if chosen["success"] and identical:
                        case["oracle"] = {
                            "actions": chosen["actions"],
                            "expected_initial_observation_sha256": chosen["initial_observation"],
                            "expected_transitions": chosen["transitions"],
                            "expected_progression": chosen["progression"],
                            "source": source, "removed_reference_commands": removed,
                        }
                        record["passed"] = True
                    else:
                        case["diagnostic"] = {"reason": "Reference policy did not reach progression 1 within native budget or replay diverged", "attempt": chosen}
            except Exception as exc:
                record.update(error_type=type(exc).__name__, error=str(exc))
                case["diagnostic"] = {"error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}
            cases.append(case)
            records.append(record)
            print(json.dumps(record), flush=True)
    ids = [case["episode"]["task_id"] for case in cases]
    manifest = {
        "schema_version": 1, "scope": "BALROG TextWorld three configured families x predetermined seeds 0..9",
        "selection": "All three configured families and all seeds 0..9; no outcome filtering or replacement",
        "source_commits": {name: item["commit"] for name, item in sources.items() if "commit" in item},
        "asset_catalog": {name: [p.relative_to(ROOT).as_posix() for p in paths] for name, paths in games.items()},
        "original_asset_archive": sources["original_asset_archive"],
        "splits": {"full": ids, "parity": ids, "sanity": ids[:3]}, "cases": cases,
    }
    report = {
        "scope": "Native Linux Docker environment, reference oracle, and independent fresh-instance replay; no model API",
        "passed": sum(record["passed"] for record in records), "total": len(records),
        "python": sys.version, "platform": platform.platform(), "textworld_version": textworld.__version__,
        "uid": os.getuid(),
        "requirements": Path("/opt/runtime-requirements.txt").read_text().splitlines(),
        "source_commits": manifest["source_commits"], "cases": records,
        "source_archive_sha256": {name: item["archive_sha256"] for name, item in sources.items() if "archive_sha256" in item},
    }
    report_name = "textworld_cross_process_replay.json" if replay_manifest else "textworld_probe_results.json"
    (args.output_dir / report_name).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not replay_manifest:
        (args.output_dir / "textworld_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"RESULT: {report['passed']}/{report['total']}", flush=True)
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
