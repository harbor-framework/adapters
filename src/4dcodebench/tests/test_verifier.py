"""Run the generated tests/run_verifier.py against a stand-in for `python -m scorer`.

The stand-in follows the scorer's manifest and root contract (`scorer/paths.py`): it
resolves each entry's `world` and `out` against `--runs`, reads the gate inputs, and
writes `results/reward.json` and `reward.detail.json` the way `scorer/score.py` lays
them out. It is not the real scorer; the real one runs only in the GPU verifier image.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from harbor_4dcodebench.adapter import Harbor4DCodeBenchAdapter
from harbor_4dcodebench.rewards import REWARD_KEYS

FAKE_SCORER = '''
import argparse, json, os, sys
from pathlib import Path

REWARD_KEYS = __REWARD_KEYS__
REAL_ONLY = ("flow_distribution", "track2d_dtw", "depth_error", "uni3d_moge_scene")

parser = argparse.ArgumentParser()
for flag in ("--manifest", "--cases", "--data", "--runs", "--checkpoints",
             "--task-timeout", "--prepare-timeout"):
    parser.add_argument(flag)
args = parser.parse_args()
mode = os.environ.get("FAKE_SCORER_MODE", "ok")
Path(os.environ["FAKE_SCORER_ARGS"]).write_text(json.dumps(vars(args)))
if mode == "crash":
    sys.exit(2)
for entry in json.loads(Path(args.manifest).read_text()):
    def resolve(path):
        name, _, rest = path.partition("/")
        assert name == "runs", path
        return Path(args.runs) / rest
    world, out = resolve(entry["world"]), resolve(entry["out"])
    assert (Path(args.cases) / entry["case"] / "reference.mp4").is_file()
    readable = (world / "render.mp4").is_file()
    gate = readable and (world.parent / "solution" / "build.sh").is_file()
    reward = {key: ("not_applicable" if key in REAL_ONLY else (0.9 if gate else "error"))
              for key in REWARD_KEYS}
    causes = {} if gate else {key: "no_video" for key, value in reward.items() if value == "error"}
    if mode == "partial":
        reward.pop("scene_3d")
    results = out / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / "reward.json").write_text(json.dumps(reward))
    (results / "reward.detail.json").write_text(json.dumps(
        {"status": "ok" if gate else "gate_failure", "causes": causes,
          "gate_failure": None if gate else "no_video: Missing render.mp4"}))
    sys.exit(0 if gate else 1)
'''


@pytest.fixture
def verifier(benchmark, tmp_path, monkeypatch):
    """The generated verifier of synthetic/B_01, with its container paths under tmp_path."""

    Harbor4DCodeBenchAdapter(tmp_path / "out", repo=benchmark, task_ids=["B_01"]).run()
    tests = tmp_path / "out" / "synthetic-b-01" / "tests"
    spec = importlib.util.spec_from_file_location("run_verifier_under_test", tests / "run_verifier.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    root = tmp_path / "container"
    (root / "checkpoints" / "dinov3-vitl16-pretrain-lvd1689m").mkdir(parents=True)
    monkeypatch.setattr(module, "BENCH", tests / "bench")
    monkeypatch.setattr(module, "CHECKPOINTS", root / "checkpoints")
    monkeypatch.setattr(module, "RUNS_ROOT", root)
    monkeypatch.setattr(module, "WORKSPACE", root / "workspace")
    monkeypatch.setattr(module, "LOGS", root / "logs" / "verifier")
    monkeypatch.setattr(module, "OUT", root / "logs" / "verifier" / "4dcodebench")
    monkeypatch.setattr(module, "MANIFEST", root / "tmp" / "manifest.json")

    scorer = tmp_path / "scorer-root" / "scorer"
    scorer.mkdir(parents=True)
    (scorer / "__init__.py").write_text("")
    (scorer / "__main__.py").write_text(FAKE_SCORER.replace("__REWARD_KEYS__", repr(REWARD_KEYS)))
    monkeypatch.setenv("SCORER_ROOT", str(scorer.parent))
    monkeypatch.setenv("FAKE_SCORER_ARGS", str(tmp_path / "scorer-args.json"))
    module.root = root
    module.solution = tmp_path / "out" / "synthetic-b-01" / "solution"
    return module


def deliver(root: Path, solution: Path) -> None:
    """What the oracle's solve.sh leaves in /workspace."""
    import shutil
    shutil.copytree(solution / "world", root / "workspace" / "world")
    (root / "workspace" / "solution").mkdir(parents=True)
    shutil.copy(solution / "build.sh", root / "workspace" / "solution" / "build.sh")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_scored_world_writes_harbor_rewards(verifier, tmp_path):
    deliver(verifier.root, verifier.solution)
    assert verifier.main() == 0
    logs = verifier.root / "logs" / "verifier"
    rewards = read(logs / "reward.json")
    assert rewards["executable"] == 1.0 and rewards["scene_3d"] == 0.9
    assert "depth_error" not in rewards
    readings = read(logs / "4dcodebench_readings.json")
    assert readings["case"] == "synthetic/B_01" and readings["status"] == "ok"
    assert readings["readings"]["depth_error"]["reading"] == "not_applicable"
    assert (logs / "4dcodebench" / "results" / "reward.json").is_file()   # original output kept
    manifest = read(verifier.root / "tmp" / "manifest.json")
    assert manifest == [{"case": "synthetic/B_01", "world": "runs/workspace/world",
                         "out": "runs/logs/verifier/4dcodebench"}]
    args = read(tmp_path / "scorer-args.json")
    assert args["runs"] == str(verifier.root)
    assert args["task_timeout"] == "1800" and args["prepare_timeout"] == "600"


def test_missing_submission_is_scored_not_failed(verifier):
    """No world at all: the scorer's video gate closes, which is a score, not an infra error."""
    assert verifier.main() == 0
    rewards = read(verifier.root / "logs" / "verifier" / "reward.json")
    assert rewards["executable"] == 0.0 and rewards["semantic_dinov3"] == 0.0
    assert "mesh_watertight" not in rewards


@pytest.mark.parametrize("mode, message", [("crash", "wrote no reward.json"),
                                           ("partial", "unusable scorer output")])
def test_scorer_failure_writes_no_reward(verifier, monkeypatch, mode, message):
    monkeypatch.setenv("FAKE_SCORER_MODE", mode)
    deliver(verifier.root, verifier.solution)
    assert verifier.main() == 1
    logs = verifier.root / "logs" / "verifier"
    assert not (logs / "reward.json").exists()
    assert message in (logs / "4dcodebench_failure.txt").read_text(encoding="utf-8")


def test_missing_checkpoints_or_data_fail_before_scoring(verifier, monkeypatch, tmp_path):
    monkeypatch.setattr(verifier, "CHECKPOINTS", tmp_path / "nowhere")
    assert verifier.main() == 1
    assert "checkpoints missing" in (verifier.root / "logs" / "verifier" / "4dcodebench_failure.txt").read_text()
    monkeypatch.setattr(verifier, "CHECKPOINTS", verifier.root / "checkpoints")
    import shutil
    shutil.rmtree(verifier.BENCH / "data" / "synthetic" / "B_01" / "estimates")
    assert verifier.main() == 1
    assert "reference data missing" in (verifier.root / "logs" / "verifier" / "4dcodebench_failure.txt").read_text()
    assert not (tmp_path / "scorer-args.json").exists()
