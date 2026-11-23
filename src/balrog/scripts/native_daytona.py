"""Original BALROG evaluator on Harbor's single-container Daytona provider.

Preview is pure local validation. Only run_live constructs a provider or reads its
process-environment credentials. Remote execution has not been validated here.
"""

import asyncio
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import shutil
import tempfile
import tomllib
import uuid

from parity_launch import PACKAGE, _assert_no_links, file_sha256, read_json

GRACE_SECONDS = 120
POLL_GRACE_SECONDS = 30
BOOT_SUFFIX = b'\n# Native evaluator: match docker run --user 0; no HTTP sidecar.\nUSER root\nENTRYPOINT []\nCMD ["sleep", "infinity"]\n'
RESOURCE_FIELDS = ("build_timeout_sec", "cpus", "memory_mb", "storage_mb")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _input_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True).encode("utf-8")


def package_files(package=PACKAGE):
    """Include the complete Python package, including source-pin fixtures."""
    files = {}
    for path in sorted(Path(package).rglob("*")):
        _assert_no_links(path)
        relative = path.relative_to(package)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if any(part.startswith(".env") or part.lower() in {".git", "secrets"} for part in relative.parts):
            raise ValueError("Unexpected private file in package upload")
        if path.is_file():
            files[relative.as_posix()] = file_sha256(path)
    for required in ("native_batch.py", "parity_runner.py"):
        if required not in files:
            raise ValueError("Native package is incomplete")
    return files


def preview(environment_dir, episodes, settings, build, episode_timeout, *, package=PACKAGE):
    """Validate schemas and hash remote inputs without constructing a provider."""
    from harbor.environments.daytona.environment import DaytonaOptions
    from harbor.models.task.config import EnvironmentConfig

    directory = Path(environment_dir)
    task_path = directory.parent / "task.toml"
    _assert_no_links(task_path)
    task = tomllib.loads(task_path.read_text(encoding="utf-8"))
    source = task.get("environment", {})
    if any(name not in source for name in RESOURCE_FIELDS):
        raise ValueError("Native Daytona requires explicit generated task resource/build limits")
    resources = {name: source[name] for name in RESOURCE_FIELDS}
    if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in resources.values()):
        raise ValueError("Native Daytona resource/build limits must be finite and positive")
    # The task's agent healthcheck concerns /logs/verifier and is not a native
    # evaluator healthcheck. No compose service, task env or secret is inherited.
    environment_config = EnvironmentConfig.model_validate({**resources, "workdir": "/app"}).model_dump(mode="json")
    options = {"auto_mounting": False}
    DaytonaOptions.model_validate(options)
    derived_dockerfile = (directory / "Dockerfile.game").read_bytes() + BOOT_SUFFIX
    files = {name: digest for name, digest in build["build_files_sha256"].items()
             if Path(name).name not in {"Dockerfile", ".dockerignore"}
             and not Path(name).name.startswith(("docker-compose", "compose."))}
    files["Dockerfile"] = hashlib.sha256(derived_dockerfile).hexdigest()
    package_hashes = package_files(package)
    try:
        sdk_version = importlib.metadata.version("daytona")
    except importlib.metadata.PackageNotFoundError:
        sdk_version = None
    return {"provider": "harbor-daytona-direct", "provider_kwargs": options,
            "harbor_version": importlib.metadata.version("harbor"), "daytona_sdk_version": sdk_version,
            "platform_note": "Local schemas and fake lifecycle only; remote runtime remains untested",
            "credentials": "DAYTONA_API_KEY is read by Harbor from the live process environment; OPENAI_API_KEY is passed only to native exec",
            "environment_config": environment_config, "task_config_sha256": file_sha256(task_path),
            "original_game_dockerfile_sha256": file_sha256(directory / "Dockerfile.game"),
            "derived_dockerfile_sha256": files["Dockerfile"], "derived_context_files_sha256": files,
            "derived_context_sha256": _digest(files), "package_files_sha256": package_hashes,
            "package_sha256": _digest(package_hashes), "episodes_sha256": hashlib.sha256(_input_bytes(episodes)).hexdigest(),
            "settings_sha256": hashlib.sha256(_input_bytes(settings)).hexdigest(), "helper_sha256": file_sha256(Path(__file__)),
            "episode_timeout_sec": episode_timeout,
            "batch_timeout_sec": len(episodes) * episode_timeout + GRACE_SECONDS if episode_timeout else None,
            "batch_host_timeout_sec": len(episodes) * episode_timeout + GRACE_SECONDS + POLL_GRACE_SECONDS if episode_timeout else None,
            "start_host_timeout_sec": resources["build_timeout_sec"] + GRACE_SECONDS,
            "setup_host_timeout_sec": GRACE_SECONDS + POLL_GRACE_SECONDS,
            "batch_grace_sec": GRACE_SECONDS, "collection_timeout_sec": GRACE_SECONDS,
            "native_command": native_command(episode_timeout) if episode_timeout else None}


def native_command(episode_timeout):
    if type(episode_timeout) is not int or episode_timeout <= 0:
        raise ValueError("An explicit positive per-episode timeout is required")
    return ("python /opt/parity/native_batch.py --episodes /input/episodes.json "
            "--settings /input/settings.json --output-dir /results --episode-timeout " + str(episode_timeout))


def stage(directory, destination, metadata, episodes, settings, *, package=PACKAGE):
    """Copy only hash-attested nonsecret inputs, without mutating source files."""
    destination = Path(destination)
    context, code, inputs = (destination / name for name in ("environment", "package", "inputs"))
    for folder in (context, code, inputs):
        folder.mkdir(parents=True)
    for name, expected in metadata["derived_context_files_sha256"].items():
        target = context / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == "Dockerfile":
            target.write_bytes((Path(directory) / "Dockerfile.game").read_bytes() + BOOT_SUFFIX)
        else:
            shutil.copyfile(Path(directory) / name, target)
        if file_sha256(target) != expected:
            raise ValueError("Native context changed after preflight")
    for name, expected in metadata["package_files_sha256"].items():
        target = code / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(package) / name, target)
        if file_sha256(target) != expected:
            raise ValueError("Native package changed after preflight")
    for name, value in (("episodes", episodes), ("settings", settings)):
        payload = _input_bytes(value)
        if hashlib.sha256(payload).hexdigest() != metadata[name + "_sha256"]:
            raise ValueError("Native inputs changed after preflight")
        (inputs / (name + ".json")).write_bytes(payload)
    return context, code, inputs


def create_provider(context, provider_logs, metadata):
    """Live-only factory; SDK credentials are never inspected by preview."""
    from harbor.environments.factory import EnvironmentFactory
    from harbor.models.environment_type import EnvironmentType
    from harbor.models.task.config import EnvironmentConfig
    from harbor.models.trial.paths import TrialPaths

    paths = TrialPaths(trial_dir=provider_logs)
    paths.mkdir()
    return EnvironmentFactory.create_environment(
        type=EnvironmentType.DAYTONA, environment_dir=context,
        environment_name="balrog-native-" + metadata["derived_context_sha256"][:16],
        session_id=str(uuid.uuid4()), trial_paths=paths,
        task_env_config=EnvironmentConfig.model_validate(metadata["environment_config"]),
        enable_environment_dir_upload=False, **metadata["provider_kwargs"])


def validate_results(output, episodes, settings, metadata):
    """A successful process is insufficient: require complete native artifacts."""
    output = Path(output)
    status = read_json(output / "run_status.json")
    ids = [episode["task_id"] for episode in episodes]
    expected = {"status": "completed", "task_ids": ids, "completed": ids,
                "runner_sha256": metadata["package_files_sha256"]["parity_runner.py"],
                "episodes_sha256": hashlib.sha256(json.dumps(episodes, sort_keys=True).encode()).hexdigest(),
                "input_settings_sha256": hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=True).encode()).hexdigest()}
    if any(status.get(key) != value for key, value in expected.items()):
        raise ValueError("Native batch result is missing, incomplete or mismatched")
    if (read_json(output / "inputs/settings.json") != settings
            or file_sha256(output / "inputs/parity_runner.py") != expected["runner_sha256"]):
        raise ValueError("Native settings or runner snapshot differs")
    for episode in episodes:
        if read_json(output / "inputs" / (episode["task_id"] + ".json")) != episode:
            raise ValueError("Native episode snapshot differs")
        folder = output / episode["task_id"]
        result = read_json(folder / "episode_result.json")
        identity = {"status": "completed", "mode": "native", "task_id": episode["task_id"],
                    "task": episode["task"], "seed": episode["seed"], "max_steps": episode["expected_max_steps"],
                    "runner_sha256": expected["runner_sha256"]}
        if any(result.get(key) != value for key, value in identity.items()):
            raise ValueError("Native episode result identity or completion differs")
        score = result.get("native_progression")
        steps = result.get("steps")
        if (type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1
                or type(steps) is not int or not 0 <= steps <= episode["expected_max_steps"]):
            raise ValueError("Native score or step count is invalid")
        original = read_json(folder / "original_episode_result.json")
        if original.get("progression") != score or original.get("num_steps") != steps:
            raise ValueError("Original evaluator output disagrees")
        if not isinstance(read_json(folder / "model_calls.json"), list):
            raise ValueError("Native model-call artifact is invalid")
        if steps and not isinstance(read_json(folder / "trajectory.json"), dict):
            raise ValueError("Native trajectory artifact is missing")


async def execute(provider, code, inputs, output, episodes, settings, metadata, model_key):
    """Collect before cleanup on success, failure and cancellation; no retry."""
    output = Path(output)
    report = {"status": "running", "cleanup_attempted": False, "artifacts_downloaded": False}
    primary = None
    try:
        await asyncio.wait_for(provider.start(force_build=True), metadata["start_host_timeout_sec"])
        for index, command in enumerate(("mkdir -p /opt/parity /input /results", "python /opt/runtime_guard.py verify")):
            checked = await asyncio.wait_for(provider.exec(command, user="root", timeout_sec=GRACE_SECONDS),
                                             metadata["setup_host_timeout_sec"])
            for name in ("stdout", "stderr"):
                text = getattr(checked, name, None) or ""
                (output / (f"setup_{index}_" + name + ".txt")).write_text(text.replace(model_key, "[REDACTED]"), encoding="utf-8")
            if checked.return_code != 0:
                raise RuntimeError("Native sandbox setup/runtime verification failed")
        await asyncio.wait_for(provider.upload_dir(code, "/opt/parity"), GRACE_SECONDS)
        await asyncio.wait_for(provider.upload_dir(inputs, "/input"), GRACE_SECONDS)
        # The provider's timeout_sec wraps the remote process. Its polling loop
        # has no host deadline, so also bound the local await independently.
        result = await asyncio.wait_for(provider.exec(metadata["native_command"], cwd="/app", user="root",
                                     env={"OPENAI_API_KEY": model_key}, timeout_sec=metadata["batch_timeout_sec"]),
                                     metadata["batch_host_timeout_sec"])
        report["return_code"] = result.return_code
        for name in ("stdout", "stderr"):
            text = getattr(result, name, None) or ""
            (output / ("native_" + name + ".txt")).write_text(text.replace(model_key, "[REDACTED]"), encoding="utf-8")
        if result.return_code != 0:
            raise RuntimeError("Native Daytona batch failed; retained artifacts may be partial")
    except BaseException as exc:
        primary = exc
        report["error_type"] = type(exc).__name__
    finally:
        # Shield one cleanup task so cancellation of the execution cannot skip
        # the download/delete sequence. A second cancellation still waits for it.
        async def collect_and_stop():
            try:
                with tempfile.TemporaryDirectory(prefix="balrog-daytona-results-") as temporary:
                    target = Path(temporary) / "results"
                    try:
                        await asyncio.wait_for(provider.download_dir("/results", target), GRACE_SECONDS)
                    except BaseException as exc:
                        # A provider may have downloaded a partial directory
                        # before failing; retain those files as failed evidence.
                        report["collection_error_type"] = type(exc).__name__
                    if not target.is_dir():
                        raise ValueError("Native artifact directory was not downloaded")
                    for path in target.rglob("*"):
                        _assert_no_links(path)
                    for path in target.iterdir():
                        if (output / path.name).exists():
                            raise ValueError("Downloaded native artifact collides with host provenance")
                        shutil.move(str(path), str(output / path.name))
                    report["artifacts_downloaded"] = "collection_error_type" not in report
            except BaseException as exc:
                report.setdefault("collection_error_type", type(exc).__name__)
            finally:
                report["cleanup_attempted"] = True
                try:
                    await asyncio.wait_for(provider.stop(delete=True), GRACE_SECONDS)
                    # Harbor may swallow provider deletion errors internally.
                    report["cleanup_call_returned"] = True
                except BaseException as exc:
                    report["cleanup_error_type"] = type(exc).__name__

        cleanup = asyncio.create_task(collect_and_stop())
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError as exc:
                if primary is None:
                    primary = exc
                    report["error_type"] = type(exc).__name__
        if primary is None:
            try:
                if "collection_error_type" in report or "cleanup_error_type" in report:
                    raise RuntimeError("Native artifact collection or cleanup failed")
                validate_results(output, episodes, settings, metadata)
            except Exception as exc:
                primary = exc
                report["error_type"] = type(exc).__name__
        report["status"] = "error" if primary else "completed"
        (output / "daytona_execution.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if primary is not None:
        if isinstance(primary, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
            raise primary
        # SDK exception messages can contain the exec request, including env.
        # Preserve its type in the report, never print the untrusted message.
        raise RuntimeError("Native Daytona execution failed (" + type(primary).__name__ + "); see daytona_execution.json") from None
    return report


def run_live(environment_dir, output, episodes, settings, metadata, model_key, *, package=PACKAGE):
    """Called only after explicit live CLI selection and key loading."""
    from harbor.utils.async_cleanup import with_async_cleanup

    with tempfile.TemporaryDirectory(prefix="balrog-native-daytona-") as temporary:
        context, code, inputs = stage(environment_dir, Path(temporary), metadata, episodes, settings, package=package)

        async def launch():
            provider = create_provider(context, Path(output) / "provider", metadata)
            return await execute(provider, code, inputs, output, episodes, settings, metadata, model_key)

        try:
            return asyncio.run(with_async_cleanup(launch()))
        except Exception as exc:
            # Construction/shared-client cleanup can fail outside execute().
            # SDK diagnostics must not print credential-bearing request text.
            report_path = Path(output) / "daytona_execution.json"
            report = read_json(report_path) if report_path.exists() else {"cleanup_attempted": False}
            report.update(status="error", launch_error_type=type(exc).__name__)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            raise RuntimeError("Native Daytona launch failed (" + type(exc).__name__ + "); see daytona_execution.json") from None
