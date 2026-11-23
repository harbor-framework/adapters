"""Local parity selection and preflight helpers; no credentials or subprocesses."""

import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import tomllib
from urllib.parse import urlsplit


PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = PROJECT / "src/balrog"
ENVIRONMENTS = ("babyai", "babaisai", "textworld", "crafter", "nle", "minihack")
COUNTS = dict(zip(ENVIRONMENTS, (50, 120, 30, 10, 5, 40)))


def read_json(path):
    _assert_no_links(Path(path))
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_sha256(path):
    _assert_no_links(Path(path))
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _assert_no_links(path):
    for component in (path.absolute(), *path.absolute().parents):
        _require(not component.is_symlink() and not getattr(component, "is_junction", lambda: False)(),
                 "Input paths must not traverse symlinks or junctions")


def _episode_identity(value):
    return {"env_name": "babyai", **value}


def _ids(value, label):
    _require(isinstance(value, list) and value and all(isinstance(v, str) and
             re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", v) for v in value),
             f"{label} must be a nonempty JSON list of safe task IDs")
    _require(len(value) == len(set(value)), f"Duplicate task IDs in {label}")
    return value


def _manifest(package, environment):
    filename = "manifest.json" if environment == "babyai" else environment + "_manifest.json"
    path = Path(package) / "fixtures" / filename
    manifest = read_json(path)
    episodes = [{"env_name": environment, **case["episode"]} for case in manifest["cases"]]
    _ids([episode["task_id"] for episode in episodes], "manifest")
    _require(len(episodes) == COUNTS[environment] and
             all(e["env_name"] == environment for e in episodes), "Manifest environment/coverage mismatch")
    return episodes, {"manifest_sha256": file_sha256(path),
                      "manifest_path": str(path.resolve()), "source_commits": manifest.get("source_commits", {})}


def select_episodes(environment, split="sanity", *, selection_plan=None, task_ids_file=None, package=PACKAGE):
    """Select a per-environment slice; explicit plans are validated globally first.

    Without an explicit selector, sanity retains every seed-0 type (58 overall).
    A task-IDs file is a JSON list wholly within this environment and split.
    A plan is the full parity proposal schema, with all six manifests bound.
    """
    _require(environment in ENVIRONMENTS and split in {"sanity", "full", "parity"}, "Unknown environment or split")
    _require(not (selection_plan and task_ids_file), "Choose one explicit selection source")
    episodes, metadata = _manifest(package, environment)
    eligible = [e for e in episodes if split != "sanity" or e["seed"] == 0]
    selected_ids = [e["task_id"] for e in eligible]
    selection_mode = "legacy_seed_zero_per_type" if split == "sanity" else "full_manifest"
    provenance = {}
    if selection_plan:
        plan = read_json(selection_plan)
        scope = plan["scope"]
        _require(set(scope["environments"]) == set(ENVIRONMENTS), "Plan must declare exactly all six environments")
        all_ids, available = [], {}
        for env in ENVIRONMENTS:
            cases, pins = _manifest(package, env)
            ids = [e["task_id"] for e in cases]
            entry = scope["environments"][env]
            _require(_ids(entry["task_ids"], f"{env} plan scope") == ids and
                     entry["episodes"] == len(cases) and entry["manifest_sha256"] == pins["manifest_sha256"],
                     f"Plan scope or manifest hash differs for {env}")
            _require(entry["native_action_budget_per_full_run"] == sum(e["expected_max_steps"] for e in cases),
                     f"Plan native budget differs for {env}")
            all_ids += ids
            available.update({e["task_id"]: e for e in cases})
        _require(scope["episodes_per_full_run"] == len(all_ids) == 255, "Plan full scope is not 255 cases")
        sanity = _ids(scope["sanity_task_ids"], "plan sanity")
        _require(len(sanity) == scope["sanity_episodes_per_side"] and 5 <= len(sanity) <= 10,
                 "Plan sanity must declare 5-10 tasks")
        _require(set(sanity) <= set(all_ids), "Unknown task ID in plan sanity")
        _require({available[i]["env_name"] for i in sanity} == set(ENVIRONMENTS) and
                 all(available[i]["seed"] == 0 for i in sanity), "Plan sanity must span six environments at seed 0")
        global_ids = sanity if split == "sanity" else all_ids
        selected_ids = [i for i in global_ids if available[i]["env_name"] == environment]
        selection_mode = "selection_plan"
        provenance = {"selection_file_sha256": file_sha256(selection_plan),
                      "selection_plan_status": plan.get("status"),
                      "global_selected_task_count": len(global_ids)}
    elif task_ids_file:
        selected_ids = _ids(read_json(task_ids_file), "task-IDs file")
        _require(set(selected_ids) <= {e["task_id"] for e in eligible},
                 "Task-IDs file contains unknown, wrong-environment, or out-of-split tasks")
        selection_mode = "task_ids_file"
        provenance = {"selection_file_sha256": file_sha256(task_ids_file)}
    by_id = {e["task_id"]: e for e in episodes}
    _require(bool(selected_ids), "Selection is empty for this environment")
    # Preserve the native manifest ordering, including for reversed input lists.
    selected_ids = [e["task_id"] for e in episodes if e["task_id"] in set(selected_ids)]
    chosen = [by_id[i] for i in selected_ids]
    return chosen, {"schema_version": 1, "environment": environment, "split": split,
                    "selection_mode": selection_mode, "task_ids": selected_ids, "episodes": len(chosen),
                    "native_action_budget": sum(e["expected_max_steps"] for e in chosen),
                    "selection_helper_sha256": file_sha256(Path(__file__)), **metadata, **provenance}


def load_settings(path):
    settings = read_json(path)
    _require(isinstance(settings, dict) and not set(settings) - {"api_base_url", "agent", "client", "limits"},
             "Settings must contain only nonsecret parity configuration")
    allowed = {
        "agent": {"type", "remember_cot", "max_text_history", "max_image_history", "max_cot_history"},
        "client": {"client_name", "model_id", "generate_kwargs", "timeout", "max_retries", "delay", "alternate_roles"},
        "limits": {"max_model_calls"},
    }
    for name, keys in allowed.items():
        value = settings.get(name, {})
        _require(isinstance(value, dict) and not set(value) - keys, f"Unknown or secret {name} settings")
    generate = settings.get("client", {}).get("generate_kwargs", {})
    _require(isinstance(generate, dict) and not set(generate) - {"temperature", "max_tokens", "thinking_budget"},
             "Unknown or secret generation settings")
    model = settings.get("client", {}).get("model_id")
    _require(isinstance(model, str) and model.strip() == model and model and
             not re.search(r"REPLACE[_-]|YOUR[_-]|CHANGEME|TODO|<|>", model, re.IGNORECASE),
             "An exact nonplaceholder model ID is required, including for dry-run")
    endpoint = settings.get("api_base_url")
    _require(isinstance(endpoint, str) and endpoint and not any(ord(c) <= 32 for c in endpoint),
             "An explicit API base URL without whitespace or controls is required")
    url = urlsplit(endpoint)
    _require(url.scheme in {"http", "https"} and url.hostname and not url.username and not url.password
             and not url.query and not url.fragment, "API base URL must not include credentials, query or fragment")
    agent, client = settings.get("agent", {}), settings.get("client", {})
    _require(agent.get("type", "naive") == "naive", "Only the pinned upstream naive agent is supported")
    _require(agent.get("max_image_history", 0) == 0, "Parity launchers support text-only observations")
    _require(client.get("client_name", "openai") in {"openai", "vllm", "nvidia", "xai"},
             "Only supported OpenAI-compatible upstream clients may be used")
    for name in ("max_text_history", "max_image_history", "max_cot_history"):
        if name in agent:
            _require(type(agent[name]) is int and agent[name] >= 0, f"{name} must be a nonnegative integer")
    for container, name in ((agent, "remember_cot"), (client, "alternate_roles")):
        if name in container:
            _require(type(container[name]) is bool, f"{name} must be boolean")
    # Upstream max_retries counts total attempts: zero would issue no request.
    # This is distinct from Harbor's intentionally disabled whole-job retries.
    for container, name, minimum in ((client, "max_retries", 1), (settings.get("limits", {}), "max_model_calls", 1)):
        if name in container:
            _require(type(container[name]) is int and container[name] >= minimum, f"Invalid {name}")
    for name, minimum, exclusive in (("timeout", 0, True), ("delay", 0, False)):
        if name in client:
            value = client[name]
            _require(type(value) in (int, float) and math.isfinite(value) and
                     (value > minimum if exclusive else value >= minimum), f"Invalid {name}")
    for name, minimum in (("max_tokens", 1), ("thinking_budget", 0)):
        value = generate.get(name)
        if value is not None:
            _require(type(value) is int and value >= minimum, f"Invalid {name}")
    temperature = generate.get("temperature")
    if temperature is not None:
        _require(type(temperature) in (int, float) and math.isfinite(temperature) and 0 <= temperature <= 2,
                 "Temperature must be a finite number in [0, 2]")
    return settings, {"model_id": model, "settings_file_sha256": file_sha256(path),
                      "agent_type": settings.get("agent", {}).get("type", "naive")}


def validate_timeout(value, *, dry_run):
    if value is not None:
        _require(type(value) is int and value > 0, "Episode timeout must be positive")
    _require(dry_run or value is not None, "Live execution requires an explicit --episode-timeout for this environment")
    return {"episode_timeout_sec": value, "episode_timeout_confirmed": value is not None,
            "timeout_note": "Explicit outer infrastructure deadline; native budget unchanged" if value else
            "Unresolved preview only: an explicit per-environment timeout is required before live execution"}


def validate_dataset(dataset, episodes):
    dataset = Path(dataset)
    _assert_no_links(dataset)
    _require(dataset.is_dir() and not dataset.is_symlink(), "Dataset must be a real local directory")
    tasks = {p.parent.name: p.parent for p in dataset.glob("*/task.toml")}
    _require(set(tasks) == {e["task_id"] for e in episodes}, "Dataset directory does not exactly match selected task IDs")
    result = {}
    for episode in episodes:
        path = tasks[episode["task_id"]]
        _require(not path.is_symlink(), "Task directory must not be a symlink")
        for filename in ("environment/episode.json", "tests/task_config.json"):
            _require(_episode_identity(read_json(path / filename)) == episode,
                     f"Generated task identity/settings changed: {episode['task_id']}")
        config = tomllib.loads((path / "task.toml").read_text(encoding="utf-8"))
        _require(config.get("task", {}).get("name") == "balrog/" + episode["task_id"] and
                 config.get("verifier", {}).get("environment_mode") == "separate", "Task name or separate verifier configuration differs")
        result[episode["task_id"]] = {name: file_sha256(path / name) for name in
            ("task.toml", "environment/episode.json", "tests/task_config.json")}
    return result


def native_build_provenance(environment_dir, episodes, *, package=PACKAGE):
    directory = Path(environment_dir)
    _assert_no_links(directory)
    _require(directory.is_dir() and not directory.is_symlink(), "Generated environment directory is missing or symlinked")
    environment = episodes[0]["env_name"]
    full, _ = _manifest(package, environment)
    image_episode = _episode_identity(read_json(directory / "episode.json"))
    _require(image_episode in full, "Generated image episode is not an unchanged case in this environment")
    required = ("Dockerfile.game", "game_server.py", "export_result.py", "episode.json", "requirements-agent.lock",
                "runtime_guard.py", "runtime-lock.json", "requirements-game.lock", "apt-game.lock")
    _require(all((directory / name).is_file() for name in required), "Native build context is missing a required runtime input")
    _require((directory / "vendor").is_dir(), "Native build context is missing vendored sources")
    files = {}
    for path in sorted(directory.rglob("*")):
        _assert_no_links(path)
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = file_sha256(path)
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"image": "harbor-balrog-native:" + digest[:16], "build_context_sha256": digest,
            "build_files_sha256": files}


def build_harbor_job(*, dataset, settings_path, model_id, jobs_dir, job_name, concurrency=1,
                     episode_timeout=None, collection_grace=120, environment_type="docker"):
    from harbor.models.job.config import JobConfig

    _require(environment_type in {"docker", "daytona"}, "Environment type must be docker or daytona")
    _require(type(concurrency) is int and concurrency > 0, "Concurrency must be positive")
    _require(type(collection_grace) is int and collection_grace > 0, "Collection grace must be positive")
    _require(isinstance(job_name, str) and re.fullmatch(r"[A-Za-z0-9_-]+", job_name), "Use a safe, nonempty job name")
    validate_timeout(episode_timeout, dry_run=True)
    kwargs = {"settings_path": str(Path(settings_path).resolve())}
    if episode_timeout is not None:
        kwargs["execution_timeout_sec"] = episode_timeout
    environment = {"type": environment_type, "delete": True, "kwargs": {"auto_mounting": False}}
    if environment_type == "daytona":
        # Validate only the installed provider's pure options model. Constructing
        # an environment or calling preflight would inspect cloud credentials.
        from harbor.environments.daytona.environment import DaytonaOptions

        DaytonaOptions.model_validate(environment["kwargs"])
    job = {"job_name": job_name, "jobs_dir": str(Path(jobs_dir).resolve()), "n_attempts": 1,
           "n_concurrent_trials": concurrency, "retry": {"max_retries": 0},
           "environment": environment,
           "agents": [{"import_path": "balrog.agent:BalrogNativeAgent", "model_name": model_id,
                       "skip_model_parsing": True,
                       "override_timeout_sec": episode_timeout + collection_grace if episode_timeout is not None else None,
                       "kwargs": kwargs}],
           "datasets": [{"path": str(Path(dataset).resolve())}]}
    normalized = JobConfig.model_validate(job).model_dump(mode="json")
    _require(normalized["n_concurrent_trials"] == concurrency and normalized["retry"]["max_retries"] == 0,
             "Installed Harbor did not preserve concurrency/retry settings")
    return normalized


def harbor_version():
    return importlib.metadata.version("harbor")
