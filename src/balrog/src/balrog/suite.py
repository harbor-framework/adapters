"""Generate frozen cases for all six BALROG environments without changing scores."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import tempfile

from .adapter import (BALROG_COMMIT, PACKAGE_DIR, _check_plain_tree, _is_link,
                      _source_archive, _write_json, load_manifest)
from .runtime_locks import stage_runtime_lock

ENVIRONMENTS = ("babyai", "babaisai", "textworld", "crafter", "nle", "minihack")
COUNTS = {"babyai": 50, "babaisai": 120, "textworld": 30, "crafter": 10, "nle": 5, "minihack": 40}
SEEDS = {"babyai": 10, "babaisai": 3, "textworld": 10, "crafter": 10, "nle": 5, "minihack": 5}


def load_environment_manifest(env_name: str) -> dict:
    if env_name == "babyai":
        return load_manifest()
    if env_name not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {env_name}")
    path = PACKAGE_DIR / "fixtures" / f"{env_name}_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    scope = json.loads((PACKAGE_DIR / "fixtures/suite_scope.json").read_text(encoding="utf-8"))[env_name]
    cases = manifest.get("cases", [])
    if manifest.get("schema_version") != 1 or manifest.get("source_commits") != scope["source_commits"]:
        raise ValueError(f"Wrong manifest schema/source revisions in {path.name}")
    if len(cases) != COUNTS[env_name]:
        raise ValueError(f"Incomplete {env_name} scope: expected {COUNTS[env_name]} cases")
    pairs, ids = set(), set()
    for case in cases:
        ep = case["episode"]
        name, seed, task = ep["task_id"], ep["seed"], ep["task"]
        if ep.get("env_name") != env_name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError("Invalid environment or task ID")
        if type(seed) is not int or seed not in range(SEEDS[env_name]) or task not in scope["tasks"]:
            raise ValueError("Unexpected frozen task/seed")
        if name in ids or (task, seed) in pairs:
            raise ValueError("Duplicate frozen case")
        pairs.add((task, seed))
        ids.add(name)
        if type(ep.get("expected_max_steps")) is not int or ep["expected_max_steps"] != scope["max_steps"]:
            raise ValueError("Missing native step budget")
        if not re.fullmatch(r"[0-9a-f]{64}", ep.get("expected_initial_observation_sha256", "")):
            raise ValueError("Missing frozen initial observation hash")
    if {task for task, _ in pairs} != set(scope["tasks"]):
        raise ValueError("Manifest does not cover the original configured task families")
    for task in scope["tasks"]:
        if {(task, seed) for seed in range(SEEDS[env_name])} - pairs:
            raise ValueError("Outcome filtering or missing seeds in scope")
    return manifest


def select_suite_cases(environments, split="full", task_ids=None, limit=None):
    if not environments or len(environments) != len(set(environments)):
        raise ValueError("Select nonempty, unique environments")
    if "all" in environments and environments != ["all"]:
        raise ValueError("Use all alone, without other environment names")
    names = list(ENVIRONMENTS) if environments == ["all"] else environments
    if split not in {"full", "parity", "sanity"} or (limit is not None and limit < 0):
        raise ValueError("Invalid split or limit")
    cases = []
    for env_name in names:
        for original in load_environment_manifest(env_name)["cases"]:
            case = {**original, "episode": {"env_name": env_name, **original["episode"]}}
            if split != "sanity" or case["episode"]["seed"] == 0:
                cases.append(case)
    if task_ids:
        unknown = set(task_ids) - {c["episode"]["task_id"] for c in cases}
        if unknown:
            raise ValueError(f"Task IDs outside selected environments/split: {sorted(unknown)}")
        cases = [c for c in cases if c["episode"]["task_id"] in task_ids]
    return cases if limit is None else cases[:limit]


def instruction(env_name):
    return f"""Play the {env_name} task in the running BALROG game.

Run `balrog observe` to read the original task instructions, available actions,
current text observation and native action budget. Execute one action at a time:

    balrog act "ACTION_FROM_THE_ORIGINAL_INSTRUCTIONS"

Use the exact action strings from the game instructions. Every action returns
the updated observation and whether the episode has ended. There is one episode
and no reset endpoint. Stop when `done` is true.

Evaluation uses the original BALROG progression metric for this environment,
on a scale from 0 to 1, and independently replays the recorded actions. Partial
progress is preserved where the native benchmark awards it. Interact with the
game to submit your work; writing an answer or reward file does not submit actions.
"""


REFERENCE_SCRIPT = '''"""Replay a validated reference through the public action endpoint."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
payload = json.loads(Path("/solution/oracle_actions.json").read_text())
if not isinstance(payload, dict) or not payload.get("actions"):
    raise RuntimeError("No validated oracle/reference is available for this task yet")
with urlopen("http://game:8080/observation", timeout=30) as response:
    observation = json.load(response)
for action in payload["actions"]:
    if observation["done"]:
        raise RuntimeError("Episode ended before all reference actions were consumed")
    req = Request("http://game:8080/action", data=json.dumps({"action": action, "expected_step": observation["step"]}).encode(), headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=60) as response:
        observation = json.load(response)
print(json.dumps({"steps": observation["step"], "terminated": observation["terminated"], "reference_kind": payload.get("kind", "oracle")}))
'''


def generate_suite(adapter):
    cases = select_suite_cases(adapter.environments, adapter.split, adapter.task_ids, adapter.limit)
    if not cases:
        return []
    output = adapter.output_dir.expanduser().absolute()
    if any(_is_link(p) for p in (output, *output.parents)):
        raise ValueError("Refusing output path through symlink/junction")
    output = output.resolve()
    destinations = [adapter._check_destination(output, c["episode"]["task_id"]) for c in cases]
    template = PACKAGE_DIR / "task-template"
    _check_plain_tree(template)
    source_lock = json.loads((PACKAGE_DIR / "fixtures/runtime_sources.json").read_text())
    assets_dir = adapter.assets_dir or Path(adapter.benchmark_source).parent / "benchmark-assets"
    assets_dir = Path(assets_dir).resolve()
    balrog_archive = _source_archive(Path(adapter.benchmark_source), BALROG_COMMIT)
    archives = {"balrog.tar.gz": balrog_archive}
    needed_names = {c["episode"]["env_name"] for c in cases}
    for env_name in needed_names - {"babyai"}:
        for resource in source_lock[env_name]:
            source = (assets_dir / resource["path"]).resolve()
            if not source.is_relative_to(assets_dir):
                raise ValueError("Source archive escapes assets directory")
            content = source.read_bytes()
            if hashlib.sha256(content).hexdigest() != resource["sha256"]:
                raise ValueError(f"Pinned source/asset checksum mismatch: {source}")
            archives[resource["archive"]] = content
    if "babyai" in needed_names:
        from .adapter import MINIGRID_COMMIT
        archives["minigrid.tar.gz"] = _source_archive(Path(adapter.minigrid_source), MINIGRID_COMMIT)
    output.mkdir(parents=True, exist_ok=True)
    for case, destination in zip(cases, destinations):
        ep = case["episode"]
        env_name, task_id = ep["env_name"], ep["task_id"]
        replacements = {"__TASK_ID__": task_id, "__RESULT_TOKEN__": secrets.token_hex(32)}
        with tempfile.TemporaryDirectory(prefix=f".{task_id}-", dir=output) as temporary:
            staged = Path(temporary) / task_id
            shutil.copytree(template, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for path in staged.rglob("*"):
                if path.is_file():
                    content = path.read_text(encoding="utf-8")
                    for key, value in replacements.items():
                        content = content.replace(key, value)
                    path.write_text(content, encoding="utf-8", newline="\n")
            if env_name != "babyai":
                shutil.copyfile(PACKAGE_DIR / "runtime-dockerfiles" / f"{env_name}.Dockerfile", staged / "environment/Dockerfile.game")
                (staged / "instruction.md").write_text(instruction(env_name), encoding="utf-8", newline="\n")
                (staged / "solution/replay_oracle.py").write_text(REFERENCE_SCRIPT, encoding="utf-8", newline="\n")
                config = (staged / "task.toml").read_text(encoding="utf-8")
                config = config.replace('"babyai"', json.dumps(env_name)).replace('difficulty = "easy"', 'difficulty = "hard"')
                config = config.replace("timeout_sec = 300.0", "timeout_sec = 1800.0")
                config = config.replace("timeout_sec = 120.0", "timeout_sec = 1800.0")
                config = config.replace("--request-timeout 100", "--request-timeout 1700")
                config = config.replace("build_timeout_sec = 900.0", "build_timeout_sec = 1800.0")
                config = config.replace("memory_mb = 1024", "memory_mb = 2048").replace("storage_mb = 2048", "storage_mb = 4096")
                (staged / "task.toml").write_text(config, encoding="utf-8", newline="\n")
            stage_runtime_lock(PACKAGE_DIR, env_name, staged / "environment")
            vendor = staged / "environment/vendor"
            vendor.mkdir()
            selected = ["balrog.tar.gz"] + (["minigrid.tar.gz"] if env_name == "babyai" else [r["archive"] for r in source_lock[env_name]])
            metadata = {}
            for archive in selected:
                (vendor / archive).write_bytes(archives[archive])
                metadata[archive] = {"sha256": hashlib.sha256(archives[archive]).hexdigest()}
            _write_json(vendor / "manifest.json", {"balrog_commit": BALROG_COMMIT, "archives": metadata, "sources": source_lock.get(env_name, [])})
            _write_json(staged / "environment/episode.json", ep)
            _write_json(staged / "tests/task_config.json", ep)
            reference = case.get("oracle") or case.get("reference")
            if reference is None and case.get("native_probe", {}).get("transitions_replay_equal") is True:
                probe = case["native_probe"]
                reference = {"kind": "native_smoke_diagnostic_not_full_oracle",
                             "actions": probe["actions"], "expected_progression": probe["final_progression"]}
            _write_json(staged / "solution/oracle_actions.json", reference)
            _write_json(staged / "solution/reference_status.json", {
                "full_oracle_available": bool(case.get("oracle") and case["oracle"].get("expected_progression") == 1.0),
                "reference_available": bool(reference),
                "expected_progression": reference.get("expected_progression") if reference else None,
            })
            adapter._check_destination(output, task_id)
            if destination.exists():
                shutil.rmtree(destination)
            staged.rename(destination)
    return destinations
