"""Checks against a real 4DCodeBench checkout (HARBOR_4DCODEBENCH_UPSTREAM); skipped without one."""

from __future__ import annotations

import importlib
import importlib.util
import sys

import pytest

from conftest import add_case
from harbor_4dcodebench import rewards
from harbor_4dcodebench.adapter import REQUIRED_DATA, Harbor4DCodeBenchAdapter, render_agent_context, upstream_paths


@pytest.fixture
def upstream_modules(upstream, monkeypatch):
    monkeypatch.syspath_prepend(str(upstream))
    for name in [name for name in sys.modules if name.split(".")[0] in ("scorer", "config", "checker")]:
        monkeypatch.delitem(sys.modules, name)
    return upstream


def test_reward_keys_match_the_scorer(upstream_modules):
    try:
        score = importlib.import_module("scorer.score")
    except ImportError as error:   # the scorer's own dependencies (numpy, h5py)
        pytest.skip(f"cannot import scorer.score: {error}")
    outcome = importlib.import_module("scorer.outcome")
    assert tuple(score.REWARD_KEYS) == rewards.REWARD_KEYS
    assert tuple(score.WORLD_KEYS) == rewards.GEOMETRY_QUALITY_KEYS
    assert {outcome.NO_VIDEO, outcome.UNDECODABLE_VIDEO, outcome.VIDEO_MISMATCH,
            outcome.NO_WORLD, outcome.INVALID_WORLD} == set(rewards.GATE_CAUSES)
    assert rewards.ERROR == outcome.ERROR
    assert set(rewards.UNSCORED_STATES) == {outcome.NOT_APPLICABLE, outcome.EXCLUDED, outcome.UNCOMPUTABLE}


def test_required_estimates_are_the_scorer_file_names(upstream_modules):
    estimates = importlib.import_module("config.estimates")
    names = {estimates.FLOW_FILENAME, estimates.TRACKS_FILENAME, estimates.MOGE_FILENAME,
             estimates.DEPTH_FILENAME, estimates.SEMANTIC_FILENAME.format(name="dinov3"),
             estimates.SEMANTIC_FILENAME.format(name="tips"), estimates.GEOPHYS_FILENAME.format(name="dinov3")}
    required = {entry.split("/", 1)[1] for kind in REQUIRED_DATA.values() for entry in kind
                if entry.startswith(estimates.ESTIMATES_DIRNAME + "/")}
    assert required == names


def test_task_md_renders_as_the_upstream_harness_renders_it(upstream, tmp_path):
    spec = importlib.util.spec_from_file_location("_upstream_infer", upstream / "harness" / "runtime" / "infer.py")
    infer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(infer)
    infer.prepare_agent_context(tmp_path / "upstream")
    ours = render_agent_context(upstream, tmp_path / "ours")
    theirs = (tmp_path / "upstream" / "TASK.md").read_text(encoding="utf-8")
    # infer.py writes str(Path): POSIX paths on Linux, backslashes on a Windows host
    assert "\\" not in (upstream / "harness" / "agent_context" / "TASK.md").read_text(encoding="utf-8")
    assert ours == theirs.replace("\\", "/")
    assert upstream_paths(upstream) == {"task": "/task", "entrypoint": "TASK.md", "video": "/input/reference.mp4",
                                        "world": "/workspace/world", "solution": "/workspace/solution"}


def test_generation_from_the_upstream_checkout(upstream, tmp_path):
    data_home = tmp_path / "bench"
    add_case(data_home, "synthetic", "B_01")
    add_case(data_home, "real", "abc_130k_01_dual_arm_robotic")
    written = Harbor4DCodeBenchAdapter(tmp_path / "out", repo=upstream, cases_root=data_home / "cases",
                                       data_root=data_home / "data").run()
    assert [path.name for path in written] == ["synthetic-b-01", "real-abc-130k-01-dual-arm-robotic"]
    instruction = (written[0] / "instruction.md").read_text(encoding="utf-8")
    assert instruction.startswith("`input.mp4` is a video of a dynamic scene.")
    assert "{{" not in instruction and "`/workspace/world`" in instruction
