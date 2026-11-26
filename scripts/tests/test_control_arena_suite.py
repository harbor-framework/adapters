import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_control_arena as suite


class ControlArenaSuiteTests(unittest.TestCase):
    def test_registered_packages_have_locked_entry_points(self):
        import tomllib

        for package in set(suite.ADAPTERS.values()):
            project = suite.PACKAGES / package
            config = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
            self.assertIn(package, config["project"]["scripts"])
            self.assertTrue((project / "uv.lock").is_file())

    @patch("generate_control_arena.subprocess.run")
    @patch("generate_control_arena.shutil.which", return_value="/test/uv")
    def test_setting_output_and_filters(self, which, run):
        run.return_value.returncode = 0
        status = suite.main(["--settings", "bash", "bash", "--task-ids", "bash-604648",
                             "--limit", "1", "--overwrite"])
        self.assertEqual(status, 0)
        run.assert_called_once_with(
            ["/test/uv", "run", "--locked", "control-arena-bash-honest", "--output-dir",
             str(Path("datasets/control-arena/bash").resolve()), "--limit", "1",
             "--task-ids", "bash-604648", "--overwrite"],
            cwd=suite.PACKAGES / "control-arena-bash-honest")

    @patch("generate_control_arena.subprocess.run")
    def test_unavailable_setting_cannot_start_work(self, run):
        import contextlib
        import io

        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            suite.main(["--settings", "bash", "not_a_setting"])
        run.assert_not_called()
