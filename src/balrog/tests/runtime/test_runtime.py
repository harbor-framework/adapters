"""Integration tests against real BabyAI, without a model or Docker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from runtime_support import TEMPLATE, configure_upstream, frozen_case, game_server

UPSTREAM = configure_upstream()
CONFIG_PATH = UPSTREAM / "balrog/config/config.yaml"
Episode, build_server = game_server().Episode, game_server().build_server

TOKEN = "local-integration-test-token"


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = frozen_case()["episode"]
        self.config_path = CONFIG_PATH

    def test_frozen_manifest_matches_pinned_environment(self):
        episode = Episode(self.manifest, self.config_path)
        try:
            self.assertEqual(episode.mission, self.manifest["expected_mission"])
            self.assertEqual(episode.initial_hash,
                             self.manifest["expected_initial_observation_sha256"])
            self.assertTrue(episode.result()["replay_verified"])
        finally:
            episode.close()

    def test_manifest_drift_rejects_startup(self):
        for key, wrong, label in (
            ("expected_mission", "go to the red key", "mission"),
            ("expected_initial_observation_sha256", "0" * 64, "initial observation"),
            ("expected_max_steps", 65, "step budget"),
        ):
            with self.subTest(field=key):
                with self.assertRaisesRegex(ValueError, label + " differs from frozen manifest"):
                    Episode({**self.manifest, key: wrong}, self.config_path)


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.episode = Episode(
            {"task": "BabyAI-MixedTrainLocal-v0/goto", "seed": 0},
            CONFIG_PATH,
        )
        self.server = build_server(self.episode, TOKEN, ("127.0.0.1", 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.work = tempfile.TemporaryDirectory(dir=Path(__file__).parent)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.episode.close()
        self.work.cleanup()

    def request(self, path, payload=None, authorized=False):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + TOKEN
        body = None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(self.url + path, data=body, headers=headers), timeout=10) as response:
            return json.load(response)

    def verify(self, token=TOKEN):
        output = Path(self.work.name) / "verifier"
        completed = subprocess.run(
            [sys.executable, str(TEMPLATE / "tests/verifier.py"),
             "--server", self.url, "--output-dir", str(output)],
            env={**os.environ, "RESULT_TOKEN": token}, capture_output=True, text=True, timeout=30,
        )
        return completed, output

    def test_oracle_real_environment_replay_and_privacy(self):
        obs = self.request("/observation")
        self.assertEqual(obs["step"], 0)
        self.assertEqual(self.request("/observation"), obs)
        for private in ("progression", "reward", "grid", "info", "seed", "transitions"):
            self.assertNotIn(private, obs)
        with self.assertRaises(HTTPError) as rejected:
            self.request("/result")
        self.assertEqual(rejected.exception.code, 401)
        actions = frozen_case()["oracle"]["actions"]
        for step, action in enumerate(actions):
            obs = self.request("/action", {"action": action, "expected_step": step})
        self.assertTrue(obs["done"])
        completed, output = self.verify()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((output / "reward.txt").read_text().strip(), "1")
        result = json.loads((output / "result.json").read_text())
        self.assertTrue(result["replay_verified"])
        self.assertEqual(result["steps"], len(actions))
        with self.assertRaises(HTTPError) as rejected:
            self.request("/action", {"action": "turn left", "expected_step": result["steps"]})
        self.assertEqual(rejected.exception.code, 409)

    def test_no_actions_scores_zero_and_freezes(self):
        completed, output = self.verify()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((output / "reward.txt").read_text().strip(), "0")
        with self.assertRaises(HTTPError) as rejected:
            self.request("/action", {"action": "go forward", "expected_step": 0})
        self.assertEqual(rejected.exception.code, 409)

    def test_budget_failure_and_retry_does_not_duplicate_step(self):
        self.request("/action", {"action": "turn left", "expected_step": 0})
        with self.assertRaises(HTTPError) as rejected:
            self.request("/action", {"action": "turn left", "expected_step": 0})
        self.assertEqual(rejected.exception.code, 409)
        self.assertEqual(self.request("/observation")["step"], 1)
        for step in range(1, self.episode.max_steps):
            obs = self.request("/action", {"action": "turn left", "expected_step": step})
        self.assertTrue(obs["truncated"])
        completed, output = self.verify()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((output / "reward.txt").read_text().strip(), "0")

    def test_invalid_action_has_native_fallback_and_feedback(self):
        obs = self.request("/action", {"action": "not an action", "expected_step": 0})
        self.assertIn("Defaulted to action: go forward", obs["text"]["long_term_context"])
        result = self.request("/result", authorized=True)
        self.assertEqual(result["transitions"][0]["executed_action"], "go forward")
        self.assertTrue(result["replay_verified"])

    def test_long_invalid_output_preserves_native_fallback(self):
        raw_action = "invalid action " * 2000
        obs = self.request("/action", {"action": raw_action, "expected_step": 0})
        self.assertIn("Defaulted to action: go forward", obs["text"]["long_term_context"])
        result = self.request("/result", authorized=True)
        self.assertEqual(result["transitions"][0]["raw_action"], raw_action)
        self.assertEqual(result["transitions"][0]["executed_action"], "go forward")
        self.assertTrue(result["replay_verified"])

    def test_bad_auth_does_not_create_or_reuse_reward(self):
        output = Path(self.work.name) / "verifier"
        output.mkdir()
        (output / "reward.txt").write_text("1\n")
        (output / "reward.json").write_text('{"reward": 1}\n')
        completed, output = self.verify(token="wrong-token")
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse((output / "reward.txt").exists())
        self.assertFalse((output / "reward.json").exists())
        self.assertTrue((output / "error.json").exists())
        # Unauthorized verification does not freeze the game.
        self.assertEqual(self.request("/action", {"action": "turn left", "expected_step": 0})["step"], 1)

    def test_replay_detects_corrupt_trajectory(self):
        self.request("/action", {"action": "turn left", "expected_step": 0})
        self.episode.transitions[0]["observation_sha256"] = "deliberate-corruption"
        completed, output = self.verify()
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse((output / "reward.txt").exists())

    def test_cli_observe_and_action(self):
        client = TEMPLATE / "environment/play.py"
        obs = subprocess.run([sys.executable, str(client), "--server", self.url, "observe"],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(obs.returncode, 0, obs.stderr)
        self.assertEqual(json.loads(obs.stdout)["step"], 0)
        action = subprocess.run([sys.executable, str(client), "--server", self.url, "act", "turn left"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(action.returncode, 0, action.stderr)
        self.assertEqual(json.loads(action.stdout)["step"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
