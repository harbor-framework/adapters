"""Suite scope, source isolation, and reference artifact regression checks; no Docker/API."""
import copy
from datetime import timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from balrog import adapter, suite
from separate_verifier_support import assert_separate_verifier_contract

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("suite_reference_checker", PROJECT / "scripts/check_suite_reference.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class SuiteGenerationTests(unittest.TestCase):
    def assert_modified_manifest_rejected(self, change, message):
        manifest = copy.deepcopy(suite.load_environment_manifest("babaisai"))
        change(manifest)
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            write_json(package / "fixtures/babaisai_manifest.json", manifest)
            write_json(package / "fixtures/suite_scope.json",
                       checker.read_json(adapter.PACKAGE_DIR / "fixtures/suite_scope.json"))
            with patch.object(suite, "PACKAGE_DIR", package):
                with self.assertRaisesRegex(ValueError, message):
                    suite.load_environment_manifest("babaisai")

    def test_replacing_a_whole_family_does_not_preserve_valid_scope(self):
        def replace_family(manifest):
            original = manifest["cases"][0]["episode"]["task"]
            for case in manifest["cases"]:
                if case["episode"]["task"] == original:
                    case["episode"]["task"] = "env/not-in-pinned-config"
        self.assert_modified_manifest_rejected(replace_family, "Unexpected frozen task")

    def test_wrong_environment_subrepository_pin_is_rejected(self):
        self.assert_modified_manifest_rejected(
            lambda manifest: manifest["source_commits"].update(baba="0" * 40), "source revisions")

    def test_changed_native_budget_or_manifest_schema_is_rejected(self):
        self.assert_modified_manifest_rejected(
            lambda manifest: manifest["cases"][0]["episode"].update(expected_max_steps=101), "native step budget")
        self.assert_modified_manifest_rejected(lambda manifest: manifest.update(schema_version=2), "schema/source")

    def test_all_environments_keep_every_frozen_task_and_seed(self):
        all_cases = suite.select_suite_cases(["all"])
        self.assertEqual(len(all_cases), 255)
        self.assertEqual(len({c["episode"]["task_id"] for c in all_cases}), 255)
        for name, count in suite.COUNTS.items():
            cases = [c for c in all_cases if c["episode"]["env_name"] == name]
            self.assertEqual(len(cases), count)
            for task in {c["episode"]["task"] for c in cases}:
                self.assertEqual({c["episode"]["seed"] for c in cases if c["episode"]["task"] == task},
                                 set(range(suite.SEEDS[name])))
        self.assertEqual(len(suite.select_suite_cases(["all"], "sanity")), 58)

    def test_runner_source_declarations_match_every_frozen_episode(self):
        runner_spec = importlib.util.spec_from_file_location("suite_runner_pins", adapter.PACKAGE_DIR / "parity_runner.py")
        runner = importlib.util.module_from_spec(runner_spec)
        runner_spec.loader.exec_module(runner)
        for environment in suite.ENVIRONMENTS:
            manifest = suite.load_environment_manifest(environment)
            for case in manifest["cases"]:
                self.assertEqual(runner.source_commits(case["episode"]["task_id"]), manifest["source_commits"])
        with self.assertRaises(ValueError):
            runner.source_commits("unknown-task-seed-0")

    def test_partial_references_remain_partial_in_generated_tasks(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "tasks"
            with patch.object(suite, "_source_archive", return_value=b"pinned fixture archive"):
                paths = adapter.BALROGAdapter(output, environments=["crafter", "nle"], split="sanity").run()
            self.assertEqual(len(paths), 2)
            for path in paths:
                episode = checker.read_json(path / "environment/episode.json")
                assert_separate_verifier_contract(self, path, episode)
                status = checker.read_json(path / "solution/reference_status.json")
                reference = checker.read_json(path / "solution/oracle_actions.json")
                self.assertFalse(status["full_oracle_available"])
                self.assertTrue(status["reference_available"])
                self.assertLess(status["expected_progression"], 1)
                self.assertIn("not_full_oracle", reference["kind"])
                self.assertEqual({p.name for p in (path / "environment/vendor").iterdir()},
                                 {"balrog.tar.gz", "manifest.json"})

    def test_bad_asset_checksum_fails_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_lock = checker.read_json(adapter.PACKAGE_DIR / "fixtures/runtime_sources.json")
            resource = source_lock["babaisai"][0]
            asset = root / "assets" / resource["path"]
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"wrong source revision")
            output = root / "tasks"
            with patch.object(suite, "_source_archive", return_value=b"pinned fixture archive"):
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    adapter.BALROGAdapter(output, environments=["babaisai"], limit=1,
                                          assets_dir=asset.parent).run()
            self.assertFalse(output.exists())

    def test_main_image_copy_inputs_exclude_game_assets_and_solution(self):
        dockerfile = (adapter.PACKAGE_DIR / "task-template/environment/Dockerfile").read_text()
        copies = [line for line in dockerfile.splitlines() if line.startswith("COPY ")]
        self.assertEqual(copies, ["COPY requirements-agent.lock /opt/requirements-agent.lock",
                                 "COPY vendor/balrog.tar.gz /tmp/balrog.tar.gz",
                                 "COPY play.py /usr/local/lib/balrog/play.py"])
        self.assertNotIn("balrog/environments", dockerfile)
        self.assertNotIn("assets.tar.gz", dockerfile)
        self.assertNotIn("episode.json", dockerfile)
        self.assertNotIn("solution/", dockerfile)


class SuiteReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dataset, self.job = self.root / "tasks", self.root / "job"
        self.case = copy.deepcopy(suite.load_environment_manifest("babaisai")["cases"][0])
        self.prepare(self.case)

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, case):
        ep = case["episode"]
        reference = case.get("oracle") or case.get("reference")
        if reference is None:
            probe = case["native_probe"]
            reference = {"kind": "native_smoke_diagnostic_not_full_oracle", "actions": probe["actions"],
                         "expected_progression": probe["final_progression"]}
        self.task = self.dataset / ep["task_id"]
        self.trial = self.job / (ep["task_id"] + "__test")
        self.task.mkdir(parents=True, exist_ok=True)
        (self.task / "task.toml").write_text("[task]\nname = 'balrog/" + ep["task_id"] + "'\n")
        write_json(self.task / "environment/episode.json", ep)
        write_json(self.task / "solution/oracle_actions.json", reference)
        write_json(self.task / "solution/reference_status.json", {
            "full_oracle_available": bool(case.get("oracle") and reference["expected_progression"] == 1),
            "reference_available": True, "expected_progression": reference["expected_progression"]})
        native = reference.get("expected_transitions", [{} for _ in reference["actions"]])
        transitions = []
        for index, action in enumerate(reference["actions"]):
            transition = {"step": index, "raw_action": action, "executed_action": action,
                          "observation_sha256": "a" * 64, "reward": 0.0,
                          "terminated": False, "truncated": False,
                          "budget_exhausted": index + 1 >= ep["expected_max_steps"]}
            transition.update({("observation_sha256" if key == "observation" else key): value
                               for key, value in native[index].items()})
            transitions.append(transition)
        score = reference["expected_progression"]
        write_json(self.trial / "verifier/result.json", {
            "schema_version": 1, "task_id": ep["task_id"], "task": ep["task"], "seed": ep["seed"],
            "env_name": ep["env_name"], "max_steps": ep["expected_max_steps"],
            "initial_observation_sha256": ep["expected_initial_observation_sha256"],
            "replay_verified": True, "finalized": True, "progression": score, "replay_progression": score,
            "steps": len(transitions), "transitions": transitions,
            "terminated": transitions[-1]["terminated"], "truncated": transitions[-1]["truncated"]})
        (self.trial / "verifier/reward.txt").write_text(format(score, ".17g"))
        write_json(self.trial / "result.json", {
            "task_name": "balrog/" + ep["task_id"], "started_at": "2026-11-16T01:01:00",
            "finished_at": "2026-11-16T01:02:00", "exception_info": None,
            "reward_valid": True,
            "agent_info": {"name": "oracle"}, "config": {"job_id": "test-job"},
            "verifier_result": {"rewards": {"reward": score}}})
        count = len(list(self.dataset.glob("*/task.toml")))
        write_json(self.job / "result.json", {
            "id": "test-job", "started_at": "2026-11-16T01:00:00", "finished_at": "2026-11-16T01:03:00",
            "n_total_trials": count, "stats": {"n_completed_trials": count, "n_errored_trials": 0,
            "n_cancelled_trials": 0, "n_running_trials": 0, "n_pending_trials": 0}})

    def mutate(self, path, callback):
        payload = checker.read_json(path)
        callback(payload)
        write_json(path, payload)

    def test_complete_oracle_and_fractional_reference_preserve_classification(self):
        report = checker.check_job(self.dataset, self.job)
        self.assertTrue(report["all_full_oracles"])
        self.assertTrue(report["checks"][0]["native_transitions_checked"])
        self.prepare(suite.load_environment_manifest("crafter")["cases"][0])
        report = checker.check_job(self.dataset, self.job)
        self.assertFalse(report["all_full_oracles"])
        self.assertEqual(report["by_environment"]["crafter"]["full_oracle_count"], 0)

    def test_harbor_reward_cannot_disagree_with_verified_native_score(self):
        self.mutate(self.trial / "result.json", lambda x: x["verifier_result"]["rewards"].update(reward=0))
        with self.assertRaisesRegex(ValueError, "Harbor reward mismatch"):
            checker.check_job(self.dataset, self.job)

    def test_harbor_invalid_reward_flag_is_rejected(self):
        self.mutate(self.trial / "result.json", lambda x: x.update(reward_valid=False))
        with self.assertRaisesRegex(ValueError, "reward is not valid"):
            checker.check_job(self.dataset, self.job)

    def test_missing_and_conflicting_reward_files_fail(self):
        reward = self.trial / "verifier/reward.txt"
        reward.unlink()
        with self.assertRaisesRegex(ValueError, "reward file missing"):
            checker.check_job(self.dataset, self.job)
        reward.write_text("1")
        write_json(self.trial / "verifier/reward.json", {"reward": 0})
        with self.assertRaisesRegex(ValueError, "reward.json mismatch"):
            checker.check_job(self.dataset, self.job)

    def test_completion_count_cannot_be_hidden_by_old_verifier_results(self):
        self.mutate(self.job / "result.json", lambda x: x["stats"].update(n_completed_trials=0))
        with self.assertRaisesRegex(ValueError, "total/completed"):
            checker.check_job(self.dataset, self.job)

    def test_missing_trial_artifact_fails(self):
        (self.trial / "result.json").unlink()
        with self.assertRaisesRegex(ValueError, "Trial artifact count"):
            checker.check_job(self.dataset, self.job)

    def test_stale_trial_and_trial_exception_fail(self):
        path = self.trial / "result.json"
        original = checker.read_json(path)
        for change in ({"started_at": "2026-11-15T01:01:00"}, {"exception_info": {"type": "error"}},
                       {"config": {"job_id": "another-job"}}, {"agent_info": {"name": "nop"}}):
            with self.subTest(change=change):
                write_json(path, {**original, **change})
                with self.assertRaises(ValueError):
                    checker.check_job(self.dataset, self.job)

    def test_explicit_job_timezone_handles_mixed_harbor_timestamps(self):
        self.mutate(self.trial / "result.json", lambda x: x.update(
            started_at="2026-11-16T09:01:00Z", finished_at="2026-11-16T09:02:00Z"))
        report = checker.check_job(self.dataset, self.job, timezone(-timedelta(hours=8)))
        self.assertEqual(report["naive_timestamp_interpretation"]["job_start_utc_offset_seconds"], -28800)
        self.assertEqual(report["naive_timestamp_interpretation"]["source"], "explicit offset")
        with self.assertRaisesRegex(ValueError, "timestamps fall outside"):
            checker.check_job(self.dataset, self.job, timezone.utc)

    def test_short_native_transition_prefix_fails(self):
        self.mutate(self.task / "solution/oracle_actions.json", lambda x: x["expected_transitions"].pop())
        with self.assertRaisesRegex(ValueError, "native transition count"):
            checker.check_job(self.dataset, self.job)

    def test_smoke_without_native_transitions_is_explicit(self):
        self.prepare(suite.load_environment_manifest("nle")["cases"][0])
        self.mutate(self.task / "solution/oracle_actions.json", lambda x: x.pop("expected_transitions", None))
        report = checker.check_job(self.dataset, self.job)
        result = next(c for c in report["checks"] if c["env_name"] == "nle")
        self.assertFalse(result["full_oracle"])
        self.assertFalse(result["native_transitions_checked"])
        self.assertEqual(result["validation_level"], "server_replay_and_native_final_score_only")

    def test_diagnostic_with_score_one_is_not_promoted_to_declared_oracle(self):
        self.mutate(self.task / "solution/reference_status.json", lambda x: x.update(full_oracle_available=False))
        self.mutate(self.task / "solution/oracle_actions.json",
                    lambda x: x.update(kind="native_smoke_diagnostic_not_full_oracle"))
        report = checker.check_job(self.dataset, self.job)
        self.assertTrue(report["checks"][0]["full_reward"])
        self.assertFalse(report["checks"][0]["full_oracle"])
        self.assertFalse(report["all_full_oracles"])

    def test_legacy_six_significant_digits_are_exactly_identified(self):
        case = suite.load_environment_manifest("crafter")["cases"][0]
        self.prepare(case)
        score = case["reference"]["expected_progression"]
        rounded = float(format(score, ".6g"))
        self.mutate(self.trial / "result.json", lambda x: x["verifier_result"]["rewards"].update(reward=rounded))
        (self.trial / "verifier/reward.txt").write_text(str(rounded))
        report = checker.check_job(self.dataset, self.job)
        self.assertTrue(next(c for c in report["checks"] if c["env_name"] == "crafter")["legacy_reward_rounding"])
        (self.trial / "verifier/reward.txt").write_text(str(rounded + 1e-7))
        with self.assertRaisesRegex(ValueError, "reward.txt mismatch"):
            checker.check_job(self.dataset, self.job)


if __name__ == "__main__":
    unittest.main()
