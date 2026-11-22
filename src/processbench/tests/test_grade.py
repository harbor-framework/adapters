"""Tests for the verifier's ground-truth lookup (tests/grade.py in the task template)."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

GRADE = Path(__file__).parents[1] / "src/processbench/task-template/tests/grade.py"
sys.dont_write_bytecode = True  # never write .pyc into the task template
spec = importlib.util.spec_from_file_location("grade", GRADE)
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)


class LoadGroundTruthTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.tests = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, name, payload):
        (self.tests / name).write_text(json.dumps(payload) + "\n")

    def test_loads_the_single_file(self):
        self.write("ground_truth.gsm8k-69.json", {"id": "gsm8k-69", "label": 1})
        self.assertEqual(grade.load_ground_truth(self.tests)["label"], 1)

    def test_missing_file_fails(self):
        with self.assertRaises(SystemExit):
            grade.load_ground_truth(self.tests)

    def test_two_files_fail_instead_of_guessing(self):
        self.write("ground_truth.gsm8k-69.json", {"id": "gsm8k-69", "label": 1})
        self.write("ground_truth.gsm8k-39.json", {"id": "gsm8k-39", "label": 2})
        with self.assertRaises(SystemExit):
            grade.load_ground_truth(self.tests)

    def test_old_shared_name_is_not_accepted(self):
        self.write("ground_truth.json", {"id": "gsm8k-69", "label": 1})
        with self.assertRaises(SystemExit):
            grade.load_ground_truth(self.tests)

    def test_id_must_match_file_name(self):
        self.write("ground_truth.gsm8k-69.json", {"id": "gsm8k-39", "label": 2})
        with self.assertRaises(SystemExit):
            grade.load_ground_truth(self.tests)


if __name__ == "__main__":
    unittest.main()
