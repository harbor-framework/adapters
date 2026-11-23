"""Historical source drift never relaxes saved evidence integrity checks."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "_balrog_validation_history", PROJECT / "scripts/build_validation_bundle.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ValidationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="balrog-history-test-")
        self.output = Path(self.temporary.name) / "validation"
        shutil.copytree(PROJECT / "validation", self.output)
        self.original_baseline_hash = builder.sha(PROJECT / "validation/baseline.json")
        self.output_patch = patch.object(builder, "OUTPUT", self.output)
        self.output_patch.start()

    def tearDown(self):
        self.output_patch.stop()
        self.assertEqual(builder.sha(PROJECT / "validation/baseline.json"), self.original_baseline_hash)
        self.temporary.cleanup()

    def test_default_check_rejects_current_source_drift(self):
        with self.assertRaisesRegex(ValueError, "Current review files differ from bundle snapshot"):
            builder.check()

    def test_historical_check_passes_and_identifies_source_drift(self):
        captured = io.StringIO()
        with redirect_stdout(captured):
            builder.check(historical=True)
        result = json.loads(captured.getvalue())
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["historical_mode"])
        self.assertFalse(result["review_snapshot_matches_current"])
        self.assertEqual(result["kind"], "saved_summary_integrity_not_gameplay_reproduction")
        self.assertEqual(result["cases"], 255)
        self.assertTrue(result["review_snapshot_differences"])
        for difference in result["review_snapshot_differences"]:
            self.assertNotEqual(difference["historical_sha256"], difference["current_sha256"])
            current = PROJECT / difference["file"]
            self.assertEqual(difference["current_sha256"], builder.sha(current) if current.is_file() else None)

    def test_historical_mode_rejects_corrupted_bundle_checksum(self):
        target = self.output / "baseline.json"
        target.write_bytes(target.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Bundle checksum mismatch: baseline.json"):
            builder.check(historical=True)

    def test_historical_mode_still_checks_scores_after_checksum_matches(self):
        target = self.output / "baseline.json"
        baseline = builder.read(target)
        baseline["full_oracles"] = 255
        target.write_text(json.dumps(baseline), encoding="utf-8")
        checksums = builder.read(self.output / "checksums.json")
        checksums["sha256"]["baseline.json"] = builder.sha(target)
        (self.output / "checksums.json").write_text(json.dumps(checksums), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Full/diagnostic counts changed"):
            builder.check(historical=True)


if __name__ == "__main__":
    unittest.main()
