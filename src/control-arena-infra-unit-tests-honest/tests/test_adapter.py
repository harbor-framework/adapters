import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from control_arena_infra_unit_tests_honest.adapter import SLUG, TEST_BLOB, generate, native_material, verify_blob


class InfraGeneratorTests(unittest.TestCase):
    def test_released_material(self):
        prompt, source, reference = native_material()
        self.assertIn("/workspace/training-infra/training/tests/test_train.py", prompt)
        self.assertEqual(verify_blob(reference, TEST_BLOB), reference)
        compile(source, "native_score.py", "exec")

    def test_offline_generation_and_safe_retries(self):
        with tempfile.TemporaryDirectory() as temp, patch(
            "control_arena_infra_unit_tests_honest.adapter.read_training", return_value=b"# offline test input\n"
        ) as download:
            root = Path(temp)
            generated, = generate(root, task_ids=["control-arena/" + SLUG])
            self.assertEqual((generated / "tests/train.py").read_bytes(),
                             (generated / "environment/training/train.py").read_bytes())
            self.assertEqual(generate(root), [generated])
            self.assertEqual(download.call_count, 1)
            self.assertEqual(generate(root, overwrite=True), [generated])
            self.assertEqual(download.call_count, 2)
            notes = generated / "notes.txt"
            notes.write_text("keep")
            for overwrite in (False, True):
                with self.assertRaises(ValueError):
                    generate(root, overwrite=overwrite)
            self.assertEqual(notes.read_text(), "keep")
            notes.unlink()
            (generated / "tests/case.json").write_text(json.dumps({"objective": "a different task"}))
            with self.assertRaises(ValueError):
                generate(root, overwrite=True)
            self.assertEqual(download.call_count, 2)

    def test_source_checks_and_empty_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(generate(root, limit=0), [])
            self.assertEqual(generate(root, task_ids=[]), [])
            with self.assertRaises(ValueError):
                generate(root, task_ids=["unknown"])
            (root / "train.py").write_bytes(b"wrong source")
            with self.assertRaisesRegex(ValueError, "Git blob"):
                generate(root, source_dir=root)
            self.assertFalse((root / SLUG).exists())


if __name__ == "__main__":
    unittest.main()
