"""Regression checks on scorer outputs recorded on a GPU.

Each `fixtures/<case>/` holds files copied unchanged from a real run (RTX A6000,
4DCodeBench 6c466be, Harbor 0.27.0, adapter 20c9878 plus the liquid-only
`required_data` change), one case per reward path:

    b01   gate open, every applicable metric computed (first B_01 validation run)
    b09   world gate closed: a liquid-only reference world without dynamics/
          (no_world), as the original scorer also reports it
    s02   gate open, one metric `error` on both sides (its worker was killed under
          the 32 GiB verifier memory limit)

    original/reward.json, reward.detail.json   upstream scorer on the reference world
                                               (scripts/run_original_sanity.sh)
    harbor/reward.json, reward.detail.json     the same scorer in the Harbor verifier
                                               (oracle trial)
    harbor/harbor_reward.json                  the /logs/verifier/reward.json Harbor read

These tests do not rerun the scorer. They pin the conversion and the comparison to
what the real scorer wrote, so a later change to rewards.py or compare.py cannot
silently change the Harbor rewards of worlds that have been checked on a GPU.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harbor_4dcodebench.compare import compare, load
from harbor_4dcodebench.rewards import EXECUTABLE_KEY, GEOMETRY_QUALITY_KEYS, REWARD_KEYS, convert

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NOT_APPLICABLE_ON_SYNTHETIC = ("uni3d_moge_scene", "flow_distribution", "track2d_dtw", "depth_error")
VIDEO_KEYS = ("semantic_dinov3", "semantic_tips", "geophys_dinov3")
CASES = {"b01": "synthetic/B_01", "b09": "synthetic/B_09", "s02": "synthetic/S_02"}
# fields of reward.detail.json that legitimately differ between the two runs:
# where each side mounted the reference world, and a wall-clock timing
RUN_SPECIFIC = {"reference", "dynamics_seconds"}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(CASES))
def test_recorded_original_and_harbor_readings_match_exactly(name):
    original, harbor = load(FIXTURES / name / "original"), load(FIXTURES / name / "harbor")
    rows, problems = compare(original, harbor, atol=0.0)
    assert problems == []
    assert original[0] == harbor[0]
    assert [row["key"] for row in rows] == list(REWARD_KEYS)
    assert all(row["abs_diff"] in (None, 0.0) for row in rows)
    detail_a, detail_b = original[1], harbor[1]
    assert {key for key in detail_a.keys() | detail_b.keys() if detail_a.get(key) != detail_b.get(key)} <= RUN_SPECIFIC
    case = CASES[name]
    assert (detail_a["reference"], detail_b["reference"]) == (f"/data/{case}/world", f"/bench/data/{case}/world")


@pytest.mark.parametrize("name", sorted(CASES))
def test_recorded_scorer_output_converts_to_the_recorded_harbor_reward(name):
    rewards, record = convert(*load(FIXTURES / name / "harbor"))
    assert rewards == read(FIXTURES / name / "harbor" / "harbor_reward.json")
    for key in NOT_APPLICABLE_ON_SYNTHETIC:
        assert key not in rewards
        assert record["readings"][key]["reading"] == "not_applicable"


def test_open_gate_with_every_metric_computed():
    rewards, record = convert(*load(FIXTURES / "b01" / "harbor"))
    assert rewards[EXECUTABLE_KEY] == 1.0 and record["status"] == "ok"
    assert len(rewards) == len(REWARD_KEYS) - len(NOT_APPLICABLE_ON_SYNTHETIC) + 1


def test_closed_world_gate_scores_world_metrics_at_worst_and_omits_geometry_quality():
    reward, detail = load(FIXTURES / "b09" / "harbor")
    rewards, record = convert(reward, detail)
    assert rewards[EXECUTABLE_KEY] == 0.0 and record["status"] == "gate_failure"
    for key in GEOMETRY_QUALITY_KEYS:
        assert key not in rewards and reward[key] == "error"
    world_keys = set(REWARD_KEYS) - set(GEOMETRY_QUALITY_KEYS) - set(VIDEO_KEYS) - set(NOT_APPLICABLE_ON_SYNTHETIC)
    assert world_keys and all(rewards[key] == 0.0 and reward[key] == "error" for key in world_keys)
    # the video-side metrics do not need the world and are still computed
    assert all(isinstance(reward[key], float) and rewards[key] == reward[key] for key in VIDEO_KEYS)


def test_a_metric_error_with_the_gate_open_scores_its_worst_value():
    reward, detail = load(FIXTURES / "s02" / "harbor")
    rewards, record = convert(reward, detail)
    assert rewards[EXECUTABLE_KEY] == 1.0 and record["status"] == "ok"
    errors = sorted(key for key in REWARD_KEYS if reward[key] == "error")
    assert errors == ["interpenetration"]
    assert rewards["interpenetration"] == 0.0     # a geometry-quality key, scored because the gate is open
    assert all(rewards[key] == reward[key] for key in REWARD_KEYS
               if key not in errors and key not in NOT_APPLICABLE_ON_SYNTHETIC)
