"""Exercise artifact validation using synthetic jobs, without Docker/model calls."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_oracle.py"
SPEC = importlib.util.spec_from_file_location("check_oracle", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


class OracleArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="balrog-oracle-check-")
        self.job = Path(self.temporary.name)
        manifest = checker.read_json(checker.DEFAULT_MANIFEST)
        self.fixtures = checker.select_fixtures(manifest, "full", None)
        self.trial_paths = {}
        write_json(self.job / "result.json", {
            "finished_at": "2026-11-16T00:00:00", "n_total_trials": 50,
            "stats": {"n_completed_trials": 50, "n_errored_trials": 0},
        })
        for task_id, case in self.fixtures.items():
            ep, oracle = case["episode"], case["oracle"]
            trial = self.job / (task_id + "__synthetic")
            verifier = trial / "verifier"
            verifier.mkdir(parents=True)
            self.trial_paths[task_id] = trial
            write_json(trial / "result.json", {
                "task_name": "balrog/" + task_id, "finished_at": "2026-11-16T00:00:00",
                "exception_info": None, "agent_info": {"name": "oracle"},
                "verifier_result": {"rewards": {"reward": 1.0}},
            })
            transitions = []
            for i, native in enumerate(oracle["expected_transitions"]):
                transitions.append({
                    "step": i, "raw_action": oracle["actions"][i],
                    **{("observation_sha256" if key == "observation" else key): value for key, value in native.items()},
                    "budget_exhausted": i + 1 >= ep["expected_max_steps"],
                })
            write_json(verifier / "result.json", {
                "task_id": task_id, "task": ep["task"], "seed": ep["seed"],
                "max_steps": ep["expected_max_steps"],
                "initial_observation_sha256": ep["expected_initial_observation_sha256"],
                "replay_verified": True, "finalized": True,
                "progression": 1.0, "replay_progression": 1.0,
                "terminated": True, "truncated": False,
                "steps": len(transitions), "transitions": transitions,
            })
            (verifier / "reward.txt").write_text("1\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_complete_fifty_task_job_matches_native_fixtures(self):
        result = checker.check_job(self.job, self.fixtures)
        self.assertEqual(len(result), 50)
        self.assertTrue(all(r["native_fixture_matched"] for r in result))

    def test_reward_one_cannot_hide_changed_transition(self):
        path = next(iter(self.trial_paths.values())) / "verifier/result.json"
        payload = checker.read_json(path)
        payload["transitions"][0]["observation_sha256"] = "0" * 64
        write_json(path, payload)
        with self.assertRaisesRegex(ValueError, "native observation mismatch"):
            checker.check_job(self.job, self.fixtures)

    def test_infrastructure_errors_are_rejected(self):
        path = self.job / "result.json"
        payload = checker.read_json(path)
        payload["stats"]["n_errored_trials"] = 1
        write_json(path, payload)
        with self.assertRaisesRegex(ValueError, "infrastructure errors"):
            checker.check_job(self.job, self.fixtures)

    def test_duplicate_trial_cannot_replace_a_missing_task(self):
        paths = list(self.trial_paths.values())
        payload = checker.read_json(paths[1] / "result.json")
        payload["task_name"] = checker.read_json(paths[0] / "result.json")["task_name"]
        write_json(paths[1] / "result.json", payload)
        with self.assertRaises(ValueError):
            checker.check_job(self.job, self.fixtures)

    def test_missing_trial_artifacts_are_rejected(self):
        (next(iter(self.trial_paths.values())) / "result.json").unlink()
        with self.assertRaisesRegex(ValueError, "Trial artifact count"):
            checker.check_job(self.job, self.fixtures)


if __name__ == "__main__":
    unittest.main()
