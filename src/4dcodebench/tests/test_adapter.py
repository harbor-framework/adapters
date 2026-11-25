from __future__ import annotations

import json
import re
import shutil
import tomllib
from pathlib import Path

import pytest

from conftest import add_case
from harbor_4dcodebench.adapter import (
    AdapterError,
    Harbor4DCodeBenchAdapter,
    REQUIRED_DATA,
    task_id_for,
)
from harbor_4dcodebench.main import main

TASK_IDS = ["real-abc-130k-01-dual-arm-robotic", "real-phys101-01-solid-object-dropped",
            "synthetic-b-01", "synthetic-li-08"]


def generate(repo: Path, out: Path, **options) -> list[Path]:
    return Harbor4DCodeBenchAdapter(out, repo=repo, **options).run()


def files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def test_one_task_per_case_with_stable_names(benchmark, tmp_path):
    written = generate(benchmark, tmp_path / "out")
    assert sorted(path.name for path in written) == TASK_IDS
    assert task_id_for("synthetic", "B_01") == "synthetic-b-01"
    again = generate(benchmark, tmp_path / "again")
    assert [path.name for path in again] == [path.name for path in written]
    assert (tmp_path / "out" / "metric.py").is_file()


def test_task_layout_and_config(benchmark, tmp_path):
    generate(benchmark, tmp_path / "out", task_ids=["B_01"])
    task = tmp_path / "out" / "synthetic-b-01"
    for name in ("task.toml", "instruction.md", "environment/Dockerfile", "solution/solve.sh",
                 "tests/test.sh", "tests/Dockerfile", "tests/run_verifier.py", "tests/rewards.py"):
        assert (task / name).is_file(), name
    config = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
    assert config["version"] == "1.0"
    assert config["task"]["name"] == "4dcodebench/synthetic-b-01"
    assert config["task"]["authors"][0] == {"name": "Ruihong Shen"}
    assert config["metadata"]["case"] == "synthetic/B_01"
    assert config["metadata"]["oracle"] == "reference-world"
    assert config["verifier"]["environment_mode"] == "separate"
    assert config["verifier"]["environment"]["network_mode"] == "no-network"
    assert config["verifier"]["environment"]["gpus"] == 1 and config["environment"]["gpus"] == 1
    assert config["verifier"]["env"]["OMP_NUM_THREADS"] == "8"
    assert config["agent"]["timeout_sec"] == 21600
    assert "network_mode" not in config["agent"]        # upstream: the agent's default network
    assert config["artifacts"] == [{"source": "/workspace/world"}, {"source": "/workspace/solution"}]
    case = json.loads((task / "tests" / "case.json").read_text(encoding="utf-8"))
    assert case["case"] == "synthetic/B_01"
    assert case["required_data"] == list(REQUIRED_DATA["synthetic"])
    assert case["task_timeout_sec"] == 1800 and case["task_prepare_timeout_sec"] == 600


def test_no_placeholder_is_left_unrendered(benchmark, tmp_path):
    generate(benchmark, tmp_path / "out")
    for task in (tmp_path / "out").iterdir():
        if not task.is_dir():
            continue
        for name in ("task.toml", "environment/Dockerfile", "tests/Dockerfile", "solution/solve.sh"):
            text = (task / name).read_text(encoding="utf-8")
            assert not re.search(r"\{[a-z_]+\}", text), f"{task.name}/{name}"
            assert "\r" not in text


def test_instruction_is_the_rendered_task_md(benchmark, tmp_path):
    generate(benchmark, tmp_path / "out", task_ids=["synthetic/B_01"])
    task = tmp_path / "out" / "synthetic-b-01"
    instruction = (task / "instruction.md").read_text(encoding="utf-8")
    assert "`/workspace/solution` is the program" in instruction
    assert "`/workspace/world` is in `/task/world-format.md`" in instruction
    assert "match `/input/reference.mp4`" in instruction
    assert '{"intrinsics": K, "extrinsic": E}' in instruction
    assert "{{" not in instruction and "\\" not in instruction
    assert (task / "environment" / "task" / "TASK.md").read_text(encoding="utf-8").rstrip("\n") == instruction.rstrip("\n")
    assert (task / "environment" / "task" / "world-format.md").is_file()


@pytest.mark.parametrize("task_id", ["synthetic-b-01", "real-abc-130k-01-dual-arm-robotic"])
def test_agent_environment_holds_no_evaluation_data(benchmark, tmp_path, task_id):
    """The agent image is built from environment/ alone: only the task context and the video."""
    generate(benchmark, tmp_path / "out", task_ids=[task_id])
    task = tmp_path / "out" / task_id
    assert files(task / "environment") == ["Dockerfile", "docker-compose.yaml", "input/reference.mp4",
                                           "task/TASK.md", "task/render-settings.md", "task/world-format.md"]
    secrets = [path for path in (task / "environment").rglob("*")
               if path.is_file() and b"SECRET" in path.read_bytes()]
    assert secrets == []
    assert "SECRET" not in (task / "instruction.md").read_text(encoding="utf-8")
    dockerfile = (task / "environment" / "Dockerfile").read_text(encoding="utf-8")
    assert re.findall(r"^COPY .*$", dockerfile, re.MULTILINE) == [
        "COPY task/ /task/", "COPY input/reference.mp4 /input/reference.mp4"]


def test_verifier_holds_the_reference_data(benchmark, tmp_path):
    generate(benchmark, tmp_path / "out")
    synthetic = tmp_path / "out" / "synthetic-b-01" / "tests" / "bench"
    assert (synthetic / "cases/synthetic/B_01/reference.mp4").is_file()
    assert (synthetic / "data/synthetic/B_01/world/meshes/1.npz").read_bytes().startswith(b"SECRET")
    assert (synthetic / "data/synthetic/B_01/estimates/semantic_tips.npz").is_file()
    real = tmp_path / "out" / "real-abc-130k-01-dual-arm-robotic" / "tests" / "bench" / "data" / "real"
    assert (real / "abc_130k_01_dual_arm_robotic/annotation/dynamic_mask.npz").is_file()
    assert (real / "abc_130k_01_dual_arm_robotic/estimates/depth.h5").is_file()
    dockerfile = (tmp_path / "out" / "synthetic-b-01" / "tests" / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM 4dcb/scorer-checkpoints:dev" in dockerfile and "ENTRYPOINT []" in dockerfile


def test_synthetic_oracle_submits_the_reference_world(benchmark, tmp_path):
    generate(benchmark, tmp_path / "out", task_ids=["B_01"])
    solution = tmp_path / "out" / "synthetic-b-01" / "solution"
    assert files(solution) == ["build.sh", "solve.sh", "world/camera.json", "world/dynamics/body.npz",
                               "world/meshes/1.npz", "world/render.mp4"]
    solve = (solution / "solve.sh").read_text(encoding="utf-8")
    assert "cp -a /solution/world /workspace/world" in solve
    build = (solution / "build.sh").read_text(encoding="utf-8")
    assert "ORACLE PLACEHOLDER" in build and build.rstrip().endswith("exit 1")


def test_real_oracle_is_marked_unresolved(benchmark, tmp_path):
    generate(benchmark, tmp_path / "out", task_ids=["abc_130k_01_dual_arm_robotic"])
    task = tmp_path / "out" / "real-abc-130k-01-dual-arm-robotic"
    assert files(task / "solution") == ["solve.sh"]
    solve = (task / "solution" / "solve.sh").read_text(encoding="utf-8")
    assert "UNRESOLVED" in solve and solve.rstrip().endswith("exit 1")
    assert tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))["metadata"]["oracle"] == "unresolved"


def test_split_selection_and_limit(benchmark, tmp_path):
    assert [p.name for p in generate(benchmark, tmp_path / "a", split="synthetic")] == ["synthetic-b-01", "synthetic-li-08"]
    assert [p.name for p in generate(benchmark, tmp_path / "b", split="real", limit=1)] == [TASK_IDS[0]]


def test_task_id_forms(benchmark, tmp_path):
    written = generate(benchmark, tmp_path / "out",
                       task_ids=["4dcodebench/synthetic-li-08", "real/phys101_01_solid_object_dropped"])
    assert sorted(path.name for path in written) == ["real-phys101-01-solid-object-dropped", "synthetic-li-08"]
    with pytest.raises(AdapterError, match="unknown task ids"):
        generate(benchmark, tmp_path / "bad", task_ids=["B_99"])


def test_missing_reference_data_fails_or_is_skipped(fake_repo, tmp_path):
    add_case(fake_repo, "synthetic", "B_01")
    add_case(fake_repo, "synthetic", "B_02", complete=False)
    with pytest.raises(AdapterError, match=r"reference data missing .*synthetic/B_02: \['world/render.mp4'"):
        generate(fake_repo, tmp_path / "out")
    assert not (tmp_path / "out").exists()       # nothing is written before the check
    written = generate(fake_repo, tmp_path / "out", skip_incomplete=True)
    assert [path.name for path in written] == ["synthetic-b-01"]


def test_missing_inputs_are_reported(fake_repo, tmp_path):
    with pytest.raises(AdapterError, match="cases root does not exist"):
        generate(fake_repo, tmp_path / "out")
    (fake_repo / "cases" / "real").mkdir(parents=True)
    with pytest.raises(AdapterError, match="no <kind>/<case>/reference.mp4"):
        generate(fake_repo, tmp_path / "out")
    add_case(fake_repo, "real", "x")
    shutil.rmtree(fake_repo / "harness" / "agent_context")
    with pytest.raises(AdapterError, match="not a 4DCodeBench checkout"):
        generate(fake_repo, tmp_path / "out")
    assert not (tmp_path / "out" / "real-x").exists()
    assert not (tmp_path / "out" / "real-x.partial").exists()


def test_overwrite(benchmark, tmp_path):
    out = tmp_path / "out"
    generate(benchmark, out, task_ids=["B_01"])
    marker = out / "synthetic-b-01" / "marker"
    marker.write_text("kept", encoding="utf-8")
    assert generate(benchmark, out, task_ids=["B_01"]) == []
    assert marker.exists()
    generate(benchmark, out, task_ids=["B_01"], overwrite=True)
    assert not marker.exists()


def test_custom_data_roots_and_images(benchmark, tmp_path):
    moved = tmp_path / "elsewhere"
    moved.mkdir()
    (benchmark / "cases").rename(moved / "cases")
    (benchmark / "data").rename(moved / "data")
    generate(benchmark, tmp_path / "out", task_ids=["B_01"], cases_root=moved / "cases",
             data_root=moved / "data", agent_image="registry/agent:1", scorer_image="registry/scorer:1",
             agent_network="allowlist", agent_allowed_hosts=["pypi.org"])
    task = tmp_path / "out" / "synthetic-b-01"
    assert "FROM registry/agent:1" in (task / "environment" / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM registry/scorer:1" in (task / "tests" / "Dockerfile").read_text(encoding="utf-8")
    agent = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))["agent"]
    assert agent["network_mode"] == "allowlist" and agent["allowed_hosts"] == ["pypi.org"]


def test_cli(benchmark, tmp_path, capsys):
    main(["--repo", str(benchmark), "--output-dir", str(tmp_path / "out"), "--split", "real",
          "--limit", "1", "--overwrite"])
    assert [p.name for p in (tmp_path / "out").iterdir() if p.is_dir()] == [TASK_IDS[0]]
    with pytest.raises(SystemExit) as raised:
        main(["--repo", str(tmp_path / "missing"), "--output-dir", str(tmp_path / "x")])
    assert raised.value.code == 1
