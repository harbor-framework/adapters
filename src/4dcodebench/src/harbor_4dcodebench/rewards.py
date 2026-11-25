"""Convert one original 4DCodeBench `reward.json` into a Harbor reward file.

The original scorer (`scorer/score.py`) writes every metric as a number or as one of
four states, `not_applicable`, `excluded`, `error` and `uncomputable`
(`scorer/outcome.py`). Harbor reward files hold finite numbers only, so this module
maps each reading the way the benchmark's own specification aggregates it
(`docs/spec.md`, "Executability and scoring" and "Geometry quality"):

    number                          kept unchanged
    error                           the metric's worst value: 0, or 2 for `depth_error`
    error on a geometry-quality     left out: those metrics are averaged over the runs
      key, from a closed gate        that pass the world gate
    not_applicable, excluded,       left out: the metric is not scored on this case
      uncomputable                   or is omitted for every model

`executable` is 1 when both validation gates passed (`status` "ok" in
`reward.detail.json`) and 0 otherwise. No other key is added, and no combined score
is formed: the paper's Overall score is not implemented by the original scorer.

This file is copied into every generated task's `tests/` and runs in the verifier
with the standard library alone.
"""

from __future__ import annotations

import math
from typing import Any

# The reward keys of `scorer/score.py` (`REWARD_KEYS`) at the pinned upstream commit.
REWARD_KEYS = (
    "dynamic_iou",
    "scene_3d",
    "trajectory_dtw",
    "emd_step",
    "occupancy_dtw",
    "interpenetration",
    "mesh_watertight",
    "mesh_manifold",
    "mesh_clean_faces",
    "mesh_no_self_intersection",
    "uni3d_point_scene",
    "uni3d_moge_scene",
    "flow_distribution",
    "track2d_dtw",
    "semantic_dinov3",
    "semantic_tips",
    "geophys_dinov3",
    "depth_error",
)

# `WORLD_KEYS` of `scorer/score.py`: computed from the submitted world alone
GEOMETRY_QUALITY_KEYS = (
    "interpenetration",
    "mesh_watertight",
    "mesh_manifold",
    "mesh_clean_faces",
    "mesh_no_self_intersection",
)

# docs/spec.md: "`error` is assigned the metric's worst possible value: 0 for
# similarities and 2 for Depth error"
WORST_VALUE = {key: 0.0 for key in REWARD_KEYS} | {"depth_error": 2.0}

ERROR = "error"
UNSCORED_STATES = ("not_applicable", "excluded", "uncomputable")

# the `error` causes a closed gate writes (`scorer/outcome.py`)
GATE_CAUSES = ("no_video", "undecodable_video", "video_mismatch", "no_world", "invalid_world")

EXECUTABLE_KEY = "executable"


class ScoreConversionError(ValueError):
    """The original scorer's output is missing, incomplete or not in the expected form."""


def convert(reward: dict[str, Any], detail: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    """Return the Harbor rewards of one scored world and the record of every reading.

    `reward` and `detail` are the scorer's `reward.json` and `reward.detail.json`.
    Raises `ScoreConversionError` when a reward key is missing or unknown, or a
    reading is neither a finite number nor one of the four states.
    """

    if not isinstance(reward, dict) or not isinstance(detail, dict):
        raise ScoreConversionError("reward.json and reward.detail.json must be JSON objects")
    missing = [key for key in REWARD_KEYS if key not in reward]
    unknown = sorted(set(reward) - set(REWARD_KEYS))
    if missing or unknown:
        raise ScoreConversionError(
            f"reward.json does not hold the expected keys: missing {missing}, unknown {unknown}"
        )
    status = detail.get("status")
    if status not in ("ok", "gate_failure"):
        raise ScoreConversionError(f"reward.detail.json has no gate verdict (status={status!r})")

    causes = detail.get("causes") or {}
    rewards: dict[str, float] = {}
    readings: dict[str, Any] = {}
    for key in REWARD_KEYS:
        value = reward[key]
        cause = causes.get(key)
        if isinstance(value, bool):
            raise ScoreConversionError(f"{key}: unexpected boolean reading {value!r}")
        if isinstance(value, (int, float)):
            if not math.isfinite(value):
                raise ScoreConversionError(f"{key}: non-finite reading {value!r}")
            rewards[key] = float(value)
        elif value == ERROR:
            if not (key in GEOMETRY_QUALITY_KEYS and cause in GATE_CAUSES):
                rewards[key] = WORST_VALUE[key]
        elif value not in UNSCORED_STATES:
            raise ScoreConversionError(f"{key}: unknown reading {value!r}")
        readings[key] = {"reading": value, "cause": cause, "harbor": rewards.get(key)}

    rewards[EXECUTABLE_KEY] = 1.0 if status == "ok" else 0.0
    record = {
        "status": status,
        "gate_failure": detail.get("gate_failure"),
        "executable": rewards[EXECUTABLE_KEY],
        "readings": readings,
    }
    return rewards, record


__all__ = [
    "EXECUTABLE_KEY",
    "GATE_CAUSES",
    "GEOMETRY_QUALITY_KEYS",
    "REWARD_KEYS",
    "ScoreConversionError",
    "WORST_VALUE",
    "convert",
]
