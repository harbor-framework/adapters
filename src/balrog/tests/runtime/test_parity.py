"""Offline parity checks: real upstream agents/environments, fake model client."""

from __future__ import annotations

import json
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

from runtime_support import configure_upstream, frozen_case, game_server, parity_runner

UPSTREAM = configure_upstream()

from balrog.agents import AgentFactory
from balrog.client import LLMResponse, OpenAIWrapper
from omegaconf import OmegaConf

Episode, build_server = game_server().Episode, game_server().build_server
runner = parity_runner()
HTTPEnvironment, digest, load_config = runner.HTTPEnvironment, runner.digest, runner.load_config
run_episode, run_original_episode = runner.run_episode, runner.run_original_episode

CONFIG_PATH = UPSTREAM / "balrog/config/config.yaml"
MANIFEST = frozen_case()["episode"]
SETTINGS = {"api_base_url": "http://127.0.0.1:1/v1", "client": {"model_id": "offline-fake-model"}}


class FakeClient:
    def __init__(self, config, completions, failure=None):
        self.responses = iter(completions)
        self.failure = failure
        self.converter = OpenAIWrapper(config.client)

    def convert_messages(self, messages):
        return self.converter.convert_messages(messages)

    def generate(self, messages):
        if self.failure:
            raise self.failure
        return LLMResponse("offline-fake-model", next(self.responses), "stop", 7, 3, None)


def new_agent(config, completions, failure=None):
    agent = AgentFactory(config).create_agent()
    agent.client = FakeClient(config, completions, failure)
    return agent


def metadata(config):
    return {"agent": OmegaConf.to_container(config.agent, resolve=True),
            "client": OmegaConf.to_container(config.client, resolve=True),
            "api_base_url": SETTINGS["api_base_url"], "limits": {}}


class ParityTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path = Path(self.work.name)
        self.config = load_config(CONFIG_PATH, SETTINGS)

    def tearDown(self):
        self.work.cleanup()

    @contextmanager
    def live_http_episode(self, manifest):
        episode = Episode(manifest, CONFIG_PATH)
        server = build_server(episode, "offline-test-only", ("127.0.0.1", 0))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield episode, HTTPEnvironment(f"http://127.0.0.1:{server.server_port}")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            episode.close()

    def test_http_service_supplies_full_identity_without_task_id_argument(self):
        full_id = MANIFEST["task_id"] + "-authoritative-name-longer-than-the-harbor-trial-directory"
        manifest = {**MANIFEST, "task_id": full_id}
        with self.live_http_episode(manifest) as (episode, environment):
            self.assertEqual(environment.observation()["task_id"], full_id)
            report = run_episode(new_agent(self.config, frozen_case()["oracle"]["actions"]),
                                 environment, self.path, metadata(self.config), mode="http")
            self.assertEqual(report["task_id"], full_id)
            self.assertEqual(report["source_commits"], runner.source_commits(full_id))
            self.assertEqual(episode.result()["progression"], 1)
        saved = json.loads((self.path / "episode_result.json").read_text())
        self.assertEqual(saved["task_id"], full_id)

    def test_explicit_wrong_task_identity_fails_before_model_or_game_action(self):
        with self.live_http_episode(MANIFEST) as (episode, environment):
            agent = new_agent(self.config, [], failure=AssertionError("Model must not be called"))
            with self.assertRaisesRegex(ValueError, "identity differs"):
                run_episode(agent, environment, self.path, metadata(self.config), mode="http",
                            task_id="babyai-wrong-identity-seed-0")
            self.assertEqual(episode.transitions, [])
        report = json.loads((self.path / "episode_result.json").read_text())
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(report["steps"], 0)

    def run_pair(self, completions):
        native_report = run_original_episode(new_agent(self.config, completions), self.config, MANIFEST,
                                             self.path / "native", metadata(self.config))
        server_episode = Episode(MANIFEST, CONFIG_PATH)
        server = build_server(server_episode, "offline-test-only", ("127.0.0.1", 0))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            http_report = run_episode(new_agent(self.config, completions),
                                      HTTPEnvironment(f"http://127.0.0.1:{server.server_port}"),
                                      self.path / "http", metadata(self.config), mode="http",
                                      task_id=MANIFEST["task_id"])
            result = server_episode.result()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            server_episode.close()
        native_calls = json.loads((self.path / "native/model_calls.json").read_text())
        http_calls = json.loads((self.path / "http/model_calls.json").read_text())
        self.assertEqual(len(native_calls), len(http_calls))
        for left, right in zip(native_calls, http_calls):
            for field in ("messages", "prompt_sha256", "request_messages", "request_prompt_sha256",
                          "raw_completion", "parsed_action", "observation_sha256", "next_observation_sha256"):
                self.assertEqual(left[field], right[field], field)
        for field in ("steps", "max_steps", "terminated", "truncated", "initial_observation_sha256",
                      "settings_sha256", "runtime_versions", "runner_sha256", "source_commits"):
            self.assertEqual(native_report[field], http_report[field], field)
        self.assertEqual(native_report["native_progression"], result["progression"])
        self.assertNotIn("native_progression", http_report)
        self.assertEqual(http_report["input_tokens"], 7 * len(http_calls))
        self.assertEqual(http_report["output_tokens"], 3 * len(http_calls))
        self.assertEqual(http_report["settings_sha256"], digest(http_report["settings"]))
        return native_report, result, native_calls

    def test_unvalidated_agent_variants_are_rejected(self):
        for name in ("cot", "robust_naive", "robust_cot", "few_shot"):
            with self.subTest(agent=name), self.assertRaises(ValueError):
                load_config(CONFIG_PATH, {**SETTINGS, "agent": {"type": name}})

    def test_oracle_prompts_match_exactly(self):
        actions = frozen_case()["oracle"]["actions"]
        # Punctuation is intentionally stripped by the real upstream NaiveAgent.
        raw = ["`" + action + "`" for action in actions]
        native, result, calls = self.run_pair(raw)
        self.assertEqual(native["native_progression"], 1)
        self.assertTrue(result["replay_verified"])
        self.assertEqual(calls[0]["raw_completion"], raw[0])
        self.assertEqual(calls[0]["parsed_action"], actions[0])
        self.assertEqual(calls[0]["messages"][0]["role"], "user")

    def test_actual_trajectories_validate_with_harbor_atif(self):
        validator = os.environ.get("HARBOR_PYTHON")
        if not validator:
            self.skipTest("Set HARBOR_PYTHON to a Python 3.12 interpreter with Harbor for ATIF validation")
        self.run_pair(frozen_case()["oracle"]["actions"])
        code = ("import sys; from pathlib import Path; "
                "from harbor.models.trajectories.trajectory import Trajectory; "
                "[Trajectory.model_validate_json(Path(p).read_text()) for p in sys.argv[1:]]")
        checked = subprocess.run([str(validator), "-c", code, str(self.path / "native/trajectory.json"),
                                  str(self.path / "http/trajectory.json")], capture_output=True, text=True, timeout=60)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_long_invalid_response_and_history_eviction_match(self):
        long_output = "?? invalid response! " * 2000
        native, result, calls = self.run_pair([long_output] + ["turn left"] * 64)
        self.assertEqual(native["native_progression"], 0)
        self.assertEqual(native["steps"], 64)
        self.assertTrue(native["truncated"])
        self.assertEqual(calls[0]["raw_completion"], long_output)
        self.assertGreater(len(calls[0]["parsed_action"]), 512)
        self.assertEqual(result["transitions"][0]["raw_action"], calls[0]["parsed_action"])
        self.assertEqual(result["transitions"][0]["executed_action"], "go forward")
        self.assertEqual(calls[1]["messages"][-2]["content"], calls[0]["parsed_action"])
        self.assertIn("Defaulted to action: go forward", calls[1]["messages"][-1]["content"])
        self.assertLessEqual(len(calls[-1]["messages"]), 33)

    def test_api_error_is_not_zero_score(self):
        with self.assertRaises(ConnectionError):
            run_original_episode(new_agent(self.config, [], ConnectionError("fake failure")),
                                 self.config, MANIFEST, self.path, metadata(self.config))
        report = json.loads((self.path / "episode_result.json").read_text())
        self.assertEqual(report["status"], "error")
        self.assertNotIn("native_progression", report)
        self.assertEqual(report["steps"], 0)
        calls = json.loads((self.path / "model_calls.json").read_text())
        self.assertEqual(calls[0]["error_type"], "ConnectionError")

    def test_call_budget_failure_preserves_partial_usage(self):
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            run_original_episode(new_agent(self.config, ["turn left"] * 64), self.config, MANIFEST,
                                 self.path, metadata(self.config), max_model_calls=2)
        report = json.loads((self.path / "episode_result.json").read_text())
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["model_calls"], 2)
        self.assertEqual(report["input_tokens"], 14)
        self.assertNotIn("native_progression", report)

    def test_unsafe_or_implicit_endpoint_settings_rejected(self):
        for change in ({"api_base_url": None}, {"api_base_url": "https://user:password@example.test/v1"},
                       {"api_key": "never-allowed"}, {"client": {"model_id": "REPLACE_MODEL_ID"}}):
            with self.subTest(change=list(change)):
                with self.assertRaises(ValueError):
                    load_config(CONFIG_PATH, {**SETTINGS, **change})
        self.assertEqual(os.environ["OPENAI_BASE_URL"], SETTINGS["api_base_url"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
