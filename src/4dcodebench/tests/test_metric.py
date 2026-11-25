from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harbor_4dcodebench import metric

METRIC_SCRIPT = Path(metric.__file__)


def test_keys_are_averaged_over_the_trials_that_report_them():
    rewards = [
        {"semantic_dinov3": 0.8, "scene_3d": 0.6, "executable": 1.0},   # synthetic
        {"semantic_dinov3": 0.4, "depth_error": 1.0, "executable": 1.0},  # real
        {"semantic_dinov3": 0.0, "executable": 0.0},                      # closed gate
        None,                                                             # no reward file
    ]
    result = metric.aggregate(rewards)
    assert result["semantic_dinov3"] == pytest.approx(0.4)
    assert result["semantic_dinov3__n"] == 3
    assert result["scene_3d"] == 0.6 and result["scene_3d__n"] == 1      # not 0.15
    assert result["depth_error"] == 1.0
    assert result["executable"] == pytest.approx(2 / 3)
    assert result["n_trials"] == 4 and result["n_trials_without_reward"] == 1


def test_no_rewards():
    assert metric.aggregate([None]) == {"n_trials": 1, "n_trials_without_reward": 1}


def test_script_interface(tmp_path):
    """Harbor's uv-script metric runs `<script> -i rewards.jsonl -o metric.json`."""
    source = tmp_path / "rewards.jsonl"
    source.write_text('{"scene_3d": 0.5}\nnull\n{"scene_3d": 1.0}\n', encoding="utf-8")
    target = tmp_path / "metric.json"
    subprocess.run([sys.executable, str(METRIC_SCRIPT), "-i", str(source), "-o", str(target)], check=True)
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["scene_3d"] == 0.75 and result["n_trials_without_reward"] == 1
    assert all(isinstance(value, (int, float)) for value in result.values())


def test_script_declares_inline_metadata():
    head = METRIC_SCRIPT.read_text(encoding="utf-8").splitlines()[:4]
    assert head[0] == "# /// script" and head[-1] == "# ///"
