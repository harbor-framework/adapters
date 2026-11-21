"""Ordinary generation consistency regressions from migrated PR #3490."""
import contextlib
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import swebench_multimodal.adapter as module


@pytest.fixture
def adapter(tmp_path):
    source = tmp_path / "source" / "task"
    source.mkdir(parents=True)
    (source / "task.yaml").write_text(yaml.safe_dump({
        "instance_id": "task", "repo": "example/project", "split": "test",
        "image": "swebench/sweb.eval.x86_64.example:latest",
        "log_parser": "parse_log_lighthouse", "eval_type": "pass_and_fail",
        "version": "1.4",
    }))
    for name, value in {"gold.patch": "ordinary fixture", "eval.sh": "exit 0\n",
                        "problem_statement.md": "Fix the ordinary display issue.",
                        "tests.json": '{"FAIL_TO_PASS":["ordinary"],"PASS_TO_PASS":[]}'}.items():
        (source / name).write_text(value)
    return module.SWEBenchMultimodalAdapter(tmp_path / "out", source.parent)


def test_empty_selection_does_not_create_directory_or_lock(adapter):
    adapter.split = "dev"
    with patch.object(Path, "mkdir", side_effect=PermissionError("read-only")):
        assert adapter.generate() == []
    assert not adapter.output_dir.exists()


def test_empty_selection_preserves_unrelated_readonly_directory(adapter):
    adapter.output_dir.mkdir()
    note = adapter.output_dir / "notes.txt"
    note.write_text("keep")
    adapter.split = "dev"
    with patch.object(module, "_file_lock", side_effect=AssertionError("no lock needed")):
        assert adapter.generate() == []
    assert note.read_text() == "keep"


def test_empty_selection_recovers_recognized_backup(adapter):
    backup = adapter.output_dir / ".backup_task_aaaaaaaa"
    backup.mkdir(parents=True)
    (backup / "content").write_text("recover")
    adapter.split = "dev"
    assert adapter.generate() == []
    assert (adapter.output_dir / "task/content").read_text() == "recover"


def test_ambiguous_backups_are_all_preserved(adapter):
    backups = [adapter.output_dir / f".backup_task_{token}" for token in ("aaaaaaaa", "bbbbbbbb")]
    for b, value in zip(backups, ("older", "newer")):
        b.mkdir(parents=True); (b / "content").write_text(value)
    with pytest.raises(RuntimeError, match="Multiple orphaned backups"):
        adapter._recover_orphaned_backups()
    assert not (adapter.output_dir / "task").exists()
    assert [(b / "content").read_text() for b in backups] == ["older", "newer"]


def test_cleanup_stays_inside_install_lock(adapter, monkeypatch):
    adapter.generate_task("task")
    real_lock, real_remove = module._file_lock, shutil.rmtree
    held = False
    @contextlib.contextmanager
    def tracked(path):
        nonlocal held
        with real_lock(path):
            held = True
            try: yield
            finally: held = False
    def remove(path, *args, **kwargs):
        if Path(path).name.startswith(".backup_"):
            assert held
        return real_remove(path, *args, **kwargs)
    monkeypatch.setattr(module, "_file_lock", tracked)
    monkeypatch.setattr(shutil, "rmtree", remove)
    adapter.generate_task("task", overwrite=True)


def test_stale_backup_cannot_replace_latest_after_interrupted_swap(adapter, monkeypatch):
    current = adapter.generate_task("task")
    (current / "content").write_text("latest")
    stale = adapter.output_dir / ".backup_task_aaaaaaaa"
    stale.mkdir(); (stale / "content").write_text("old")
    real_rename = Path.rename
    def interrupted(path, target):
        if path.name.startswith(".tmp_"):
            raise KeyboardInterrupt("synthetic interrupted installation")
        return real_rename(path, target)
    monkeypatch.setattr(Path, "rename", interrupted)
    with pytest.raises(KeyboardInterrupt):
        adapter.generate_task("task", overwrite=True)
    assert (current / "content").read_text() == "latest"
    assert not stale.exists()
    assert not list(adapter.output_dir.glob(".backup_*"))


def test_failed_old_backup_cleanup_prevents_new_backup(adapter, monkeypatch):
    current = adapter.generate_task("task")
    (current / "content").write_text("latest")
    stale = adapter.output_dir / ".backup_task_aaaaaaaa"
    stale.mkdir(); (stale / "content").write_text("old")
    real_remove = shutil.rmtree
    def fail(path, *args, **kwargs):
        if Path(path) == stale:
            raise OSError("synthetic cleanup failure")
        return real_remove(path, *args, **kwargs)
    monkeypatch.setattr(shutil, "rmtree", fail)
    with pytest.raises(OSError, match="synthetic cleanup failure"):
        adapter.generate_task("task", overwrite=True)
    assert (current / "content").read_text() == "latest"
    assert list(adapter.output_dir.glob(".backup_*")) == [stale]


def test_process_exit_during_swap_recovers_latest(adapter):
    """A child exits without finally blocks after the current task is backed up."""
    import subprocess

    current = adapter.generate_task("task")
    (current / "content").write_text("latest")
    stale = adapter.output_dir / ".backup_task_aaaaaaaa"
    stale.mkdir()
    (stale / "content").write_text("old")
    code = """
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from swebench_multimodal.adapter import SWEBenchMultimodalAdapter
real_rename = Path.rename
def interrupted(path, target):
    if path.name.startswith('.tmp_'):
        os._exit(23)
    return real_rename(path, target)
Path.rename = interrupted
SWEBenchMultimodalAdapter(Path(sys.argv[2]), Path(sys.argv[3])).generate_task('task', overwrite=True)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(Path(module.__file__).parents[1]),
         str(adapter.output_dir), str(adapter.source_dir)],
        timeout=10, capture_output=True, text=True,
    )
    assert result.returncode == 23, result.stderr
    assert not current.exists()
    assert len(list(adapter.output_dir.glob(".backup_*"))) == 1
    adapter._recover_orphaned_backups()
    assert (current / "content").read_text() == "latest"
