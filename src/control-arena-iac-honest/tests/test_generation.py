import json
import tempfile
import unittest
from importlib.metadata import distribution
from pathlib import Path

from control_arena_iac_honest.adapter import ControlArenaIaCHonestAdapter, OBJECTIVES


class GenerationTest(unittest.TestCase):
    def test_native_inputs_and_private_tests_in_both_variants(self):
        sources = Path(distribution("control-arena").locate_file("control_arena/settings"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for setting, baseline in (("iac", sources / "iac/setting"),
                                      ("iac_fast", sources / "iac_fast/docker/setting")):
                adapter = ControlArenaIaCHonestAdapter(root, setting=setting)
                cases = adapter.run()
                self.assertEqual(len(OBJECTIVES), len(cases))
                self.assertEqual(cases, adapter.run())
                for name, case in zip(OBJECTIVES, cases, strict=True):
                    self.assertEqual(json.loads((case / "tests/source.json").read_text())["objective"], name)
                    actual = case / "environment/repo"
                    self.assertFalse((actual / "tests").exists())
                    self.assertFalse(any(actual.rglob("*.patch")))
                    expected_modules = sorted(p.relative_to(baseline) for p in baseline.rglob("core_infrastructure/**/*.py"))
                    self.assertGreater(len(expected_modules), 0)
                    self.assertEqual(sorted(p.relative_to(actual) for p in actual.rglob("*.py")), expected_modules)
                    for module in expected_modules:
                        self.assertEqual((baseline / module).read_bytes(), (actual / module).read_bytes())
                    test = f"test_{name}.py"
                    self.assertEqual([test], sorted(p.name for p in (case / "tests").glob("test_*.py")))
                    self.assertEqual((baseline / "tests" / test).read_bytes(), (case / "tests" / test).read_bytes())
                    self.assertEqual((sources / "iac/tasks/QA" / name / "solution.patch").read_bytes(),
                                     (case / "solution/reference.patch").read_bytes())
            self.assertEqual(10, len(list(root.iterdir())))

    def test_skip_unselected_and_reject_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            adapter = ControlArenaIaCHonestAdapter(out, setting="iac_fast", task_ids=["create_billing_alarm"])
            self.assertEqual("iac-fast-honest-create-billing-alarm", adapter.run()[0].name)
            with self.assertRaisesRegex(ValueError, "Unknown"):
                ControlArenaIaCHonestAdapter(out, task_ids=["unknown"]).run()


if __name__ == "__main__":
    unittest.main()
