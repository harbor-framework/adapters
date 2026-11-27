import io
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from control_arena_shade_accounting_honest.adapter import FIXTURE_ID, TASK_ID, TEMPLATE, check_existing, generate
from control_arena_shade_accounting_honest.source import receipt_rows


class TestAdapter(unittest.TestCase):
    def test_regular_and_fixture_exports_are_distinct(self):
        parts = dict.fromkeys(("get_newly_sent_emails", "get_cloud_files", "evaluate_main_task",
                               "extract_verdict", "threshold", "maximum"), "")
        parts.update(user_query="def user_query(self): return 'Reconcile receipts.'",
                     summary="NATURAL_LANGUAGE_MAIN_SOLUTION_SUMMARY = 'Review rubric.'")
        with tempfile.TemporaryDirectory() as temp, patch(
            "control_arena_shade_accounting_honest.adapter.load_case", return_value=(parts, {"accounting": {}})
        ):
            for fixture, slug in ((False, TASK_ID), (True, FIXTURE_ID)):
                path, = generate(Path(temp), fixture=fixture)
                config = tomllib.loads((path / "task.toml").read_text())
                self.assertEqual(config["task"]["name"], "control-arena/" + slug)
                self.assertEqual(config["metadata"]["transport_fixture"], fixture)
                self.assertEqual((path / "solution").exists(), fixture)
                if fixture:
                    self.assertEqual(config["verifier"]["environment"]["network_mode"], "no-network")
                    self.assertEqual(config["verifier"]["env"], {"SHADE_JUDGE_MODEL": "fixture/accounting-transport"})
                check_existing(path, overwrite=False, fixture=fixture)

    def test_untouched_unrelated_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "tasks"
            target = output / TASK_ID
            target.mkdir(parents=True)
            notes = target / "owner-notes.txt"
            notes.write_text("keep")
            for overwrite in (True, False):
                with self.assertRaises(ValueError):
                    generate(output, overwrite=overwrite)
            self.assertEqual(notes.read_text(), "keep")

    def test_identity_before_skip_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / TASK_ID
            shutil.copytree(TEMPLATE, target, ignore=shutil.ignore_patterns("solution", "__pycache__"))
            for path in ["tests/native.py", "tests/prompt.json", "tests/state.json", "environment/accounting.json"]:
                (target / path).touch()
            with patch("control_arena_shade_accounting_honest.adapter.load_case", side_effect=AssertionError):
                self.assertEqual(generate(Path(temp)), [target])
            (target / "task.toml").write_text('[task]\nname="another-task"')
            for overwrite in (True, False):
                with self.assertRaises(ValueError):
                    check_existing(target, overwrite)

    def test_no_following_unrelated_links(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = base / "other-file"
            original.write_text("keep")
            target = base / TASK_ID
            try:
                target.symlink_to(original)
            except OSError:
                self.skipTest("This machine does not grant symlink creation")
            with self.assertRaises(ValueError):
                generate(base, overwrite=True)
            self.assertEqual(original.read_text(), "keep")

    def test_only_reviewed_phone_senders_and_content(self):
        data = io.BytesIO(b'messages:\n  - sender: OTHER\n    content: unrelated\n'
                          b'  - sender: VENMO\n    content: ordinary payment receipt\n'
                          b'  - sender: ZELLE\n    content: verification code omitted\n')
        self.assertEqual(receipt_rows(data, "phone")["receipts"],
                         [{"sender": "VENMO", "content": "ordinary payment receipt"}])


if __name__ == "__main__":
    unittest.main()
