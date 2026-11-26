import json
import tempfile
import tomllib
import unittest
from importlib.metadata import distribution
from pathlib import Path

from control_arena_rogue_eval_honest.adapter import ControlArenaRogueEvalHonestAdapter, TASK


class AdditionTest(unittest.TestCase):
    def test_projection_and_separate_fixture(self):
        source = Path(distribution("control-arena").locate_file("control_arena/settings/rogue_eval"))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            live, = ControlArenaRogueEvalHonestAdapter(output).run()
            fixture, = ControlArenaRogueEvalHonestAdapter(output, fixture=True).run()
            self.assertEqual((live / "solution/reference.py").read_bytes(),
                             (source / "main_tasks/addition/solution.py").read_bytes())
            self.assertNotEqual((fixture / "solution/reference.py").read_bytes(),
                                (live / "solution/reference.py").read_bytes())
            self.assertIn(TASK, (live / "instruction.md").read_text(encoding="utf-8"))
            self.assertFalse((live / "tests/fixture_data.py").exists())
            for case in (live, fixture):
                config = tomllib.loads((case / "task.toml").read_text())
                self.assertEqual(config["environment"]["network_mode"], "no-network")
                self.assertEqual(config["verifier"]["network_mode"], "no-network")
                self.assertEqual(config["verifier"]["environment_mode"], "separate")
                self.assertEqual(config["artifacts"], [{"source": "/workspace/solution.py"}])
                self.assertEqual(json.loads((case / "tests/case.json").read_text())["source_id"], "addition-honest")
                self.assertEqual({p.name for p in (case / "environment").iterdir()}, {"monitoring.py", "Dockerfile"})
                self.assertEqual((case / "environment/monitoring.py").read_bytes(),
                                 (source / "sandbox_env/monitoring.py").read_bytes())

    def test_selection_and_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with self.assertRaisesRegex(ValueError, "Only the reviewed"):
                ControlArenaRogueEvalHonestAdapter(out, task_ids=["unknown"]).run()
            self.assertEqual([], ControlArenaRogueEvalHonestAdapter(out, limit=0).run())
            adapter = ControlArenaRogueEvalHonestAdapter(out, task_ids=["addition-honest"])
            self.assertEqual(adapter.run(), adapter.run())
