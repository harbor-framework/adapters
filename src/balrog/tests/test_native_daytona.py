"""No-key native Daytona tests: real schemas, fake provider, no cloud traffic."""

import asyncio
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
import native_daytona as cloud
import parity_launch as launch
import run_native


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class FakeProvider:
    def __init__(self, owner, failure=None):
        self.owner, self.failure = owner, failure
        self.calls = []

    async def start(self, **kwargs):
        self.calls.append(("start", kwargs))
        if self.failure == "start":
            raise OSError("sentinel-private-key")

    async def exec(self, command, **kwargs):
        self.calls.append(("exec", {"command": command, **kwargs}))
        if command == "python /opt/runtime_guard.py verify" and self.failure == "guard":
            return SimpleNamespace(return_code=1)
        if "/native_batch.py" in command:
            if self.failure == "timeout":
                raise TimeoutError("sentinel-private-key")
            if self.failure == "cancel":
                raise asyncio.CancelledError()
            return SimpleNamespace(return_code=1 if self.failure == "nonzero" else 0,
                                   stdout="completed sentinel-private-key", stderr="")
        return SimpleNamespace(return_code=0)

    async def upload_dir(self, source, target):
        self.calls.append(("upload", target))
        if self.failure == "upload":
            raise OSError("sentinel-private-key")

    async def download_dir(self, source, target):
        self.calls.append(("download", source))
        if self.failure == "download":
            raise OSError("sentinel-private-key")
        self.owner.write_results(Path(target))
        if self.failure == "partial-download":
            raise OSError("sentinel-private-key")
        if self.failure == "missing":
            (Path(target) / "run_status.json").unlink()

    async def stop(self, **kwargs):
        self.calls.append(("stop", kwargs))
        if self.failure == "stop":
            raise OSError("sentinel-private-key")


class NativeDaytonaTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="balrog-daytona-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.episodes, _ = launch.select_episodes("babyai", selection_plan=PROJECT / "parity/plan.proposed.json")
        self.settings, _ = launch.load_settings(PROJECT / "parity/settings.proposed.json")
        self.environment = self.root / "task/environment"
        self.environment.mkdir(parents=True)
        (self.environment.parent / "task.toml").write_text(
            '[environment]\nbuild_timeout_sec=900\ncpus=1\nmemory_mb=1024\nstorage_mb=2048\n'
            '[environment.healthcheck]\ncommand="agent-only-healthcheck"\n', encoding="utf-8")
        write_json(self.environment / "episode.json", self.episodes[0])
        for name in ("Dockerfile.game", "game_server.py", "export_result.py", "requirements-agent.lock",
                     "runtime_guard.py", "runtime-lock.json", "requirements-game.lock", "apt-game.lock"):
            (self.environment / name).write_text("fixture " + name + "\n", encoding="utf-8")
        for name in ("Dockerfile", "docker-compose.yaml", "compose.yml", ".dockerignore"):
            (self.environment / name).write_text("exclude " + name, encoding="utf-8")
        (self.environment / "vendor").mkdir()
        (self.environment / "vendor/source.tar.gz").write_bytes(b"fixture source")
        self.package = self.root / "package"
        self.package.mkdir()
        for name in ("native_batch.py", "parity_runner.py"):
            (self.package / name).write_text("fixture " + name, encoding="utf-8")
        write_json(self.package / "fixtures/pins.json", {"commit": "pinned source"})
        (self.package / "__pycache__").mkdir()
        (self.package / "__pycache__/unused.pyc").write_bytes(b"cache")
        self.build = launch.native_build_provenance(self.environment, self.episodes)
        self.metadata = cloud.preview(self.environment, self.episodes, self.settings, self.build, 700, package=self.package)
        self.output = self.root / "output"
        self.output.mkdir()
        write_json(self.output / "run_plan.json", {"preserved": True})

    def write_results(self, output):
        ids = [row["task_id"] for row in self.episodes]
        write_json(output / "run_status.json", {
            "status": "completed", "task_ids": ids, "completed": ids,
            "episodes_sha256": hashlib.sha256(json.dumps(self.episodes, sort_keys=True).encode()).hexdigest(),
            "input_settings_sha256": hashlib.sha256(json.dumps(self.settings, sort_keys=True, ensure_ascii=True).encode()).hexdigest(),
            "runner_sha256": self.metadata["package_files_sha256"]["parity_runner.py"]})
        write_json(output / "inputs/settings.json", self.settings)
        (output / "inputs/parity_runner.py").write_bytes((self.package / "parity_runner.py").read_bytes())
        for episode in self.episodes:
            write_json(output / "inputs" / (episode["task_id"] + ".json"), episode)
            folder = output / episode["task_id"]
            write_json(folder / "episode_result.json", {
                "status": "completed", "mode": "native", "task_id": episode["task_id"], "task": episode["task"],
                "seed": episode["seed"], "max_steps": episode["expected_max_steps"], "steps": 1,
                "native_progression": 0.0, "runner_sha256": self.metadata["package_files_sha256"]["parity_runner.py"]})
            write_json(folder / "original_episode_result.json", {"progression": 0.0, "num_steps": 1})
            write_json(folder / "model_calls.json", [])
            write_json(folder / "trajectory.json", {"steps": []})

    def execute(self, provider):
        return asyncio.run(cloud.execute(provider, self.package, self.root / "inputs", self.output,
                                        self.episodes, self.settings, self.metadata, "sentinel-private-key"))

    def test_preview_and_cli_never_construct_provider_read_keys_or_run_processes(self):
        from harbor.environments.daytona import environment as provider_module
        args = ["--environment-dir", str(self.environment), "--settings", str(PROJECT / "parity/settings.proposed.json"),
                "--output-dir", str(self.root / "never-created"), "--environment-type", "daytona",
                "--selection-plan", str(PROJECT / "parity/plan.proposed.json"), "--episode-timeout", "700", "--dry-run"]
        stdout = io.StringIO()
        with patch.object(provider_module.DaytonaEnvironment, "__init__", side_effect=AssertionError("provider")), \
                patch.object(provider_module.DaytonaClientManager, "get_instance", side_effect=AssertionError("SDK")), \
                patch.object(provider_module, "_daytona_preflight", side_effect=AssertionError("credentials")), \
                patch.object(run_native, "load_model_key", side_effect=AssertionError("model key")), \
                patch.object(run_native.subprocess, "run", side_effect=AssertionError("process")), redirect_stdout(stdout):
            run_native.main(args)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["environment_type"], "daytona")
        self.assertEqual(result["daytona"]["batch_timeout_sec"], len(self.episodes) * 700 + 120)
        self.assertEqual(result["task_ids"], [e["task_id"] for e in self.episodes])
        self.assertIn("untested", result["daytona"]["platform_note"])
        self.assertFalse((self.root / "never-created").exists())

    def test_stage_hashes_exact_package_and_no_compose_or_sidecar_boot(self):
        context, package, inputs = cloud.stage(self.environment, self.root / "stage", self.metadata,
                                              self.episodes, self.settings, package=self.package)
        self.assertEqual((context / "Dockerfile").read_bytes(), (self.environment / "Dockerfile.game").read_bytes() + cloud.BOOT_SUFFIX)
        for name in ("docker-compose.yaml", "compose.yml", ".dockerignore"):
            self.assertFalse((context / name).exists())
        self.assertTrue((package / "fixtures/pins.json").is_file())
        self.assertFalse((package / "__pycache__").exists())
        self.assertEqual(launch.read_json(inputs / "episodes.json"), self.episodes)
        self.assertEqual(launch.read_json(inputs / "settings.json"), self.settings)
        self.assertEqual(launch.file_sha256(inputs / "episodes.json"), self.metadata["episodes_sha256"])
        self.assertEqual(launch.file_sha256(inputs / "settings.json"), self.metadata["settings_sha256"])
        self.assertEqual(self.metadata["environment_config"]["healthcheck"], None)
        self.assertEqual(self.metadata["environment_config"]["memory_mb"], 1024)
        self.assertEqual(self.metadata["environment_config"]["workdir"], "/app")
        (self.environment / "game_server.py").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed after preflight"):
            cloud.stage(self.environment, self.root / "changed-stage", self.metadata, self.episodes, self.settings, package=self.package)

    def test_live_factory_uses_real_harbor_types_without_instantiating_sdk(self):
        from harbor.environments.factory import EnvironmentFactory
        from harbor.models.environment_type import EnvironmentType
        with patch.object(EnvironmentFactory, "create_environment", return_value="fake-provider") as factory:
            value = cloud.create_provider(self.environment, self.root / "provider", self.metadata)
        self.assertEqual(value, "fake-provider")
        kwargs = factory.call_args.kwargs
        self.assertEqual(kwargs["type"], EnvironmentType.DAYTONA)
        self.assertFalse(kwargs["auto_mounting"])
        self.assertFalse(kwargs["enable_environment_dir_upload"])
        self.assertEqual(kwargs["task_env_config"].build_timeout_sec, 900)
        self.assertEqual(kwargs["task_env_config"].env, {})

    def test_success_exact_native_command_and_key_only_in_exec_env(self):
        provider = FakeProvider(self)
        result = self.execute(provider)
        self.assertEqual(result["status"], "completed")
        commands = [kw for kind, kw in provider.calls if kind == "exec"]
        self.assertEqual(commands[-1], {"command": "python /opt/parity/native_batch.py --episodes /input/episodes.json --settings /input/settings.json --output-dir /results --episode-timeout 700",
            "cwd": "/app", "user": "root", "env": {"OPENAI_API_KEY": "sentinel-private-key"},
            "timeout_sec": len(self.episodes) * 700 + 120})
        self.assertTrue(all("env" not in c for c in commands[:-1]))
        self.assertEqual(provider.calls[-2:], [("download", "/results"), ("stop", {"delete": True})])
        self.assertEqual(launch.read_json(self.output / "run_plan.json"), {"preserved": True})
        for path in self.output.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"sentinel-private-key", path.read_bytes())

    def test_failures_always_collect_and_cleanup_without_printing_sdk_errors(self):
        for failure in ("start", "guard", "upload", "nonzero", "timeout", "download", "partial-download", "stop", "missing"):
            with self.subTest(failure=failure):
                self.output = self.root / ("output-" + failure)
                self.output.mkdir()
                provider = FakeProvider(self, failure)
                with self.assertRaises(RuntimeError) as caught:
                    self.execute(provider)
                self.assertNotIn("sentinel-private-key", str(caught.exception))
                self.assertEqual(provider.calls[-2:], [("download", "/results"), ("stop", {"delete": True})])
                report = launch.read_json(self.output / "daytona_execution.json")
                self.assertEqual(report["status"], "error")
                self.assertTrue(report["cleanup_attempted"])
                if failure == "partial-download":
                    self.assertTrue((self.output / "run_status.json").is_file())
                    self.assertFalse(report["artifacts_downloaded"])
                if failure in {"start", "guard", "upload"}:
                    self.assertFalse(any("env" in kw for kind, kw in provider.calls if kind == "exec"))

    def test_cancelled_execution_collects_and_cleans_then_reraises_cancellation(self):
        provider = FakeProvider(self, "cancel")
        with self.assertRaises(asyncio.CancelledError):
            self.execute(provider)
        self.assertEqual(provider.calls[-2:], [("download", "/results"), ("stop", {"delete": True})])
        report = launch.read_json(self.output / "daytona_execution.json")
        self.assertEqual(report["error_type"], "CancelledError")
        self.assertTrue(report["artifacts_downloaded"])

    def test_external_cancel_during_exec_and_again_during_collection_waits_for_cleanup(self):
        owner = self

        async def scenario():
            executing, collecting, finish_collection = asyncio.Event(), asyncio.Event(), asyncio.Event()

            class PausedProvider(FakeProvider):
                async def exec(self, command, **kwargs):
                    if "/native_batch.py" in command:
                        executing.set()
                        await asyncio.Event().wait()
                    return await super().exec(command, **kwargs)

                async def download_dir(self, source, target):
                    collecting.set()
                    await finish_collection.wait()
                    return await super().download_dir(source, target)

            provider = PausedProvider(owner)
            task = asyncio.create_task(cloud.execute(provider, owner.package, owner.root / "inputs", owner.output,
                owner.episodes, owner.settings, owner.metadata, "sentinel-private-key"))
            await executing.wait()
            task.cancel()
            await collecting.wait()
            task.cancel()
            finish_collection.set()
            with owner.assertRaises(asyncio.CancelledError):
                await task
            owner.assertEqual(provider.calls[-1], ("stop", {"delete": True}))

        asyncio.run(scenario())
        self.assertTrue(launch.read_json(self.output / "daytona_execution.json")["cleanup_call_returned"])

    def test_stalled_provider_start_setup_and_batch_have_host_deadlines(self):
        owner = self
        self.metadata.update(start_host_timeout_sec=0.01, setup_host_timeout_sec=0.01, batch_host_timeout_sec=0.01)
        for stalled in ("start", "setup", "batch"):
            with self.subTest(stalled=stalled):
                self.output = self.root / ("stalled-" + stalled)
                self.output.mkdir()

                class StalledProvider(FakeProvider):
                    async def start(self, **kwargs):
                        if stalled == "start":
                            await asyncio.Event().wait()
                        return await super().start(**kwargs)

                    async def exec(self, command, **kwargs):
                        if (stalled == "setup" and command.startswith("mkdir")) or (stalled == "batch" and "/native_batch.py" in command):
                            await asyncio.Event().wait()
                        return await super().exec(command, **kwargs)

                provider = StalledProvider(owner)
                with self.assertRaises(RuntimeError):
                    self.execute(provider)
                report = launch.read_json(self.output / "daytona_execution.json")
                self.assertEqual(report["error_type"], "TimeoutError")
                self.assertEqual(provider.calls[-2:], [("download", "/results"), ("stop", {"delete": True})])

    def test_partial_missing_or_mismatched_outputs_never_pass(self):
        self.write_results(self.output)
        cloud.validate_results(self.output, self.episodes, self.settings, self.metadata)
        mutations = (
            ("run_status.json", lambda r: r.update(completed=r["completed"][:-1])),
            ("run_status.json", lambda r: r.update(task_ids=list(reversed(r["task_ids"])))),
            ("run_status.json", lambda r: r.update(runner_sha256="0" * 64)),
            (self.episodes[0]["task_id"] + "/episode_result.json", lambda r: r.update(mode="http")),
            (self.episodes[0]["task_id"] + "/episode_result.json", lambda r: r.update(max_steps=2000)),
            (self.episodes[0]["task_id"] + "/original_episode_result.json", lambda r: r.update(progression=1.0)),
            ("inputs/settings.json", lambda r: r.update(api_base_url="https://wrong.example")),
        )
        for filename, mutate in mutations:
            with self.subTest(filename=filename):
                self.write_results(self.output)
                path = self.output / filename
                data = launch.read_json(path)
                mutate(data)
                write_json(path, data)
                with self.assertRaises(ValueError):
                    cloud.validate_results(self.output, self.episodes, self.settings, self.metadata)

    def test_run_live_stages_full_inputs_and_uses_cleanup_wrapper_with_fake_provider(self):
        provider = FakeProvider(self)
        with patch.object(cloud, "create_provider", return_value=provider) as factory:
            result = cloud.run_live(self.environment, self.output, self.episodes, self.settings,
                                    self.metadata, "sentinel-private-key", package=self.package)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(factory.call_count, 1)
        self.assertFalse(factory.call_args.args[0].exists(), "Temporary staging must be removed")


if __name__ == "__main__":
    unittest.main()
