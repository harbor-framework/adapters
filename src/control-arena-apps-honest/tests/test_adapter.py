import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from control_arena.settings.apps.task.scorers import check_solutions_equal
from control_arena_apps_honest.adapter import COLUMNS, generate, load_records


class TestAdapter(unittest.TestCase):
    def test_allowlist_and_selection(self):
        self.assertEqual(set(COLUMNS), {"problem_id", "question", "solution_passes_tests",
                                        "is_nondeterministic", "inputs", "outputs", "solutions"})
        with self.assertRaises(ValueError):
            load_records(["2"])
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                generate(Path(temp), ["unreviewed"])
            self.assertEqual(generate(Path(temp), limit=0), [])

    def test_export_and_native_comparison(self):
        record = {"problem_id": "0", "question": "An example for the generator",
                  "solution_passes_tests": True, "is_nondeterministic": False,
                  "inputs": [""] * 11, "outputs": ["private-test-value"] * 11,
                  "solutions": [{"code": "print('private-oracle')", "compiles": True,
                                 "passes_tests": True}]}
        with tempfile.TemporaryDirectory() as temp, patch(
            "control_arena_apps_honest.adapter.load_records", return_value=[record]
        ) as fetch:
            root = Path(temp) / "tasks"
            (task,) = generate(root, ["control-arena/apps-honest-0000"])
            self.assertEqual(generate(root, ["apps-honest-0000"]), [task])
            fetch.assert_called_once_with(["0"])
            self.assertEqual(generate(root, [task.name], overwrite=True), [task])
            prompt = (task / "instruction.md").read_text(encoding="utf-8")
            self.assertIn(record["question"], prompt)
            self.assertNotIn("private", prompt)
            self.assertEqual(len(json.loads((task / "tests/cases.json").read_text())["cases"]), 10)
            self.assertEqual(json.loads((task / "solution/submission.json").read_text())["code"],
                             record["solutions"][0]["code"])
            functions = {}
            exec((task / "tests/comparison.py").read_text(encoding="utf-8"), functions)
            for actual, expected in [("1.00001 yes", "1 YES"), ("1.00001 yes", "1 yes"),
                                     ("1\n2", "1 2"), ("1\n2 ", "1 \n2")]:
                self.assertEqual(functions["check_solutions_equal"](actual, expected),
                                 check_solutions_equal(actual, expected))

    def test_unrelated_existing_target_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp, patch("control_arena_apps_honest.adapter.load_records") as fetch:
            out = Path(temp) / "tasks"
            task = out / "apps-honest-0000"
            task.mkdir(parents=True)
            sentry = task / "keep-me"
            sentry.write_text("original")
            for overwrite in (False, True):
                with self.assertRaisesRegex(ValueError, "another task"):
                    generate(out, [task.name], overwrite=overwrite)
            self.assertEqual(sentry.read_text(), "original")
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
