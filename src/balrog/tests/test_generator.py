"""No Docker or model calls: selection, fixture integrity, and filesystem safety."""

from contextlib import contextmanager
import gzip
import io
import json
from pathlib import Path
import tarfile
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from balrog import adapter


def tiny_archive() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:") as archive:
        for name in (
            "balrog/module.py", "LICENSE", "README.md", "setup.py", "pyproject.toml",
            "SECRETS", "balrog/.env", "balrog/__pycache__/old.pyc",
            "balrog/tests/test_example.py", "docs/image.png", "minigrid-text.png",
        ):
            content = b"fixture\n"
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return output.getvalue()


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="balrog-generator-test-")
        self.root = Path(self.temporary.name)
        self.output = self.root / "tasks"

    def tearDown(self):
        self.temporary.cleanup()

    @contextmanager
    def fake_sources(self):
        with patch.object(adapter, "_source_archive", return_value=gzip.compress(tiny_archive(), mtime=0)) as mocked:
            yield mocked

    def test_scope_and_splits_are_fixed_and_balanced(self):
        full = adapter.select_cases("full", None, None)
        self.assertEqual(len(full), 50)
        self.assertEqual(full, adapter.select_cases("parity", None, None))
        sanity = adapter.select_cases("sanity", None, None)
        self.assertEqual(len(sanity), 5)
        self.assertEqual({c["episode"]["seed"] for c in sanity}, {0})
        self.assertEqual({c["episode"]["task"].split("/")[1] for c in sanity}, set(adapter.TASK_TYPES))
        self.assertEqual(full[:5], sanity)
        for kind in adapter.TASK_TYPES:
            self.assertEqual(
                {c["episode"]["seed"] for c in full if c["episode"]["task"].endswith("/" + kind)},
                set(range(10)),
            )
        fixtures = adapter.PACKAGE_DIR / "fixtures"
        for name, field in (("episode.json", "episode"), ("oracle_actions.json", "oracle")):
            self.assertEqual(json.loads((fixtures / name).read_text(encoding="utf-8")), full[0][field])

    def test_filters_and_invalid_requests(self):
        self.assertEqual(adapter.select_cases("full", None, 0), [])
        self.assertEqual(len(adapter.select_cases("full", None, 100)), 50)
        selected = adapter.select_cases("full", ["babyai-open-seed-9", adapter.TASK_ID], 1)
        self.assertEqual(selected[0]["episode"]["task_id"], adapter.TASK_ID)
        for split, ids, limit in (
            ("full", ["../outside"], None), ("sanity", ["babyai-open-seed-9"], None),
            ("full", None, -1), ("missing", None, None),
        ):
            with self.assertRaises(ValueError):
                adapter.select_cases(split, ids, limit)

    def test_all_outputs_are_self_contained_and_archives_are_built_once(self):
        with self.fake_sources() as source:
            generated = adapter.BALROGAdapter(self.output).run()
        self.assertEqual(len(generated), 50)
        self.assertEqual(source.call_count, 2)
        tokens = set()
        for destination, case in zip(generated, adapter.select_cases("full", None, None)):
            config = tomllib.loads((destination / "task.toml").read_text(encoding="utf-8"))
            self.assertEqual(config["task"]["name"], "balrog/" + case["episode"]["task_id"])
            tokens.add(config["verifier"]["env"]["RESULT_TOKEN"])
            for relative, expected in (("environment/episode.json", case["episode"]), ("solution/oracle_actions.json", case["oracle"])):
                self.assertEqual(json.loads((destination / relative).read_text(encoding="utf-8")), expected)
            for name in ("balrog", "minigrid"):
                archive = destination / "environment" / "vendor" / f"{name}.tar.gz"
                self.assertTrue(archive.is_file())
                self.assertFalse(archive.is_symlink())
            for path in destination.rglob("*"):
                if path.is_file() and not path.name.endswith(".tar.gz"):
                    self.assertNotIn(b"\r\n", path.read_bytes(), str(path))
        self.assertEqual(len(tokens), 50)

    def test_existing_later_task_prevents_partial_generation(self):
        existing = self.output / "babyai-pickup-seed-0"
        existing.mkdir(parents=True)
        (existing / "keep.txt").write_text("keep", encoding="utf-8")
        with self.fake_sources() as source, self.assertRaises(FileExistsError):
            adapter.BALROGAdapter(self.output, split="sanity").run()
        source.assert_not_called()
        self.assertFalse((self.output / adapter.TASK_ID).exists())
        self.assertEqual((existing / "keep.txt").read_text(), "keep")

    def test_overwrite_only_changes_selected_task(self):
        with self.fake_sources():
            first = adapter.BALROGAdapter(self.output, split="sanity").run()
            old_configs = {p.name: (p / "task.toml").read_bytes() for p in first}
            updated = adapter.BALROGAdapter(self.output, task_ids=[adapter.TASK_ID], overwrite=True).run()
        self.assertEqual([p.name for p in updated], [adapter.TASK_ID])
        for p in first:
            current = (p / "task.toml").read_bytes()
            if p.name == adapter.TASK_ID:
                self.assertNotEqual(current, old_configs[p.name])
            else:
                self.assertEqual(current, old_configs[p.name])

    def test_source_failure_preserves_existing_output(self):
        existing = self.output / adapter.TASK_ID
        existing.mkdir(parents=True)
        (existing / "keep.txt").write_text("keep", encoding="utf-8")
        with patch.object(adapter, "_source_archive", side_effect=ValueError("wrong commit")):
            with self.assertRaisesRegex(ValueError, "wrong commit"):
                adapter.BALROGAdapter(self.output, limit=1, overwrite=True).run()
        self.assertEqual((existing / "keep.txt").read_text(), "keep")

    def test_output_symlink_is_rejected_without_touching_target(self):
        target = self.root / "elsewhere"
        target.mkdir()
        try:
            self.output.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("This host does not permit creating symlinks")
        with self.fake_sources(), self.assertRaises(ValueError):
            adapter.BALROGAdapter(self.output, overwrite=True).run()
        self.assertEqual(list(target.iterdir()), [])
        self.output.unlink()

    def test_source_archive_is_reproducible_and_excludes_sensitive_members(self):
        raw = tiny_archive()
        with patch.object(adapter, "_git", side_effect=[adapter.BALROG_COMMIT.encode(), raw] * 2):
            first = adapter._source_archive(self.root, adapter.BALROG_COMMIT)
            second = adapter._source_archive(self.root, adapter.BALROG_COMMIT)
        self.assertEqual(first, second)
        with tarfile.open(fileobj=io.BytesIO(first), mode="r:gz") as archive:
            self.assertEqual(archive.getnames(), ["balrog/module.py", "LICENSE", "README.md", "setup.py", "pyproject.toml"])
            self.assertTrue(all(m.mtime == 0 for m in archive.getmembers()))
        with patch.object(adapter, "_git", return_value=b"wrong-commit"):
            with self.assertRaisesRegex(ValueError, "Wrong source commit"):
                adapter._source_archive(self.root, adapter.BALROG_COMMIT)


if __name__ == "__main__":
    unittest.main()
