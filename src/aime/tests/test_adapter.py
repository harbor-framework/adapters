import json
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from aime.adapter import AIMEAdapter, AIMETask


class AngleConditionTests(unittest.TestCase):
    def test_generated_task_has_correct_angles_and_original_answer(self):
        record = {
            "id": "I-14",
            "problem": r"Pentagon $ABCDE$ has $\angle ZBA = 60°$.",
            "answer": "60",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "test2025-I.jsonl"
            source.write_text(json.dumps(record) + "\n")
            adapter = AIMEAdapter(root / "tasks", [str(source)])
            self.assertEqual(adapter.run(task_ids=["aime_i-14"]), (1, 0, 1))
            task_dir = root / "tasks/aime_i-14"
            instruction = (task_dir / "instruction.md").read_text()
            self.assertIn(r"$\angle B = \angle E = 60°$", instruction)
            self.assertNotIn("ZBA", instruction)
            self.assertIn("60", (task_dir / "solution/solve.sh").read_text())
            verifier = runpy.run_path(str(task_dir / "tests/test_outputs.py"))
            self.assertEqual(verifier["EXPECTED_ANSWER"], "60")
            with patch("os.path.exists", return_value=True), patch(
                "builtins.open", mock_open(read_data="60\n")
            ):
                self.assertTrue(verifier["test_answer"]())

    def test_other_problems_are_unchanged(self):
        problem = r"An unrelated problem with $\angle ZBA = 60°$."
        task = AIMETask({"id": "II-14", "problem": problem, "answer": "1"})
        self.assertEqual(task.problem, problem)

    def test_already_corrected_problem_is_unchanged(self):
        problem = r"Pentagon $ABCDE$ has $\angle B = \angle E = 60°$."
        task = AIMETask({"id": "I-14", "problem": problem, "answer": "60"})
        self.assertEqual(task.problem, problem)


if __name__ == "__main__":
    unittest.main()
