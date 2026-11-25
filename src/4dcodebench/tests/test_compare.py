from __future__ import annotations

import json
from pathlib import Path

from harbor_4dcodebench.compare import main
from harbor_4dcodebench.rewards import REWARD_KEYS

REAL_ONLY = ("flow_distribution", "track2d_dtw", "depth_error", "uni3d_moge_scene")


def results(root: Path, reward: dict, status: str = "ok") -> Path:
    root.mkdir(parents=True)
    (root / "reward.json").write_text(json.dumps(reward), encoding="utf-8")
    (root / "reward.detail.json").write_text(json.dumps({"status": status, "alignment": {"residual": 0.01}}),
                                             encoding="utf-8")
    return root


def sanity(value: float) -> dict:
    return {key: ("not_applicable" if key in REAL_ONLY else value) for key in REWARD_KEYS}


def test_matching_readings(tmp_path, capsys):
    a = results(tmp_path / "a", sanity(0.97))
    b = results(tmp_path / "b", sanity(0.97) | {"scene_3d": 0.9700004})
    assert main(["--original", str(a), "--harbor", str(b), "--json", str(tmp_path / "c.json")]) == 0
    rows = {row["key"]: row for row in json.loads((tmp_path / "c.json").read_text())["rows"]}
    assert abs(rows["scene_3d"]["abs_diff"] - 4e-7) < 1e-12
    assert rows["depth_error"]["abs_diff"] is None
    assert "registration residual=0.01" in capsys.readouterr().out


def test_tolerance_and_state_mismatches_fail(tmp_path):
    a = results(tmp_path / "a", sanity(0.97))
    b = results(tmp_path / "b", sanity(0.97) | {"scene_3d": 0.95})
    assert main(["--original", str(a), "--harbor", str(b)]) == 0          # no tolerance by default
    assert main(["--original", str(a), "--harbor", str(b), "--atol", "1e-3"]) == 1
    c = results(tmp_path / "c", sanity(0.97) | {"mesh_watertight": "error"}, status="gate_failure")
    assert main(["--original", str(a), "--harbor", str(c)]) == 1
