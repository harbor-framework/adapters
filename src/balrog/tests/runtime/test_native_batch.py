"""Native batch guardrails, using real settings validation and fake children."""

from contextlib import ExitStack, contextmanager, redirect_stderr
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime_support import PACKAGE, configure_upstream, frozen_case, load_file, parity_runner

UPSTREAM = configure_upstream()
runner = parity_runner()
batch = load_file("_balrog_test_native_batch", PACKAGE / "native_batch.py")


@contextmanager
def runner_alias():
    previous = sys.modules.get("parity_runner")
    sys.modules["parity_runner"] = runner
    try:
        yield
    finally:
        if previous is None:
            sys.modules.pop("parity_runner", None)
        else:
            sys.modules["parity_runner"] = previous


class NativeBatchTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path = Path(self.work.name)
        self.episodes_path = self.path / "episodes.json"
        self.settings_path = self.path / "settings.json"
        self.settings_path.write_text(json.dumps({
            "api_base_url": "http://127.0.0.1:1/v1",
            "client": {"model_id": "offline-fake-model"},
        }), encoding="utf-8")
        self.output = self.path / "run"

    def tearDown(self):
        self.work.cleanup()

    def invoke(self, episodes, child, *, timeout=30):
        self.episodes_path.write_text(json.dumps(episodes), encoding="utf-8")
        argv = ["native_batch.py", "--episodes", str(self.episodes_path),
                "--settings", str(self.settings_path), "--output-dir", str(self.output),
                "--episode-timeout", str(timeout)]
        original_load = runner.load_config
        # Native batch runs in /opt/balrog in Docker. Only the location of the
        # original config changes for this host test; validation is production.
        def local_config(_container_path, settings):
            return original_load(UPSTREAM / "balrog/config/config.yaml", settings)
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", argv))
            stack.enter_context(runner_alias())
            stack.enter_context(patch.object(runner, "load_config", side_effect=local_config))
            launched = stack.enter_context(patch.object(batch.subprocess, "run", side_effect=child))
            stack.enter_context(redirect_stderr(io.StringIO()))
            try:
                code = batch.main()
            except (SystemExit, ValueError) as exc:
                code = exc.code if isinstance(exc, SystemExit) else 1
            return code, launched.call_count

    def test_bad_batch_is_rejected_before_any_child(self):
        valid = frozen_case()["episode"]
        missing = {key: value for key, value in valid.items() if key != "expected_mission"}
        cases = [([], 30), ([valid, valid], 30), ([valid, {**valid, "task_id": "../bad"}], 30),
                 ([{**valid, "seed": True}], 30), ([{**valid, "task": "unknown"}], 30),
                 ([missing], 30), ([valid], 0), ([{**valid, "expected_mission": None}], 30),
                 ([{**valid, "expected_max_steps": 65}], 30),
                 ([{**valid, "expected_initial_observation_sha256": "z" * 64}], 30),
                 ([{**valid, "babyai_kwargs": {"num_dists": 1}}], 30)]
        for episodes, timeout in cases:
            with self.subTest(episodes=len(episodes), timeout=timeout):
                code, calls = self.invoke(episodes, lambda *_args, **_kwargs: self.fail("Child launched"), timeout=timeout)
                self.assertNotEqual(code, 0)
                self.assertEqual(calls, 0)
                self.assertFalse(self.output.exists())

    def test_template_settings_rejected_before_child(self):
        self.settings_path.write_text(json.dumps({"api_base_url": "http://127.0.0.1:1/v1",
                                                  "client": {"model_id": "REPLACE_MODEL_ID"}}))
        code, calls = self.invoke([frozen_case()["episode"]], lambda *_args, **_kwargs: self.fail("Child launched"))
        self.assertNotEqual(code, 0)
        self.assertEqual(calls, 0)

    def test_existing_artifacts_are_not_reused(self):
        self.output.mkdir()
        (self.output / "run_status.json").write_text('{"status":"completed"}')
        code, calls = self.invoke([frozen_case()["episode"]], lambda *_args, **_kwargs: self.fail("Child launched"))
        self.assertNotEqual(code, 0)
        self.assertEqual(calls, 0)
        self.assertEqual(json.loads((self.output / "run_status.json").read_text())["status"], "completed")

    def test_zero_exit_without_report_fails_closed(self):
        code, calls = self.invoke([frozen_case()["episode"]], lambda *_args, **_kwargs: SimpleNamespace(returncode=0))
        self.assertEqual((code, calls), (1, 1))
        status = json.loads((self.output / "run_status.json").read_text())
        self.assertEqual(status["status"], "error")
        self.assertEqual(status["completed"], [])

    def test_failed_child_stops_before_next_episode(self):
        episodes = [frozen_case()["episode"], frozen_case("babyai-pickup-seed-0")["episode"]]
        code, calls = self.invoke(episodes, lambda *_args, **_kwargs: SimpleNamespace(returncode=1))
        self.assertEqual((code, calls), (1, 1))
        status = json.loads((self.output / "run_status.json").read_text())
        self.assertEqual(status["failed_task"], episodes[0]["task_id"])
        self.assertEqual(status["completed"], [])

    def test_mismatched_report_is_not_completed(self):
        def child(command, **kwargs):
            destination = Path(command[command.index("--output-dir") + 1])
            destination.mkdir()
            (destination / "episode_result.json").write_text(json.dumps({
                "status": "completed", "mode": "native", "task_id": "wrong-task",
            }))
            return SimpleNamespace(returncode=0)
        code, calls = self.invoke([frozen_case()["episode"]], child)
        self.assertEqual((code, calls), (1, 1))
        self.assertEqual(json.loads((self.output / "run_status.json").read_text())["status"], "error")

    def test_settings_and_runner_snapshots_are_stable_across_children(self):
        episodes = [frozen_case()["episode"], frozen_case("babyai-pickup-seed-0")["episode"]]
        original_settings = json.loads(self.settings_path.read_text())
        observed_commands = []

        def child(command, **kwargs):
            observed_commands.append(command)
            settings_path = Path(command[command.index("--settings") + 1])
            self.assertEqual(json.loads(settings_path.read_text()), original_settings)
            self.assertEqual(settings_path, self.output / "inputs/settings.json")
            episode_path = Path(command[command.index("--episode") + 1])
            episode = json.loads(episode_path.read_text())
            destination = Path(command[command.index("--output-dir") + 1])
            destination.mkdir()
            (destination / "episode_result.json").write_text(json.dumps({
                "status": "completed", "mode": "native", "task_id": episode["task_id"],
            }))
            # Editing the user's source settings mid-run must not alter later
            # requests; every child should read the validated snapshot instead.
            self.settings_path.write_text('{"modified_after_preflight":true}')
            return SimpleNamespace(returncode=0)

        code, calls = self.invoke(episodes, child)
        self.assertEqual((code, calls), (0, 2))
        status = json.loads((self.output / "run_status.json").read_text())
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["completed"], [episode["task_id"] for episode in episodes])
        for filename, field in (("settings.json", "input_settings_sha256"), ("parity_runner.py", "runner_sha256")):
            self.assertEqual(hashlib.sha256((self.output / "inputs" / filename).read_bytes()).hexdigest(), status[field])
        self.assertTrue(all(Path(command[1]) == self.output / "inputs/parity_runner.py" for command in observed_commands))


if __name__ == "__main__":
    unittest.main(verbosity=2)
