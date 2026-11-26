import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_control_arena_scores import compare


class RecordedScoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        trial = root / "trial"
        (trial / "verifier").mkdir(parents=True)
        reward = {"main_task_success": 0}
        self.trial = {"task_name": "control-arena/example", "finished_at": "done",
                      "exception_info": None, "verifier_result": {"rewards": reward}}
        self.result = trial / "result.json"
        self.result.write_text(json.dumps(self.trial))
        (trial / "verifier/reward.json").write_text(json.dumps(reward))
        with ZipFile(root / "fixture.eval", "w") as archive:
            archive.writestr("header.json", json.dumps({"status": "success", "eval": {"config": {"epochs": 1}}}))
            archive.writestr("reductions.json", json.dumps([{"scorer": "native", "samples": [
                {"sample_id": "0", "value": {"main_task_success": 1}}]}]))
        self.manifest = root / "pairs.json"
        self.pair = {"native_log": "fixture.eval", "native_sample_id": "0", "native_scorer": "native",
                     "harbor_trial": "trial", "harbor_task": self.trial["task_name"]}
        self.manifest.write_text(json.dumps([self.pair]))

    def test_reports_different_scores(self):
        report = compare(self.manifest, "main_task_success")
        self.assertEqual((report["pairs"], report["matching"], report["native_mean"], report["harbor_mean"]),
                         (1, 0, 1, 0))

    def test_rejects_duplicate_or_failed_trials(self):
        self.manifest.write_text(json.dumps([self.pair, self.pair]))
        with self.assertRaisesRegex(ValueError, "twice"):
            compare(self.manifest, "main_task_success")
        self.manifest.write_text(json.dumps([self.pair]))
        self.trial["exception_info"] = {"exception_type": "Failed"}
        self.result.write_text(json.dumps(self.trial))
        with self.assertRaisesRegex(ValueError, "errored"):
            compare(self.manifest, "main_task_success")
