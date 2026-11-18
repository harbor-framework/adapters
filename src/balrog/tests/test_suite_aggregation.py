"""Guard against weighting the large Baba task set more than the other games."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_suite_parity import COUNTS, aggregate
from analyze_parity import canonical_hash, summary, ValidationError


def fixtures():
    result = []
    for name in COUNTS:
        path = Path(__file__).resolve().parents[1] / "src/balrog/fixtures" / ("manifest.json" if name == "babyai" else name + "_manifest.json")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        task_ids = manifest["splits"]["full"]
        sdk = {"openai": "1.0", "anthropic": "2.0", "google-genai": "3.0", "omegaconf": "4.0", "tqdm": "5.0"}
        result.append({"kind": name + "_parity_analysis", "analysis_only": True,
             "manifest": {"env_name": name, "task_ids": task_ids, "split": "full",
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "task_ids_sha256": canonical_hash(task_ids)},
             "provenance": {"settings": {"agent": {"type": "naive"}, "client": {"model_id": "synthetic"}},
                            "source_commits": manifest["source_commits"], "runner_sha256": "a" * 64,
                            "runtime_versions_by_side": {side: {"python": "3.10.0", "packages": dict(sdk)}
                                                         for side in ("native", "harbor")}},
             "number_of_runs_per_side": 3,
             "native": summary([1, 1, 1] if name == "babaisai" else [0, 0, 0]),
             "harbor": summary([1, 1, 1] if name == "babaisai" else [0, 0, 0])})
    return result


class SuiteAggregationTest(unittest.TestCase):
    def test_large_environment_does_not_dominate_overall_score(self):
        result = aggregate(fixtures())
        self.assertAlmostEqual(result["native"]["mean"], 1/6)
        self.assertNotAlmostEqual(result["native"]["mean"], 120/255)

    def test_missing_environment_or_model_drift_is_rejected(self):
        with self.assertRaises(ValidationError):
            aggregate(fixtures()[:-1])
        values = fixtures()
        values[-1]["provenance"]["settings"]["client"]["model_id"] = "different"
        with self.assertRaises(ValidationError):
            aggregate(values)

    def test_edited_summary_cannot_override_raw_measurements(self):
        values = fixtures()
        values[0]["native"]["mean"] = 1
        with self.assertRaises(ValidationError):
            aggregate(values)

    def test_same_sized_replacement_or_duplicate_scope_is_rejected(self):
        for change in ("duplicate", "replacement", "reorder"):
            with self.subTest(change=change):
                values = fixtures()
                manifest = values[0]["manifest"]
                ids = manifest["task_ids"]
                if change == "duplicate":
                    ids[-1] = ids[0]
                elif change == "replacement":
                    ids[-1] = "babyai-goto-seed-999"
                else:
                    ids.reverse()
                # Even an internally consistent task-list checksum cannot turn
                # a different selection into this project's fixed full suite.
                manifest["task_ids_sha256"] = canonical_hash(ids)
                with self.assertRaises(ValidationError):
                    aggregate(values)

    def test_stale_manifest_or_changed_environment_source_is_rejected(self):
        values = fixtures()
        values[2]["manifest"]["sha256"] = "b" * 64
        with self.assertRaises(ValidationError):
            aggregate(values)
        values = fixtures()
        values[1]["provenance"]["source_commits"]["baba"] = "b" * 40
        with self.assertRaises(ValidationError):
            aggregate(values)

    def test_different_runner_or_model_sdk_across_environments_is_rejected(self):
        values = fixtures()
        values[-1]["provenance"]["runner_sha256"] = "b" * 64
        with self.assertRaises(ValidationError):
            aggregate(values)
        values = fixtures()
        for side in ("native", "harbor"):
            values[-1]["provenance"]["runtime_versions_by_side"][side]["packages"]["openai"] = "different"
        with self.assertRaises(ValidationError):
            aggregate(values)

    def test_missing_sdk_or_within_environment_drift_is_rejected(self):
        for change in ("missing", "different"):
            values = fixtures()
            packages = values[0]["provenance"]["runtime_versions_by_side"]["harbor"]["packages"]
            if change == "missing":
                del packages["openai"]
            else:
                packages["openai"] = "different"
            with self.subTest(change=change), self.assertRaises(ValidationError):
                aggregate(values)

    def test_game_dependencies_and_python_may_differ_across_environments(self):
        values = fixtures()
        for index, analysis in enumerate(values):
            for side in ("native", "harbor"):
                runtime = analysis["provenance"]["runtime_versions_by_side"][side]
                runtime["packages"]["game-package"] = str(index)
                runtime["python"] = "3.10." + str(index)
        result = aggregate(values)
        self.assertEqual(result["runner_sha256"], "a" * 64)
        self.assertNotIn("game-package", result["model_sdk_versions"])
        self.assertEqual(set(result["environment_manifest_sha256"]), set(COUNTS))


if __name__ == "__main__":
    unittest.main()
