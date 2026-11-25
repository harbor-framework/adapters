from __future__ import annotations

import json
import math

import pytest

from harbor_4dcodebench.rewards import (
    GEOMETRY_QUALITY_KEYS,
    REWARD_KEYS,
    ScoreConversionError,
    convert,
)

REAL_ONLY = ("flow_distribution", "track2d_dtw", "depth_error", "uni3d_moge_scene")
SYNTHETIC_ONLY = ("scene_3d", "trajectory_dtw", "emd_step", "occupancy_dtw", "uni3d_point_scene")


def scored(kind: str, value: float = 0.5) -> dict:
    """A reward.json whose applicable metrics all hold `value`, as scorer/outcome.py lays it out."""
    other = SYNTHETIC_ONLY if kind == "real" else REAL_ONLY
    return {key: ("not_applicable" if key in other else value) for key in REWARD_KEYS}


def harbor_valid(rewards: dict) -> bool:
    """Harbor's reward.json rule (verifier.py `_parse_reward_json`): finite int/float values."""
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
               for v in rewards.values())


def test_numbers_pass_through_and_states_are_left_out():
    reward = scored("synthetic", 0.75) | {"dynamic_iou": 0.0, "semantic_dinov3": 1.0}
    rewards, record = convert(reward, {"status": "ok"})
    assert rewards["dynamic_iou"] == 0.0 and rewards["semantic_dinov3"] == 1.0
    assert rewards["scene_3d"] == 0.75
    for key in REAL_ONLY:
        assert key not in rewards
        assert record["readings"][key] == {"reading": "not_applicable", "cause": None, "harbor": None}
    assert rewards["executable"] == 1.0
    assert harbor_valid(rewards)
    assert len(rewards) == len(REWARD_KEYS) - len(REAL_ONLY) + 1


def test_real_case_keeps_the_real_metrics_only():
    rewards, _ = convert(scored("real", 0.25), {"status": "ok"})
    assert set(REAL_ONLY) <= set(rewards)
    assert not set(SYNTHETIC_ONLY) & set(rewards)


def test_error_takes_the_worst_value_of_the_spec():
    reward = scored("real") | {"depth_error": "error", "flow_distribution": "error"}
    detail = {"status": "ok", "causes": {"depth_error": "metric_failure", "flow_distribution": "degenerate"}}
    rewards, record = convert(reward, detail)
    assert rewards["depth_error"] == 2.0      # lower is better, in [0, 2]
    assert rewards["flow_distribution"] == 0.0
    assert record["readings"]["depth_error"] == {"reading": "error", "cause": "metric_failure", "harbor": 2.0}


def test_closed_video_gate():
    reward = {key: "error" for key in REWARD_KEYS} | {key: "not_applicable" for key in REAL_ONLY}
    causes = {key: "no_video" for key in REWARD_KEYS if key not in REAL_ONLY}
    rewards, record = convert(reward, {"status": "gate_failure", "gate_failure": "no_video: Missing render.mp4",
                                       "causes": causes})
    assert rewards["executable"] == 0.0
    assert record["gate_failure"].startswith("no_video")
    for key in GEOMETRY_QUALITY_KEYS:     # averaged over the runs that pass the world gate
        assert key not in rewards
    assert rewards["semantic_dinov3"] == 0.0 and rewards["scene_3d"] == 0.0
    assert harbor_valid(rewards)


def test_closed_world_gate_keeps_render_metrics():
    reward = scored("synthetic", 0.6)
    geometry = [key for key in REWARD_KEYS
                if key not in REAL_ONLY and key not in ("semantic_dinov3", "semantic_tips", "geophys_dinov3")]
    reward |= {key: "error" for key in geometry}
    rewards, _ = convert(reward, {"status": "gate_failure", "causes": {key: "no_world" for key in geometry}})
    assert rewards["semantic_tips"] == 0.6
    assert rewards["scene_3d"] == 0.0
    assert "mesh_watertight" not in rewards
    assert rewards["executable"] == 0.0


def test_geometry_quality_failure_past_the_gate_scores_zero():
    reward = scored("synthetic") | {"mesh_manifold": "error"}
    rewards, _ = convert(reward, {"status": "ok", "causes": {"mesh_manifold": "metric_failure"}})
    assert rewards["mesh_manifold"] == 0.0


@pytest.mark.parametrize("state", ["excluded", "uncomputable"])
def test_unscored_states_are_left_out(state):
    reward = scored("real") | {"dynamic_iou": state}
    rewards, record = convert(reward, {"status": "ok", "causes": {"dynamic_iou": "transparent"}})
    assert "dynamic_iou" not in rewards
    assert record["readings"]["dynamic_iou"]["reading"] == state


@pytest.mark.parametrize("reward, detail, message", [
    ({k: 0.5 for k in REWARD_KEYS if k != "scene_3d"}, {"status": "ok"}, "missing"),
    ({k: 0.5 for k in REWARD_KEYS} | {"overall": 0.5}, {"status": "ok"}, "unknown"),
    ({k: 0.5 for k in REWARD_KEYS} | {"scene_3d": "pending"}, {"status": "ok"}, "unknown reading"),
    ({k: 0.5 for k in REWARD_KEYS} | {"scene_3d": float("nan")}, {"status": "ok"}, "non-finite"),
    ({k: 0.5 for k in REWARD_KEYS} | {"scene_3d": True}, {"status": "ok"}, "boolean"),
    ({k: 0.5 for k in REWARD_KEYS}, {}, "gate verdict"),
    ([], {"status": "ok"}, "JSON objects"),
])
def test_unusable_scorer_output_raises(reward, detail, message):
    with pytest.raises(ScoreConversionError, match=message):
        convert(reward, detail)


def test_output_is_json_serialisable_without_special_floats():
    rewards, record = convert(scored("synthetic"), {"status": "ok"})
    json.dumps(rewards, allow_nan=False)
    json.dumps(record, allow_nan=False)
