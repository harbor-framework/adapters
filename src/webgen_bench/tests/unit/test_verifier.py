import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from webgen_bench.adapter import TEMPLATE_DIR


@pytest.fixture
def verifier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(
        "webgen_verifier", TEMPLATE_DIR / "tests" / "test_ui.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(module, "REWARD_PATH", tmp_path / "reward.txt")
    return module


def test_worker_reduction_preserves_judge_settings(verifier, tmp_path, monkeypatch):
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_BASE_URL", "https://example.invalid/v1")
    tasks = tmp_path / "tasks.jsonl"
    with patch.object(verifier.subprocess, "run") as run:
        verifier.run_webvoyager(tasks)
    command = run.call_args.args[0]
    for flag, value in {
        "--test_file": str(tasks),
        "--num_workers": "3",
        "--max_iter": "15",
        "--max_attached_imgs": "3",
        "--temperature": "1",
        "--seed": "42",
        "--api_model": "test-model",
        "--api_base_url": "https://example.invalid/v1",
    }.items():
        assert command[command.index(flag) + 1] == value
    assert "--headless" in command
    assert "--fix_box_color" in command
    assert run.call_args.kwargs["check"] is True


def test_verdicts_and_missing_results_keep_original_weights(verifier):
    data = {
        "id": "fixture",
        "primary_category": "Utilities",
        "ui_instruct": [{"task_category": {"primary_category": "UI"}}] * 4,
    }
    for index, verdict in enumerate(["YES", "PARTIAL", "NO"]):
        directory = verifier.WORK_DIR / "results" / f"task1_{index}"
        directory.mkdir(parents=True)
        (directory / "interact_messages.json").write_text(
            json.dumps([{"role": "assistant", "content": verdict}])
        )
    assert verifier.compute_score(data) == pytest.approx(1.5 / 4)
    stats = json.loads(
        (verifier.REWARD_PATH.parent / "category_stats.json").read_text()
    )
    assert stats["counts"] == {"YES": 1, "PARTIAL": 1, "NO": 1, "start_failed": 1}
    assert stats["total"] == 4
