import json
import os
import tempfile
import unittest
from pathlib import Path

from control_arena_bigcodebench_honest.adapter import ControlArenaBigCodeBenchHonestAdapter, IDS, load_rows


class GenerationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get("BIGCODEBENCH_PARQUET")
        cls.source = Path(path) if path else None

    def test_all_rows_and_private_assets(self):
        rows = load_rows(self.source)
        with tempfile.TemporaryDirectory() as tmp:
            adapter = ControlArenaBigCodeBenchHonestAdapter(Path(tmp), source_parquet=self.source)
            paths = adapter.run()
            self.assertEqual(3, len(paths))
            self.assertEqual(paths, adapter.run())
            for path, row in zip(paths, rows, strict=True):
                prompt = (path / "instruction.md").read_text(encoding="utf-8")
                self.assertIn(row["complete_prompt"], prompt)
                self.assertNotIn(row["canonical_solution"], prompt)
                self.assertNotIn(row["test"], prompt)
                self.assertEqual(["Dockerfile"], sorted(p.name for p in (path / "environment").iterdir()))
                case = json.loads((path / "tests/sample.json").read_text(encoding="utf-8"))
                self.assertEqual("honest", case["metadata"]["eval_mode"])
                self.assertEqual("", case["metadata"]["metadata"]["canonical_solution"])
                self.assertEqual(case["metadata"]["metadata"]["test_code"], row["test"])
                self.assertEqual(row["canonical_solution"], (path / "solution/solution.py").read_text())

    def test_selection_and_source_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            convert = ControlArenaBigCodeBenchHonestAdapter(dest, task_ids=[IDS[-1]], source_parquet=self.source)
            self.assertEqual("bigcodebench-honest-2", convert.run()[0].name)
            with self.assertRaisesRegex(ValueError, "Unknown"):
                ControlArenaBigCodeBenchHonestAdapter(dest, task_ids=["BigCodeBench/3"]).run()
            bad = dest / "wrong.parquet"
            bad.write_bytes(b"invalid")
            with self.assertRaisesRegex(ValueError, "pinned"):
                load_rows(bad)


if __name__ == "__main__":
    unittest.main()
