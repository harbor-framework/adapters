import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from processbench.aggregate_metrics import VALID_OUTCOME_EXCEPTIONS, load_trials


class AggregateMetricsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.job = Path(self.temporary.name) / "job"
        self.job.mkdir()

    def write_trial(self, task_id="gsm8k-0", match=False, exception=None):
        trial = self.job / f"processbench-{task_id}__test"
        (trial / "verifier").mkdir(parents=True, exist_ok=True)
        result = {
            "task_name": f"qwen/processbench__{task_id}",
            "finished_at": "2026-11-12T00:00:00Z",
            "verifier": {"finished_at": "2026-11-12T00:00:00Z"},
            "verifier_result": {"rewards": {"reward": int(match)}},
            "exception_info": (
                {"exception_type": exception} if exception is not None else None
            ),
        }
        row = {
            "id": task_id, "subset": "gsm8k", "label": 1,
            "prediction": 1 if match else None, "match": match,
        }
        (trial / "result.json").write_text(json.dumps(result))
        (trial / "verifier/metrics.json").write_text(json.dumps(row))
        return trial, result

    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        return subprocess.run(
            [sys.executable, "-m", "processbench.aggregate_metrics", str(self.job), *args],
            capture_output=True, text=True, env=env,
        )

    def test_infrastructure_errors_with_zero_metrics_block_f1(self):
        errors = (
            "ApiInternalServerError", "ApiRateLimitError", "ApiUsageLimitError",
            "ApiOverloadedError", "ApiConnectionClosedError", "ApiResponseStalledError",
            "AgentAuthenticationError", "NetworkConnectionError", "ModelNotFoundError",
            "ApiProviderResourceNotFoundError", "UnknownApiError",
            "NonZeroAgentExitCodeError", "VerifierTimeoutError", "NewUnknownError",
        )
        for error in errors:
            with self.subTest(error=error):
                self.write_trial(exception=error)
                output = self.job / "summary.json"
                run = self.run_cli("--output", str(output))
                self.assertNotEqual(run.returncode, 0)
                self.assertIn(error, run.stderr)
                self.assertIn("gsm8k-0", run.stderr)
                self.assertEqual(run.stdout, "")
                self.assertFalse(output.exists())

    def test_valid_zero_and_one_scores_are_retained(self):
        self.write_trial(match=False)
        self.write_trial(task_id="gsm8k-1", match=True)
        rows = load_trials(self.job)
        self.assertEqual([r["match"] for r in rows], [False, True])
        run = self.run_cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("over 2 tasks", run.stdout)

    def test_valid_outcome_exceptions_preserve_both_scores(self):
        for exception in VALID_OUTCOME_EXCEPTIONS:
            for match in (False, True):
                with self.subTest(exception=exception, match=match):
                    self.write_trial(match=match, exception=exception)
                    self.assertEqual(load_trials(self.job)[0]["match"], match)

    def test_unfinished_or_unscored_trial_blocks_aggregation(self):
        changes = (
            {"finished_at": None}, {"verifier": None},
            {"verifier": {"finished_at": None}}, {"verifier_result": None},
            {"verifier_result": {"rewards": {"reward": True}}},
            {"verifier_result": {"rewards": {"reward": 0.5}}},
            {"exception_info": {}},
        )
        for change in changes:
            with self.subTest(change=change):
                trial, result = self.write_trial()
                result.update(change)
                (trial / "result.json").write_text(json.dumps(result))
                with self.assertRaises(ValueError):
                    load_trials(self.job)

    def test_reward_and_task_id_must_match_metrics(self):
        for change in (
            {"task_name": "qwen/processbench__gsm8k-1"},
            {"verifier_result": {"rewards": {"reward": 1}}},
        ):
            with self.subTest(change=change):
                trial, result = self.write_trial()
                result.update(change)
                (trial / "result.json").write_text(json.dumps(result))
                with self.assertRaises(ValueError):
                    load_trials(self.job)

    def test_missing_or_malformed_result_blocks_metrics(self):
        trial, _ = self.write_trial()
        (trial / "result.json").unlink()
        with self.assertRaisesRegex(ValueError, "result.json"):
            load_trials(self.job)
        for payload in ("{", "[]"):
            with self.subTest(payload=payload):
                (trial / "result.json").write_text(payload)
                with self.assertRaises(ValueError):
                    load_trials(self.job)

    def test_trial_without_metrics_is_not_silently_skipped(self):
        trial, _ = self.write_trial()
        (trial / "verifier/metrics.json").unlink()
        with self.assertRaisesRegex(ValueError, "gsm8k-0"):
            load_trials(self.job)

    def test_all_affected_trials_are_reported(self):
        self.write_trial(exception="AgentAuthenticationError")
        self.write_trial(task_id="gsm8k-1", exception="NetworkConnectionError")
        run = self.run_cli()
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("2 invalid or unfinished trials", run.stderr)
        self.assertIn("gsm8k-0", run.stderr)
        self.assertIn("gsm8k-1", run.stderr)

    def test_dataset_completeness_still_blocks_missing_tasks(self):
        self.write_trial()
        dataset = Path(self.temporary.name) / "dataset"
        tests = dataset / "processbench-gsm8k-1/tests"
        tests.mkdir(parents=True)
        (tests / "ground_truth.json").write_text(json.dumps({"id": "gsm8k-1"}))
        run = self.run_cli("--dataset-dir", str(dataset))
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("gsm8k-1", run.stderr)
        self.assertEqual(run.stdout, "")


if __name__ == "__main__":
    unittest.main()
