"""Freeze and solve predetermined Baba Is AI cases with native actions, no LLM."""
from __future__ import annotations
import argparse
import copy
import hashlib
import heapq
import itertools
import importlib
import json
import os
from pathlib import Path
import random
import re
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[1]
BALROG_SOURCE = Path(os.environ.get("BALROG_SOURCE", "/opt/balrog"))
BABA_SOURCE = Path(os.environ.get("BABA_SOURCE", "/opt/baba"))
sys.path[:0] = [str(BALROG_SOURCE), str(BABA_SOURCE)]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import numpy as np
from omegaconf import OmegaConf
from balrog.environments import make_env

# The upstream package initializer eagerly imports the unrelated Linux-only NLE
# wrapper. Load the untouched compatibility implementation in a package shell
# for this Windows-only probe; no Baba reset/step/scoring code is replaced.
if os.environ.get("BABA_WINDOWS_IMPORT_SHIM") == "1":
    if sys.platform != "win32":
        raise RuntimeError("The Windows import shim is prohibited for Linux verification")
    wrapper_package = types.ModuleType("balrog.environments.wrappers")
    wrapper_package.__path__ = [str(BALROG_SOURCE / "balrog/environments/wrappers")]
    sys.modules[wrapper_package.__name__] = wrapper_package
    wrapper_package.GymV21CompatibilityV0 = importlib.import_module(
        "balrog.environments.wrappers.gym_compatibility").GymV21CompatibilityV0

SOURCE_COMMITS = {"balrog": "b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5",
                  "baba": "40ae1b29dbc67f2ecea06cc161ed5ca51719e5e3"}
CONFIG = BALROG_SOURCE / "balrog/config/config.yaml"
ACTIONS = ("up", "right", "down", "left")
DELTA = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}


def obs_hash(obs):
    return hashlib.sha256(json.dumps({"text": obs["text"], "mission": obs.get("mission")}, sort_keys=True).encode()).hexdigest()


def create(task, seed):
    config = OmegaConf.load(CONFIG)
    config.envs.env_kwargs.seed = seed
    random.seed(seed)
    np.random.seed(seed)
    env = make_env("babaisai", task, config)
    obs, _ = env.reset(seed=seed)
    return env, obs


def raw_env(env):
    return env.env.gym_env.env


def visible_objects(env):
    return [(i % env.width, i // env.width, obj) for i, cell in enumerate(env.grid.grid)
            for obj in cell if obj is not None]


def copy_state(env):
    other = copy.copy(env)
    memo = {}
    for _, _, obj in visible_objects(env):
        if getattr(obj, "type", "") == "wall":
            memo[id(obj)] = obj
        if hasattr(obj, "img"):
            memo[id(obj.img)] = obj.img
    other.grid, other._ruleset = copy.deepcopy((env.grid, env._ruleset), memo)
    other.agent_pos = np.array(env.agent_pos).copy()
    return other


def state_key(env):
    return tuple(tuple((obj.type, obj.color, getattr(obj, "name", None),
                        getattr(obj, "property", None), getattr(obj, "_is_push", None))
                       for obj in cell if obj is not None) for cell in env.grid.grid)


def positions(env, kind=None, name=None):
    return [(x, y) for x, y, obj in visible_objects(env)
            if (kind is None or obj.type == kind) and (name is None or getattr(obj, "name", None) == name)]


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def has_rule(env, subject, prop):
    subject = subject if subject == "baba" else "f" + subject.removeprefix("f")
    return any(rule.get("object") == subject and rule.get("property") == prop
               for rule in env.grid._ruleset["_rule_"])


def search(env, goal, heuristic, *, max_nodes=30000, max_seconds=45, avoid_rule_changes=False):
    """Weighted A* on true upstream step transitions; never edit a live state."""
    start = time.monotonic()
    counter = itertools.count()
    queue = [(heuristic(env), 0, next(counter), env, ())]
    visited = {state_key(env): 0}
    expanded = 0
    while queue and expanded < max_nodes and time.monotonic() - start < max_seconds:
        _, distance, _, current, path = heapq.heappop(queue)
        if visited[state_key(current)] < distance:
            continue
        if goal(current):
            return current, path, {"expanded": expanded, "seconds": time.monotonic() - start}
        if current.step_count >= current.max_steps:
            continue
        expanded += 1
        for action in ACTIONS:
            child = copy_state(current)
            try:
                _, reward, done, _ = child.step(getattr(child.actions, action))
            except (AssertionError, IndexError, RecursionError):
                continue
            # Losing all YOU objects triggers the native BALROG wrapper reset.
            # Do not use such resets as an oracle shortcut to a different puzzle.
            if not any(obj.is_agent() for _, _, obj in visible_objects(child)):
                continue
            if done and reward <= 0:
                continue
            key = state_key(child)
            candidate_distance = distance + 1
            if visited.get(key, 10**9) <= candidate_distance:
                continue
            visited[key] = candidate_distance
            heapq.heappush(queue, (candidate_distance + 3 * heuristic(child), candidate_distance,
                                  next(counter), child, path + (action,)))
    return None, (), {"expanded": expanded, "seconds": time.monotonic() - start,
                      "reason": "budget" if queue else "exhausted"}


def agent_positions(env):
    return [(x, y) for x, y, obj in visible_objects(env) if obj.is_agent()]


def solve(task, seed, seconds=45):
    env, _ = create(task, seed)
    try:
        current = copy_state(raw_env(env))
        plan = env.get_stats()["target_plan"]
        stages = re.findall(r"(make|break|goto)\[([^\]]+)\]", plan)
        actions = ()
        trace = []
        for operation, argument in stages:
            if operation == "goto":
                def goal(state):
                    return bool(getattr(state, "is_win", False))
                def heuristic(state):
                    goals = [(x, y) for x, y, obj in visible_objects(state) if obj.is_goal()]
                    return min((manhattan(a, b) for a in agent_positions(state) for b in goals), default=100)
            else:
                subject, property_name = argument.split(" is ")
                prop = {"win": "is_goal", "you": "is_agent", "stop": "is_stop"}[property_name]
                if operation == "break":
                    def goal(state, subject=subject, prop=prop):
                        return not has_rule(state, subject, prop)
                    def heuristic(state):
                        blocks = [(x, y) for x, y, obj in visible_objects(state)
                                  if obj.type.startswith("rule_") and getattr(obj, "name", None) in {subject, "is", property_name}]
                        return min((manhattan(a, b) for a in agent_positions(state) for b in blocks), default=100)
                else:
                    def goal(state, subject=subject, prop=prop):
                        return has_rule(state, subject, prop)
                    targets = []
                    for x, y, obj in visible_objects(current):
                        if obj.type != "rule_is":
                            continue
                        for dx, dy in ((1, 0), (0, 1)):
                            next_obj = current.grid.get(x + dx, y + dy)
                            if next_obj is not None and getattr(next_obj, "name", None) == property_name:
                                targets.append((x - dx, y - dy))
                    if not targets:
                        return None, {"stages": trace, "error": "No existing IS-property pair", "stage": argument}
                    # A subject destined for the top row can become trapped by
                    # other rule blocks if raised too early. First place it one
                    # row below its slot using the same native transition search.
                    if subject == "wall" and property_name == "win" and targets[0][1] == 1:
                        waypoint = (targets[0][0], 2)
                        def waypoint_goal(state):
                            return waypoint in positions(state, "rule_object", subject)
                        def waypoint_heuristic(state):
                            return min((2 * manhattan(block, waypoint)
                                        + max(0, min(manhattan(agent, block) for agent in agent_positions(state)) - 1)
                                        for block in positions(state, "rule_object", subject)), default=100)
                        end, route, stats = search(current, waypoint_goal, waypoint_heuristic, max_seconds=seconds)
                        trace.append({"operation": "position_subject", "argument": argument,
                                      "waypoint": waypoint, "steps": len(route), **stats})
                        if end is None:
                            return None, {"stages": trace, "error": "Subject routing search did not find a solution"}
                        current = end
                        actions += route
                    def heuristic(state, targets=targets, subject=subject):
                        if goal(state):
                            return 0
                        blocks = positions(state, "rule_object", subject)
                        return min((2 * manhattan(block, target)
                                    + max(0, min(manhattan(agent, block) for agent in agent_positions(state)) - 1)
                                    for block in blocks for target in targets), default=100)
            end, stage_actions, stats = search(current, goal, heuristic, max_seconds=seconds)
            trace.append({"operation": operation, "argument": argument, "steps": len(stage_actions), **stats})
            if end is None:
                return None, {"stages": trace, "error": "Search did not find a solution"}
            current = end
            actions += stage_actions
        return actions, {"stages": trace, "planner_final_win": bool(getattr(current, "is_win", False))}
    finally:
        env.close()


def solve_manifest(source, output, seconds=45, limit=None, task_filter=None):
    result = json.loads(source.read_text(encoding="utf-8"))
    for index, case in enumerate(result["cases"]):
        if case.get("oracle_status") == "verified":
            continue
        if limit is not None and index >= limit:
            break
        if task_filter is not None and task_filter not in case["episode"]["task_id"]:
            continue
        episode = case["episode"]
        started = time.monotonic()
        try:
            actions, stats = solve(episode["task"], episode["seed"], seconds=seconds)
            case["search"] = stats
            if actions is None:
                case["oracle_status"] = "unresolved"
            else:
                original = replay(episode["task"], episode["seed"], actions)
                fresh = replay(episode["task"], episode["seed"], actions)
                if original != fresh or original["expected_progression"] != 1.0:
                    case["oracle_status"] = "replay_failed"
                    case["candidate_oracle"] = original
                else:
                    case["oracle"] = original
                    case["oracle_status"] = "verified"
                    case["fresh_replay_identical"] = True
        except Exception as exc:
            case["oracle_status"] = "error"
            case["error"] = type(exc).__name__ + ": " + str(exc)
        case["elapsed_seconds"] = time.monotonic() - started
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"index": index, "task_id": episode["task_id"], "status": case["oracle_status"],
                          "steps": len((case.get("oracle") or {}).get("actions", [])),
                          "elapsed": case["elapsed_seconds"], "error": case.get("error")}), flush=True)
    return result


def replay(task, seed, actions):
    env, obs = create(task, seed)
    try:
        initial_hash = obs_hash(obs)
        transitions = []
        for action in actions:
            executed = env.check_action_validity(action)
            obs, reward, terminated, truncated, _ = env.step(executed)
            transitions.append({"observation": obs_hash(obs), "executed_action": executed,
                                "reward": float(reward), "terminated": bool(terminated), "truncated": bool(truncated)})
            if terminated or truncated:
                break
        return {"actions": list(actions), "expected_initial_observation_sha256": initial_hash,
                "expected_transitions": transitions, "expected_progression": float(env.get_stats()["progression"])}
    finally:
        env.close()


def freeze(output):
    config = OmegaConf.load(CONFIG)
    cases = []
    for seed in range(3):
        for task in config.tasks.babaisai_tasks:
            env, obs = create(task, seed)
            raw = raw_env(env)
            episode = {"task_id": "babaisai-" + task.removeprefix("env/").replace("_", "-") + f"-seed-{seed}",
                       "env_name": "babaisai", "task": task, "seed": seed,
                       "babaisai_kwargs": {"add_ruleset": True}, "assets": [],
                       "expected_max_steps": int(env.max_steps), "expected_initial_observation_sha256": obs_hash(obs)}
            again, again_obs = create(task, seed)
            assert obs_hash(obs) == obs_hash(again_obs), (task, seed, "nondeterministic reset")
            cases.append({"episode": episode, "oracle": None, "oracle_status": "pending",
                          "research": {"target_plan": env.get_stats()["target_plan"], "grid": str(raw),
                                       "initial_observation": obs["text"], "initial_rules": dict(raw.init_rules)}})
            # init_rules can contain tuple keys, keep them only in readable form.
            cases[-1]["research"]["initial_rules"] = repr(raw.init_rules)
            env.close()
            again.close()
            print(episode["task_id"], flush=True)
    result = {"schema_version": 1, "source_commits": SOURCE_COMMITS,
              "scope": "All 40 configured Baba Is AI task types, seeds 0..2 predetermined before search",
              "selection": "No seed filtering or replacement", "cases": cases}
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def verify_manifest(source, output):
    """Require every frozen oracle and every transition to match two fresh envs."""
    import importlib.metadata
    manifest = json.loads(source.read_text(encoding="utf-8"))
    if manifest["source_commits"] != SOURCE_COMMITS:
        raise ValueError("Unexpected benchmark source pins")
    expected = [(task, seed) for seed in range(3)
                for task in OmegaConf.load(CONFIG).tasks.babaisai_tasks]
    actual = [(case["episode"]["task"], case["episode"]["seed"]) for case in manifest["cases"]]
    if actual != expected or len(expected) != 120:
        raise ValueError("Manifest must preserve all 40 configured types x seeds 0..2")
    report = {"schema_version": 1, "source_commits": SOURCE_COMMITS,
              "manifest_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "windows_import_shim": os.environ.get("BABA_WINDOWS_IMPORT_SHIM") == "1",
              "platform": sys.platform, "python": sys.version,
              "packages": {p: importlib.metadata.version(p) for p in
                           ("gym", "gymnasium", "numpy", "pillow", "pygame", "omegaconf")},
              "cases": [], "status": "running"}
    for case in manifest["cases"]:
        episode, oracle = case["episode"], case["oracle"]
        if oracle is None or oracle["expected_progression"] != 1.0:
            raise ValueError(f"Missing complete oracle: {episode['task_id']}")
        first = replay(episode["task"], episode["seed"], oracle["actions"])
        second = replay(episode["task"], episode["seed"], oracle["actions"])
        if first != oracle or second != oracle:
            raise AssertionError(f"Native replay mismatch: {episode['task_id']}")
        if first["expected_initial_observation_sha256"] != episode["expected_initial_observation_sha256"]:
            raise AssertionError(f"Initial observation mismatch: {episode['task_id']}")
        report["cases"].append({"task_id": episode["task_id"], "steps": len(oracle["actions"]),
                                "progression": first["expected_progression"], "fresh_replay_identical": True})
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report["cases"][-1]), flush=True)
    report["status"] = "passed"
    report["verified"] = len(report["cases"])
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--solve", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--seconds", type=int, default=45)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--task-filter")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.freeze:
        result = freeze(args.output)
        print(f"Frozen {len(result['cases'])} deterministic cases", flush=True)
    if args.solve:
        result = solve_manifest(args.solve, args.output, args.seconds, args.limit, args.task_filter)
        print({"verified": sum(c["oracle_status"] == "verified" for c in result["cases"]), "total": len(result["cases"])})
    if args.verify:
        verify_manifest(args.verify, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
