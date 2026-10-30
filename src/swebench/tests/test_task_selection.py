"""Run with: uv run --project src/swebench python -m unittest discover -s src/swebench/tests."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swebench_adapter.adapter import SWEBenchAdapter
from swebench_adapter.main import main


FAILING_IDS = [
    "astropy__astropy-7606",
    "astropy__astropy-8707",
    "astropy__astropy-8872",
    "django__django-10097",
]
FIXED_IDS = [
    "astropy__astropy-13398",
    "sphinx-doc__sphinx-8595",
    "sphinx-doc__sphinx-9711",
]
ALL_IDS = sorted(FAILING_IDS + FIXED_IDS + [f"example-{i:03}" for i in range(493)])


class TaskSelectionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output_dir = Path(temp.name)
        loader = self.enterContext(
            patch("swebench_adapter.adapter.SWEBenchLoader")
        )
        loader.return_value.all_ids.return_value = ALL_IDS
        self.enterContext(patch.object(SWEBenchAdapter, "_build_image_map", return_value={}))
        self.generate_many = self.enterContext(
            patch.object(SWEBenchAdapter, "generate_many", return_value=([], []))
        )
        self.output = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def selected_ids(self, **kwargs):
        SWEBenchAdapter(output_dir=self.output_dir, **kwargs).run()
        return self.generate_many.call_args.args[0]

    def test_bulk_default_excludes_only_known_failures(self):
        selected = self.selected_ids()
        self.assertEqual(len(selected), 496)
        self.assertEqual(selected, [iid for iid in ALL_IDS if iid not in FAILING_IDS])
        self.assertTrue(set(FIXED_IDS).issubset(selected))
        self.assertIn("Excluding 4 known-failing tasks", self.output.getvalue())
        for iid in FAILING_IDS:
            self.assertIn(iid, self.output.getvalue())

    def test_override_preserves_full_set(self):
        self.assertEqual(self.selected_ids(include_known_failing=True), ALL_IDS)
        self.assertNotIn("Excluding", self.output.getvalue())

    def test_filter_precedes_limit(self):
        selected = self.selected_ids(limit=2)
        self.assertEqual(selected, ["astropy__astropy-13398", "example-000"])

    def test_explicit_task_ids_preserve_known_failures_and_order(self):
        selected = self.selected_ids(task_ids=list(reversed(FAILING_IDS)), limit=2)
        self.assertEqual(selected, list(reversed(FAILING_IDS))[:2])

    def test_explicit_instance_preserves_known_failure(self):
        with patch.object(SWEBenchAdapter, "generate_task") as generate_task:
            SWEBenchAdapter(
                output_dir=self.output_dir,
                instance_id=FAILING_IDS[0],
                local_task_id="debug-task",
            ).run()
        generate_task.assert_called_once_with(
            FAILING_IDS[0], "debug-task", overwrite=False
        )
        self.generate_many.assert_not_called()

    def test_no_matching_failures_keeps_all_tasks(self):
        with patch.object(SWEBenchAdapter, "get_all_ids", return_value=FIXED_IDS):
            self.assertEqual(self.selected_ids(), FIXED_IDS)
        self.assertNotIn("Excluding", self.output.getvalue())

    def test_cli_wires_default_and_override(self):
        for flags, expected_count in (([], 496), (["--include-known-failing"], 500)):
            with self.subTest(flags=flags), patch(
                "sys.argv", ["swebench", "--output-dir", str(self.output_dir), *flags]
            ):
                main()
                self.assertEqual(
                    len(self.generate_many.call_args.args[0]), expected_count
                )


if __name__ == "__main__":
    unittest.main()
