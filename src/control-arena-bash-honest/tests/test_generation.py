import json
import tempfile
import unittest
from importlib.metadata import distribution
from pathlib import Path

from control_arena_bash_honest.adapter import CASE_IDS, generate
from harbor.models.task.task import Task


class BashGenerationTests(unittest.TestCase):
    def test_exports_native_prompts_and_public_tests(self):
        source = distribution("control-arena").locate_file("control_arena/settings/bash/bash_tasks.json")
        rows = {row["task_id"]: row for row in json.loads(Path(source).read_text(encoding="utf-8"))}
        with tempfile.TemporaryDirectory() as tmp:
            tasks = generate(Path(tmp))
            self.assertEqual([p.name for p in tasks], [f"bash-{i}" for i in CASE_IDS])
            for task in tasks:
                source_id = json.loads((task / "tests/case.json").read_text())["source_id"]
                row = rows[source_id]
                self.assertIn(row["task_description"], (task / "instruction.md").read_text(encoding="utf-8"))
                for directory in ("tests", "environment"):
                    self.assertEqual((task / directory / "test_task.py").read_text(encoding="utf-8"),
                                     row["task_verifiable"])
                self.assertEqual(Task(task).config.task.name, f"control-arena/{task.name}")
                self.assertFalse((task / "solution").exists())

    def test_private_oracle_and_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "tasks"
            scripts = Path(tmp) / "private"
            scripts.mkdir()
            (scripts / "604648.sh").write_text("#!/bin/sh\nexit 1\n")
            selected = ["control-arena/bash-604648"]
            task, = generate(output, task_ids=selected)
            with self.assertRaisesRegex(ValueError, "overwrite"):
                generate(output, task_ids=selected, oracle_dir=scripts)
            generate(output, task_ids=selected, oracle_dir=scripts, overwrite=True)
            self.assertEqual((task / "solution/solution.sh").read_text(), "#!/bin/sh\nexit 1\n")
            with self.assertRaisesRegex(ValueError, "Unknown task"):
                generate(output, task_ids=["other"])
            self.assertEqual(generate(output, limit=0), [])


if __name__ == "__main__":
    unittest.main()
