"""Fixtures: a minimal 4DCodeBench checkout and data root, written to a temporary directory.

Set HARBOR_4DCODEBENCH_UPSTREAM to a real 4DCodeBench checkout to also run the tests
that compare against the upstream code (`test_upstream.py`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

CHECKER_PATHS = '''"""Fixed Agent container interface."""

from pathlib import Path

WORKSPACE_DIR = Path("/workspace")
WORLD_DIR = WORKSPACE_DIR / "world"
SOLUTION_DIR = WORKSPACE_DIR / "solution"
SOLUTION_ENTRYPOINT = SOLUTION_DIR / "build.sh"
VIDEO_PATH = Path("/input/reference.mp4")
HOME_DIR = Path("/root")
'''

COMMON = '''CASE_VIDEO = "reference.mp4"
TASK_ENTRYPOINT = "TASK.md"
TASK_MOUNT = Path("/task")
'''

TASK_MD = """`input.mp4` is a video of a dynamic scene.

1. `{{paths.solution}}` is the program, an executable `build.sh`.
2. `{{paths.world}}` is its output: {"intrinsics": K, "extrinsic": E}.

The full format of `{{paths.world}}` is in `{{paths.task}}/world-format.md`.
`render.mp4` must match `{{paths.video}}` in frame count.
"""

SYNTHETIC_DATA = ("world/camera.json", "world/render.mp4", "world/meshes/1.npz",
                  "world/dynamics/body.npz", "estimates/semantic_dinov3.npz",
                  "estimates/semantic_tips.npz", "estimates/geophys_dinov3.npz")
REAL_DATA = ("annotation/dynamic_mask.npz", "estimates/semantic_dinov3.npz",
             "estimates/semantic_tips.npz", "estimates/geophys_dinov3.npz", "estimates/flow.h5",
             "estimates/tracks.npz", "estimates/moge.npz", "estimates/depth.h5")


def write(path: Path, content: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "4DCodeBench"
    write(repo / "checker" / "paths.py", CHECKER_PATHS)
    write(repo / "harness" / "runtime" / "common.py", COMMON)
    write(repo / "harness" / "agent_context" / "TASK.md", TASK_MD)
    write(repo / "harness" / "agent_context" / "world-format.md", "# world format\n")
    write(repo / "harness" / "agent_context" / "render-settings.md", "# render settings\n")
    return repo


def add_case(repo: Path, kind: str, name: str, complete: bool = True) -> None:
    write(repo / "cases" / kind / name / "reference.mp4", f"video {kind}/{name}".encode())
    entries = SYNTHETIC_DATA if kind == "synthetic" else REAL_DATA
    for entry in entries if complete else entries[:1]:
        write(repo / "data" / kind / name / entry, f"SECRET {kind}/{name}/{entry}".encode())


@pytest.fixture
def benchmark(fake_repo: Path) -> Path:
    """Two synthetic and two real cases, all with complete reference data."""
    for kind, name in (("synthetic", "B_01"), ("synthetic", "LI_08"),
                       ("real", "abc_130k_01_dual_arm_robotic"), ("real", "phys101_01_solid_object_dropped")):
        add_case(fake_repo, kind, name)
    return fake_repo


@pytest.fixture
def upstream() -> Path:
    value = os.environ.get("HARBOR_4DCODEBENCH_UPSTREAM")
    if not value or not (Path(value) / "scorer" / "score.py").is_file():
        pytest.skip("set HARBOR_4DCODEBENCH_UPSTREAM to a 4DCodeBench checkout")
    return Path(value)
