import tempfile
import unittest
from pathlib import Path

from control_arena_swe_django_honest.adapter import COLUMNS, TASK_ID, generate, prepare_swebench_imports


class TestAdapter(unittest.TestCase):
    def test_selection_is_limited_to_reviewed_main_issue(self):
        self.assertFalse(any("side" in name for name in COLUMNS))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "tasks"
            self.assertEqual(generate(output, limit=0), [])
            with self.assertRaises(ValueError):
                generate(output, ["unreviewed"])
            (output / TASK_ID).mkdir(parents=True)
            self.assertEqual(generate(output, ["control-arena/" + TASK_ID]), [output / TASK_ID])

    def test_native_django_parser_import(self):
        prepare_swebench_imports()
        from swebench.harness.log_parsers.python import parse_log_django
        self.assertEqual(parse_log_django("ordinary_test ... ok\n", None), {"ordinary_test": "PASSED"})


if __name__ == "__main__":
    unittest.main()
