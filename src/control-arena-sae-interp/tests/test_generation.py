import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from control_arena import EvalMode
from control_arena.settings.sae_interp_sabotage.setting import SAEInterpSetting
from harbor.models.task.task import Task

from control_arena_sae_interp.adapter import ControlArenaSAEInterpAdapter


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)

    def test_all_tasks_match_native_inputs_in_both_modes(self):
        paths = ControlArenaSAEInterpAdapter(self.output).run()
        self.assertEqual(len(paths), 22)
        setting = SAEInterpSetting()
        for mode in (EvalMode.HONEST, EvalMode.ATTACK):
            samples = list(setting.get_dataset(mode))
            self.assertEqual(len(paths), len(samples))
            for path, sample in zip(paths, samples, strict=True):
                task = Task(path)
                digest = hashlib.sha256(sample.input.encode()).hexdigest()
                self.assertEqual(task.config.task.name, "control-arena/sae-interp-" + digest[:12])
                self.assertEqual(
                    task.instruction,
                    sample.metadata["setting_description"].rstrip() + "\n\n" + sample.input + "\n",
                )
                case = json.loads((path / "tests/case.json").read_text())
                self.assertEqual(case["prompt_sha256"], digest)
                self.assertEqual(samples[case["source_index"]].input, sample.input)
                oracle = json.loads((path / "solution/submission.json").read_text(encoding="utf-8"))
                self.assertEqual(oracle["interpretation"], sample.metadata["main_task_name"])
                self.assertEqual([file.name for file in (path / "environment").iterdir()], ["Dockerfile"])
                self.assertNotIn(b"\r", (path / "tests/test.sh").read_bytes())

    def test_selection_overwrite_and_existing_directories(self):
        first, second = ControlArenaSAEInterpAdapter(self.output, limit=2).run()
        original = (second / "instruction.md").read_bytes()
        (second / "instruction.md").write_text("retained on skip")
        names = ["control-arena/" + second.name]
        self.assertEqual(ControlArenaSAEInterpAdapter(self.output, task_ids=names).run(), [second])
        self.assertEqual((second / "instruction.md").read_text(), "retained on skip")
        ControlArenaSAEInterpAdapter(self.output, task_ids=names, overwrite=True).run()
        self.assertEqual((second / "instruction.md").read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "Unknown task IDs"):
            ControlArenaSAEInterpAdapter(self.output, task_ids=["unknown"]).run()
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            ControlArenaSAEInterpAdapter(self.output, limit=-1).run()
        (first / "tests/case.json").unlink()
        with self.assertRaisesRegex(ValueError, "not a generated SAE task"):
            ControlArenaSAEInterpAdapter(self.output, task_ids=[first.name], overwrite=True).run()


if __name__ == "__main__":
    unittest.main()
