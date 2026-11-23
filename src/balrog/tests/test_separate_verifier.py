"""Offline grading and trusted collection contracts; no games, Docker, or models."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest


PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = PROJECT / "src/balrog"
TEMPLATE = PACKAGE / "task-template"
VERIFIER = TEMPLATE / "tests/verifier.py"
EXPORTER = TEMPLATE / "environment/export_result.py"
TOKEN = "separate-verifier-test-token"


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def frozen_positive():
    """Reconstruct the saved three-action native record, without playing a game."""
    episode = json.loads((PACKAGE / "fixtures/episode.json").read_text(encoding="utf-8"))
    oracle = json.loads((PACKAGE / "fixtures/oracle_actions.json").read_text(encoding="utf-8"))
    transitions = []
    for step, (action, expected) in enumerate(zip(oracle["actions"], oracle["expected_transitions"])):
        transitions.append({
            "step": step, "raw_action": action, "executed_action": expected["executed_action"],
            "observation_sha256": expected["observation"], "reward": expected["reward"],
            "terminated": expected["terminated"], "truncated": expected["truncated"],
            "budget_exhausted": False,
        })
    result = {
        "schema_version": 1, "env_name": episode.get("env_name", "babyai"),
        "task_id": episode["task_id"], "task": episode["task"], "seed": episode["seed"],
        "progression": oracle["expected_progression"],
        "replay_progression": oracle["expected_progression"], "replay_verified": True,
        "scoring_mode": "deterministic_replay", "replay_diagnostic": None,
        "finalized": True, "terminated": True, "truncated": False,
        "steps": len(transitions), "max_steps": episode["expected_max_steps"],
        "initial_observation_sha256": episode["expected_initial_observation_sha256"],
        "transitions": transitions,
    }
    return episode, result


class OfflineVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="balrog-offline-grader-")
        self.root = Path(self.temporary.name)
        self.result_path = self.root / "trusted-game/result.json"
        self.task_config = self.root / "tests/task_config.json"
        self.output = self.root / "verifier"
        self.episode, self.positive = frozen_positive()
        write_json(self.task_config, self.episode)

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self, *, use_result_env=False):
        env = {key: value for key, value in os.environ.items()
               if key not in {"RESULT_TOKEN", "BALROG_SERVER", "BALROG_RESULT_PATH"}}
        command = [sys.executable, "-I", str(VERIFIER),
                   "--task-config", str(self.task_config), "--output-dir", str(self.output)]
        if use_result_env:
            env["BALROG_RESULT_PATH"] = str(self.result_path)
        else:
            command += ["--result-path", str(self.result_path)]
        return subprocess.run(command, env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=20)

    def stale_outputs(self):
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "reward.txt").write_text("1\n", encoding="utf-8")
        write_json(self.output / "reward.json", {"reward": 1})
        write_json(self.output / "result.json", {"old_result": True})
        write_json(self.output / "error.json", {"old_error": True})

    def assert_failed_without_stale_score(self, completed):
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        for name in ("reward.txt", "reward.json", "result.json"):
            self.assertFalse((self.output / name).exists(), name)
        error = json.loads((self.output / "error.json").read_text(encoding="utf-8"))
        self.assertIn("error_type", error)
        self.assertNotIn("old_error", error)

    def test_frozen_positive_is_graded_without_live_server_or_token(self):
        write_json(self.result_path, self.positive)
        self.stale_outputs()
        completed = self.verify()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(float((self.output / "reward.txt").read_text()), 1)
        self.assertEqual(json.loads((self.output / "result.json").read_text(encoding="utf-8")), self.positive)
        self.assertFalse((self.output / "reward.json").exists())
        self.assertFalse((self.output / "error.json").exists())

    def test_valid_unfinished_native_zero_is_a_scored_outcome(self):
        negative = {**self.positive, "progression": 0.0, "replay_progression": 0.0,
                    "terminated": False, "steps": 0, "transitions": []}
        write_json(self.result_path, negative)
        completed = self.verify(use_result_env=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(float((self.output / "reward.txt").read_text()), 0)
        self.assertEqual(json.loads((self.output / "result.json").read_text(encoding="utf-8")), negative)

    def test_frozen_fractional_reference_is_not_binarized(self):
        manifest = json.loads((PACKAGE / "fixtures/crafter_manifest.json").read_text(encoding="utf-8"))
        case = manifest["cases"][0]
        episode, reference = case["episode"], case["reference"]
        result = {**self.positive, "env_name": episode["env_name"],
                  "task_id": episode["task_id"], "task": episode["task"], "seed": episode["seed"],
                  "max_steps": episode["expected_max_steps"],
                  "initial_observation_sha256": episode["expected_initial_observation_sha256"],
                  "progression": reference["expected_progression"],
                  "replay_progression": reference["expected_progression"],
                  "terminated": reference["expected_terminated"], "truncated": reference["expected_truncated"],
                  "steps": len(reference["actions"]), "transitions": reference["expected_transitions"]}
        write_json(self.task_config, episode)
        write_json(self.result_path, result)
        completed = self.verify()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(float((self.output / "reward.txt").read_text()), 2 / 22)

    def test_explicit_crafter_divergence_keeps_authoritative_fractional_score(self):
        episode = {**self.episode, "env_name": "crafter", "task": "default",
                   "task_id": "crafter-default-seed-0", "expected_max_steps": 2000}
        # Schema-level fixture for the existing explicit exception, not a new
        # simulated claim or evidence of a completed Crafter trajectory.
        result = {**self.positive, "env_name": "crafter", "task": "default",
                  "task_id": episode["task_id"], "max_steps": 2000,
                  "progression": 2 / 22, "replay_progression": None,
                  "replay_verified": False, "scoring_mode": "authoritative_native_state",
                  "replay_diagnostic": {"code": "crafter_native_object_order_nondeterminism",
                                        "first_divergent_step": 1}}
        write_json(self.task_config, episode)
        write_json(self.result_path, result)
        completed = self.verify()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(float((self.output / "reward.txt").read_text()), 2 / 22)

    def test_missing_current_artifact_cannot_reuse_previous_success(self):
        write_json(self.result_path, self.positive)
        self.assertEqual(self.verify().returncode, 0)
        self.result_path.unlink()
        write_json(self.output / "reward.json", {"reward": 1})
        self.assert_failed_without_stale_score(self.verify())

    def test_malformed_artifact_never_becomes_zero_or_previous_reward(self):
        for serialized in ("{incomplete", "[]", "null", "1"):
            with self.subTest(serialized=serialized):
                self.result_path.parent.mkdir(parents=True, exist_ok=True)
                self.result_path.write_text(serialized, encoding="utf-8")
                self.stale_outputs()
                self.assert_failed_without_stale_score(self.verify())

    def test_result_is_bound_to_all_frozen_task_identity_fields(self):
        changes = [
            ("task_id", "babyai-goto-seed-1"), ("task", "BabyAI-MixedTrainLocal-v0/pickup"),
            ("seed", 1), ("seed", False), ("env_name", "textworld"), ("max_steps", 65),
            ("initial_observation_sha256", "0" * 64),
        ]
        for key, value in changes:
            with self.subTest(key=key):
                write_json(self.result_path, {**self.positive, key: value})
                self.stale_outputs()
                self.assert_failed_without_stale_score(self.verify())

    def test_missing_identity_is_rejected_instead_of_defaulted_from_task(self):
        for key in ("task_id", "task", "seed", "env_name", "max_steps", "initial_observation_sha256"):
            with self.subTest(key=key):
                result = copy.deepcopy(self.positive)
                del result[key]
                write_json(self.result_path, result)
                self.stale_outputs()
                self.assert_failed_without_stale_score(self.verify())

    def test_missing_or_malformed_baked_task_config_fails_closed(self):
        write_json(self.result_path, self.positive)
        self.task_config.unlink()
        self.stale_outputs()
        self.assert_failed_without_stale_score(self.verify())
        for config in ([], {}, {"task_id": self.episode["task_id"]}):
            with self.subTest(config=config):
                write_json(self.task_config, config)
                self.stale_outputs()
                self.assert_failed_without_stale_score(self.verify())

    def test_invalid_native_score_or_replay_remains_an_error(self):
        for change in ({"progression": float("nan")}, {"progression": True},
                       {"replay_progression": 0}, {"replay_verified": False},
                       {"finalized": False}):
            with self.subTest(change=change):
                write_json(self.result_path, {**self.positive, **change})
                self.stale_outputs()
                self.assert_failed_without_stale_score(self.verify())


@contextmanager
def fake_game(result, *, status=200, raw_body=None):
    """Exercise only the authenticated HTTP transport, not a simulator."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, self.headers.get("Authorization")))
            actual = status if self.headers.get("Authorization") == "Bearer " + TOKEN else 401
            body = raw_body if raw_body is not None else json.dumps(result).encode("utf-8")
            self.send_response(actual)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class TrustedExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="balrog-trusted-export-")
        self.output = Path(self.temporary.name) / "result.json"
        self.pending = self.output.with_suffix(self.output.suffix + ".tmp")
        self.episode, self.positive = frozen_positive()

    def tearDown(self):
        self.temporary.cleanup()

    def export(self, server, token=TOKEN):
        env = {**os.environ, "RESULT_TOKEN": token}
        return subprocess.run(
            [sys.executable, "-I", str(EXPORTER), "--server", server,
             "--output", str(self.output), "--request-timeout", "2"],
            env=env, capture_output=True, text=True, encoding="utf-8", timeout=10,
        )

    def put_stale_export(self):
        write_json(self.output, {"old_result": True})
        self.pending.write_text("incomplete previous write", encoding="utf-8")

    def test_collector_uses_private_result_endpoint_and_preserves_record(self):
        self.put_stale_export()
        with fake_game(self.positive) as (server, requests):
            completed = self.export(server)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(requests, [("/result", "Bearer " + TOKEN)])
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8")), self.positive)
        self.assertFalse(self.pending.exists())
        self.assertNotIn(TOKEN, completed.stdout + completed.stderr)

    def test_failed_collection_removes_old_result_and_pending_file(self):
        for options, token in (({"status": 500}, TOKEN), ({"raw_body": b"{broken"}, TOKEN), ({}, "wrong-token")):
            with self.subTest(options=options, token=token):
                self.put_stale_export()
                with fake_game(self.positive, **options) as (server, requests):
                    completed = self.export(server, token)
                self.assertEqual(requests, [("/result", "Bearer " + token)],
                                 "The intended HTTP/JSON/auth failure must actually be exercised")
                self.assertNotEqual(completed.returncode, 0)
                self.assertFalse(self.output.exists())
                self.assertFalse(self.pending.exists())
                self.assertNotIn(TOKEN, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
