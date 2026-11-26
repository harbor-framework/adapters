import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from control_arena_swe_django_honest.adapter import COLUMNS, TASK_ID, TEMPLATE, generate, prepare_swebench_imports


class TestAdapter(unittest.TestCase):
    def test_selection_is_limited_to_reviewed_main_issue(self):
        self.assertFalse(any("side" in name for name in COLUMNS))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "tasks"
            self.assertEqual(generate(output, limit=0), [])
            with self.assertRaises(ValueError):
                generate(output, ["unreviewed"])
            target = output / TASK_ID
            target.mkdir(parents=True)
            for overwrite in (False, True):
                with self.assertRaisesRegex(ValueError, "another task"):
                    generate(output, overwrite=overwrite)
            shutil.copyfile(TEMPLATE / "task.toml", target / "task.toml")
            self.assertEqual(generate(output, ["control-arena/" + TASK_ID]), [target])
            with patch("control_arena_swe_django_honest.adapter.load_issue", return_value={}), patch(
                "control_arena_swe_django_honest.adapter.write_task", side_effect=lambda path, _: shutil.copytree(TEMPLATE, path)
            ):
                self.assertEqual(generate(output, overwrite=True), [target])
            real = target.rename(output / "original")
            try:
                target.symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Cannot create directory symlinks: {exc}")
            for overwrite in (False, True):
                with self.assertRaisesRegex(ValueError, "another task"):
                    generate(output, overwrite=overwrite)
            self.assertTrue((real / "task.toml").is_file())

    def test_native_django_parser_import(self):
        prepare_swebench_imports()
        from swebench.harness.log_parsers.python import parse_log_django
        self.assertEqual(parse_log_django("ordinary_test ... ok\n", None), {"ordinary_test": "PASSED"})


if __name__ == "__main__":
    unittest.main()
