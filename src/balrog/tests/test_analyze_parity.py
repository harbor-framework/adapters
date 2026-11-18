"""Synthetic offline contract tests; these are not real parity evidence."""

import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
import uuid

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "analyze", Path(__file__).resolve().parents[1] / "scripts/analyze_parity.py"
)
analyze = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analyze)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ids = ["babyai-goto-seed-0", "babyai-pickup-seed-0"]
        self.pins = {"balrog": "a" * 40, "minigrid": "b" * 40}
        self.episodes = [{"task_id": task_id, "task": f"BabyAI-MixedTrainLocal-v0/{kind}", "seed": 0,
                          "expected_max_steps": 64, "expected_initial_observation_sha256": "c" * 64}
                         for task_id, kind in zip(self.ids, ("goto", "pickup"))]
        self.manifest = self.root / "manifest.json"
        write(self.manifest, {"schema_version": 1, "source_commits": self.pins,
                              "splits": {"parity": self.ids}, "cases": [{"episode": e} for e in self.episodes]})
        self.pairs = []
        # Native means .5 and 1; Harbor means 0 and .5. SEM=.25 on each side.
        for index, (native_scores, harbor_scores) in enumerate([([1, 0], [0, 0]), ([1, 1], [0, 1])]):
            native, harbor = self.root / f"native-{index}", self.root / f"harbor-{index}"
            self.pairs.append((native, harbor))
            write(harbor / "result.json", {"finished_at": "synthetic", "stats": {
                "n_completed_trials": 2, "n_errored_trials": 0, "n_running_trials": 0,
                "n_pending_trials": 0, "n_cancelled_trials": 0, "n_retries": 0}})
            for episode, native_score, harbor_score in zip(self.episodes, native_scores, harbor_scores):
                self.write_episode(native / episode["task_id"], episode, native_score, "native")
                trial = harbor / (episode["task_id"] + "__synthetic")
                self.write_episode(trial / "agent", episode, harbor_score, "http")
                verified = self.game_result(episode, harbor_score)
                write(trial / "verifier" / "result.json", {
                    **verified, "replay_progression": harbor_score, "replay_verified": True, "finalized": True,
                    "transitions": [{"step": 0}]})
                write(trial / "result.json", {"finished_at": "synthetic", "exception_info": None,
                    "task_name": "balrog/" + episode["task_id"], "reward_valid": True,
                    "verifier_result": {"rewards": {"reward": harbor_score}},
                    "agent_info": {"name": "synthetic-test-agent", "version": "test-only"}})

    def game_result(self, episode, value):
        return {"task_id": episode["task_id"], "task": episode["task"], "seed": episode["seed"],
                "max_steps": episode["expected_max_steps"], "initial_observation_sha256": episode["expected_initial_observation_sha256"],
                "steps": 1, "progression": value, "terminated": bool(value), "truncated": False}

    def write_episode(self, directory, episode, value, mode):
        settings = {"client": {"model_id": "synthetic-test-model"}, "agent": {"type": "naive"}}
        report = {**self.game_result(episode, value), "status": "completed", "mode": mode,
                  "settings": settings, "settings_sha256": analyze.runner_hash(settings),
                  "runner_sha256": "d" * 64, "source_commits": self.pins,
                  "runtime_versions": {"python": "3.10.0", "packages": {"openai": "synthetic"}},
                  "session_id": str(uuid.uuid4()), "native_progression": value,
                  "model_calls": 1, "input_tokens": 10, "output_tokens": 2}
        write(directory / "episode_result.json", report)
        messages = [{"role": "user", "content": episode["task_id"]}]
        write(directory / "model_calls.json", [{"call": 0, "messages": messages,
              "prompt_sha256": analyze.runner_hash(messages), "raw_completion": "turn left",
              "input_tokens": 10, "output_tokens": 2}])

    def test_complete_two_run_math_disagreements_and_token_totals(self):
        result = analyze.analyze(self.manifest, self.pairs)
        self.assertEqual(result["native"]["mean"], .75)
        self.assertEqual(result["native"]["sample_sem"], .25)
        self.assertEqual(result["harbor"]["mean"], .25)
        self.assertTrue(result["run_score_ranges_overlap"])  # Touching ranges overlap.
        self.assertEqual(result["paired_runs"][0]["native_only"], [self.ids[0]])
        self.assertEqual(result["per_task"][0]["native_only_pairs"], [1, 2])
        self.assertEqual(result["token_totals"]["native"], {"input_tokens": 40, "output_tokens": 8, "model_calls": 4})
        self.assertEqual(len(result["manifest"]["sha256"]), 64)
        self.assertTrue(result["analysis_only"])
        self.assertNotIn("adapter_pr", result)
        self.assertAlmostEqual(analyze.summary([0, .5, 1])["sample_sem"], math.sqrt(1 / 12))

    def test_requires_two_independent_paired_runs(self):
        for pairs in (self.pairs[:1], [self.pairs[0], self.pairs[0]]):
            with self.subTest(pairs=pairs), self.assertRaises(analyze.ValidationError):
                analyze.analyze(self.manifest, pairs)

    def test_native_batch_failure_cannot_hide_behind_completed_episode_checkpoints(self):
        status_path = self.pairs[0][0] / "run_status.json"
        for status in ("error", "running"):
            with self.subTest(status=status):
                write(status_path, {"status": status, "task_ids": self.ids, "completed": self.ids,
                                    "error_type": "TimeoutExpired"})
                with self.assertRaisesRegex(analyze.ValidationError, "batch did not complete"):
                    analyze.analyze(self.manifest, self.pairs)

    def test_native_batch_scope_must_match_manifest_order_and_completion(self):
        status_path = self.pairs[0][0] / "run_status.json"
        valid = {"status": "completed", "task_ids": self.ids, "completed": self.ids}
        write(status_path, valid)
        self.assertEqual(analyze.analyze(self.manifest, self.pairs)["native"]["mean"], .75)
        for field in ("task_ids", "completed"):
            for values in (self.ids[:1], list(reversed(self.ids)), self.ids + ["unselected-task"]):
                with self.subTest(field=field, values=values):
                    write(status_path, {**valid, field: values})
                    with self.assertRaisesRegex(analyze.ValidationError, "differs from frozen split"):
                        analyze.analyze(self.manifest, self.pairs)

    def test_missing_episode_and_duplicate_episode_are_rejected(self):
        path = self.pairs[0][0] / self.ids[1] / "episode_result.json"
        contents = path.read_text()
        path.unlink()
        with self.assertRaisesRegex(analyze.ValidationError, "coverage"):
            analyze.analyze(self.manifest, self.pairs)
        path.write_text(contents)
        self.write_episode(self.pairs[0][0] / "duplicate", self.episodes[0], 1, "native")
        with self.assertRaisesRegex(analyze.ValidationError, "Duplicate"):
            analyze.analyze(self.manifest, self.pairs)

    def test_infrastructure_errors_cannot_be_filtered(self):
        native_path = self.pairs[0][0] / self.ids[0] / "episode_result.json"
        original = analyze.read_json(native_path)
        write(native_path, {**original, "status": "error"})
        with self.assertRaisesRegex(analyze.ValidationError, "did not complete"):
            analyze.analyze(self.manifest, self.pairs)
        write(native_path, original)
        trial_path = self.pairs[0][1] / (self.ids[0] + "__synthetic") / "result.json"
        trial = analyze.read_json(trial_path)
        write(trial_path, {**trial, "exception_info": {"exception_type": "VerifierTimeoutError"}})
        with self.assertRaisesRegex(analyze.ValidationError, "exception"):
            analyze.analyze(self.manifest, self.pairs)
        write(trial_path, trial)
        write(self.pairs[1][0] / "failed_attempt" / "error.json", {"status": "error"})
        with self.assertRaisesRegex(analyze.ValidationError, "infrastructure-error"):
            analyze.analyze(self.manifest, self.pairs)

    def test_offline_integration_artifacts_cannot_be_used_as_model_parity(self):
        write(self.pairs[0][0] / "OFFLINE_TEST_ONLY.json", {"offline_test_only": True})
        with self.assertRaisesRegex(analyze.ValidationError, "not model parity"):
            analyze.analyze(self.manifest, self.pairs)

    def test_settings_drift_and_raw_token_mismatch_are_rejected(self):
        path = self.pairs[1][0] / self.ids[0] / "episode_result.json"
        original = analyze.read_json(path)
        changed = copy.deepcopy(original)
        changed["settings"]["client"]["model_id"] = "different-synthetic-model"
        changed["settings_sha256"] = analyze.runner_hash(changed["settings"])
        write(path, changed)
        with self.assertRaisesRegex(analyze.ValidationError, "drift"):
            analyze.analyze(self.manifest, self.pairs)
        write(path, {**original, "input_tokens": 999})
        with self.assertRaisesRegex(analyze.ValidationError, "Token totals"):
            analyze.analyze(self.manifest, self.pairs)

    def test_disjoint_ranges_are_reported_without_false_success(self):
        for native, _ in self.pairs:
            for episode in self.episodes:
                self.write_episode(native / episode["task_id"], episode, 1, "native")
        result = analyze.analyze(self.manifest, self.pairs)
        self.assertFalse(result["run_score_ranges_overlap"])
        self.assertEqual(result["native"]["sample_sem"], 0)

    def test_all_committed_environment_manifests_have_parity_splits(self):
        fixtures = Path(__file__).resolve().parents[1] / "src/balrog/fixtures"
        for name, count in (("babyai", 50), ("babaisai", 120), ("textworld", 30),
                            ("crafter", 10), ("nle", 5), ("minihack", 40)):
            with self.subTest(environment=name):
                path = fixtures / ("manifest.json" if name == "babyai" else name + "_manifest.json")
                manifest = analyze.load_manifest(path, "parity")
                self.assertEqual(manifest["env_name"], name)
                self.assertEqual(len(manifest["task_ids"]), count)

    def test_fractional_crafter_scores_are_averaged_without_binarizing(self):
        manifest = analyze.read_json(self.manifest)
        for case in manifest["cases"]:
            case["episode"]["env_name"] = "crafter"
        write(self.manifest, manifest)
        expected_native = [3 / 22, 5 / 22]
        expected_harbor = [1 / 22, 3 / 22]
        for (native, harbor), native_scores, harbor_scores in zip(
                self.pairs, ([2 / 22, 4 / 22], [4 / 22, 6 / 22]),
                ([0, 2 / 22], [2 / 22, 4 / 22])):
            for episode, native_score, harbor_score in zip(self.episodes, native_scores, harbor_scores):
                self.write_episode(native / episode["task_id"], episode, native_score, "native")
                trial = harbor / (episode["task_id"] + "__synthetic")
                self.write_episode(trial / "agent", episode, harbor_score, "http")
                verified = analyze.read_json(trial / "verifier/result.json")
                verified.update(progression=harbor_score, replay_progression=harbor_score,
                                terminated=bool(harbor_score))
                write(trial / "verifier/result.json", verified)
                result = analyze.read_json(trial / "result.json")
                result["verifier_result"]["rewards"]["reward"] = harbor_score
                write(trial / "result.json", result)
        result = analyze.analyze(self.manifest, self.pairs)
        for actual, expected in zip(result["native"]["runs"], expected_native):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(result["harbor"]["runs"], expected_harbor):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(result["native"]["mean"], 4 / 22)
        self.assertAlmostEqual(result["harbor"]["mean"], 2 / 22)
        self.assertAlmostEqual(result["native"]["sample_sem"], 1 / 22)
        self.assertEqual(result["metric"], "crafter native progression")

    def test_fractional_score_range_and_nonfinite_values_are_rejected(self):
        episode = {**self.episodes[0], "env_name": "crafter"}
        for value in (-0.001, 1.001, float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(analyze.ValidationError):
                analyze.check_game_result(self.game_result(episode, value), episode, "synthetic")
        result = self.game_result(episode, 2 / 22)
        result["terminated"] = False
        self.assertEqual(analyze.check_game_result(result, episode, "synthetic"), 2 / 22)

    def test_crafter_native_state_evidence_is_explicit_and_never_applies_to_other_games(self):
        manifest = analyze.read_json(self.manifest)
        for case in manifest["cases"]:
            case["episode"]["env_name"] = "crafter"
        write(self.manifest, manifest)
        paths = []
        for _, harbor in self.pairs:
            for episode in self.episodes:
                path = harbor / (episode["task_id"] + "__synthetic") / "verifier/result.json"
                verified = analyze.read_json(path)
                verified.update(env_name="crafter", replay_verified=False, replay_progression=None,
                                scoring_mode="authoritative_native_state",
                                replay_diagnostic={"code":"crafter_native_object_order_nondeterminism",
                                                   "first_divergent_step": 0})
                write(path, verified)
                paths.append(path)
        result = analyze.analyze(self.manifest, self.pairs)
        evidence = result["paired_runs"][0]["evidence"]["harbor"][self.ids[0]]
        self.assertEqual(evidence["verification_mode"], "authoritative_native_state")
        verified = analyze.read_json(paths[0])
        for change in ({"env_name":"nle"}, {"replay_diagnostic":{}},
                       {"scoring_mode":"deterministic_replay"}, {"replay_progression":0}):
            write(paths[0], {**verified, **change})
            with self.assertRaises(analyze.ValidationError):
                analyze.analyze(self.manifest, self.pairs)
        write(paths[0], verified)
        for case in manifest["cases"]:
            case["episode"]["env_name"] = "nle"
        write(self.manifest, manifest)
        with self.assertRaises(analyze.ValidationError):
            analyze.analyze(self.manifest, self.pairs)


if __name__ == "__main__":
    unittest.main()
