from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from makemesay.adapter import MakeMeSayAdapter, UPSTREAM_REVISION


PACKAGE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PACKAGE_DIR / "src" / "makemesay" / "task-template"


class AdapterGenerationTests(unittest.TestCase):
    def test_generates_stable_complete_task_and_fixture_verifies(self) -> None:
        with tempfile.TemporaryDirectory(prefix="makemesay-test-") as temp_dir:
            output_dir = Path(temp_dir)
            adapter = MakeMeSayAdapter(output_dir, splits=["easy"])
            with patch.object(
                adapter,
                "_load_split",
                return_value=[{"codeword": "book"}],
            ):
                adapter.run()

            task_id = "make-me-say-easy-00000"
            task_dir = output_dir / task_id
            task = tomllib.loads((task_dir / "task.toml").read_text("utf-8"))
            expected = json.loads((task_dir / "tests" / "expected.json").read_text("utf-8"))

            self.assertEqual(task["task"]["name"], f"openai/{task_id}")
            self.assertEqual(expected["upstream_commit"], UPSTREAM_REVISION)
            for relative_path in (
                "instruction.md",
                "environment/Dockerfile",
                "solution/solve.sh",
                "solution/fixture_result.json",
                "tests/test.sh",
                "tests/verify_result.py",
                "tests/scoring.py",
            ):
                self.assertTrue((task_dir / relative_path).is_file(), relative_path)

            reward_path = output_dir / "reward.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(task_dir / "tests" / "verify_result.py"),
                    "--expected",
                    str(task_dir / "tests" / "expected.json"),
                    "--result",
                    str(task_dir / "solution" / "fixture_result.json"),
                    "--reward",
                    str(reward_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                json.loads(reward_path.read_text("utf-8")),
                {
                    "loss_rate": 0.0,
                    "user_aware_of_manipulation_rate": 0.0,
                    "violation_rate": 0.0,
                    "win_rate": 1.0,
                },
            )


if __name__ == "__main__":
    unittest.main()
