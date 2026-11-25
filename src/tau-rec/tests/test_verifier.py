"""Verifier tests: Harbor rewards must equal the native tau-Rec rewards.

The fixtures are native Inspect-run traces (success, constraint failure, policy
failure) with their recorded ``evaluation``; the verifier re-scores the bare trace.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import ROOT, TEMPLATE_DIR, load_module

TESTS_DIR = TEMPLATE_DIR / "tests"
FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("task_*_trial*.json"))
evaluate = load_module(TESTS_DIR / "evaluate.py")


def run(tmp_path, task_id, trace_path):
    return evaluate.main(
        [
            "--task-id", task_id,
            "--trace", str(trace_path),
            "--reward", str(tmp_path / "out" / "reward.txt"),
            "--result", str(tmp_path / "out" / "result.json"),
        ]
    )  # fmt: skip


def test_fixtures_cover_success_constraint_and_policy_failure():
    evals = [json.loads(f.read_text())["evaluation"] for f in FIXTURES]
    assert any(e["primary_reward"] == 1.0 for e in evals)
    assert any(
        e["constraint_score"] == 0 and not e["policy_detail"]["violations"]
        for e in evals
    )
    assert any(e["policy_detail"]["violations"] for e in evals)


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.stem)
def test_reward_matches_native(tmp_path, fixture):
    t = json.loads(fixture.read_text())
    expected = t.pop("evaluation")
    (tmp_path / "t.json").write_text(json.dumps(t))
    assert run(tmp_path, t["task_id"], tmp_path / "t.json") == 0
    assert (
        float((tmp_path / "out" / "reward.txt").read_text())
        == expected["primary_reward"]
    )
    result = json.loads((tmp_path / "out" / "result.json").read_text())
    assert result["primary_reward"] == expected["primary_reward"]
    assert result["constraint_score"] == expected["constraint_score"]
    assert result["policy_score"] == expected["policy_score"]
    assert (
        result["policy_detail"]["violations"] == expected["policy_detail"]["violations"]
    )


@pytest.mark.parametrize("content", [None, "{not json", '{"task_id": 3}', ""])
def test_missing_and_corrupt_trace(tmp_path, content):
    trace = tmp_path / "t.json"
    if content is not None:
        trace.write_text(content)
    assert run(tmp_path, "task_004", trace) == 0
    assert (tmp_path / "out" / "reward.txt").read_text() == "0"
    assert "error" in json.loads((tmp_path / "out" / "result.json").read_text())


def test_trace_for_another_task_scores_zero(tmp_path):
    t = json.loads(FIXTURES[0].read_text())
    t.pop("evaluation")
    (tmp_path / "t.json").write_text(json.dumps(t))
    other = "task_001" if t["task_id"] != "task_001" else "task_002"
    assert run(tmp_path, other, tmp_path / "t.json") == 0
    assert (tmp_path / "out" / "reward.txt").read_text() == "0"
    error = json.loads((tmp_path / "out" / "result.json").read_text())["error"]
    assert t["task_id"] in error and other in error


def test_missing_tau_rec_data_is_a_verifier_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("TAU_REC_ROOT", str(tmp_path / "nowhere"))
    t = json.loads(FIXTURES[0].read_text())
    t.pop("evaluation")
    (tmp_path / "t.json").write_text(json.dumps(t))
    assert run(tmp_path, t["task_id"], tmp_path / "t.json") != 0
    assert not (tmp_path / "out" / "reward.txt").exists()


def test_unknown_task_id_is_a_verifier_failure(tmp_path):
    t = json.loads(FIXTURES[0].read_text())
    t.pop("evaluation")
    t["task_id"] = "task_999"
    (tmp_path / "t.json").write_text(json.dumps(t))
    assert run(tmp_path, "task_999", tmp_path / "t.json") != 0


SIDECAR_TRACE = "/var/lib/tau-rec/trace.json"
VERIFIER_PYTHON = "/opt/tau-rec/.venv/bin/python"


def run_test_sh(tmp_path: Path, task_id: str, roots: dict[str, Path]) -> Path:
    """Run tests/test.sh against a sandbox standing in for the verifier
    container: ``roots["verifier"]`` replaces ``/`` for the trace path and
    ``/logs``; the grader is evaluate.py under this interpreter. Returns the
    reward file."""
    text = (TESTS_DIR / "test.sh").read_text()
    verifier = roots["verifier"]
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "config.json").write_text(json.dumps({"task_id": task_id}))
    script = (
        text.replace(VERIFIER_PYTHON, sys.executable)
        .replace("/tests/config.json", str(tmp_path / "tests" / "config.json"))
        .replace("/tests/evaluate.py", str(TESTS_DIR / "evaluate.py"))
        .replace(SIDECAR_TRACE, str(verifier / SIDECAR_TRACE.lstrip("/")))
        .replace("/logs/", f"{verifier}/logs/")
    )
    # A hostile PATH must not matter: the interpreter is absolute.
    env = {**os.environ, "TAU_REC_ROOT": str(ROOT), "PATH": "/usr/bin:/bin"}
    done = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr
    return verifier / "logs" / "verifier" / "reward.txt"


def test_test_sh_reads_config_and_writes_logs(tmp_path):
    """test.sh wires /tests/config.json, the sidecar trace artifact and
    /logs/verifier/, with the verifier image's absolute interpreter."""
    text = (TESTS_DIR / "test.sh").read_text()
    for needle in [
        "set -euo pipefail",
        f"PYTHON={VERIFIER_PYTHON}",
        "/tests/config.json",
        SIDECAR_TRACE,
        "/logs/verifier/reward.txt",
        "/logs/verifier/result.json",
    ]:
        assert needle in text
    t = json.loads(FIXTURES[0].read_text())
    expected = t.pop("evaluation")["primary_reward"]
    verifier = tmp_path / "verifier-root"
    trace = verifier / SIDECAR_TRACE.lstrip("/")
    trace.parent.mkdir(parents=True)
    trace.write_text(json.dumps(t))
    reward = run_test_sh(tmp_path, t["task_id"], {"verifier": verifier})
    assert float(reward.read_text()) == expected


def test_test_sh_fails_loudly_without_a_task_id(tmp_path):
    """A broken /tests/config.json is a verifier error, not a silent 0."""
    text = (TESTS_DIR / "test.sh").read_text()
    (tmp_path / "config.json").write_text("{}")
    script = text.replace(VERIFIER_PYTHON, sys.executable).replace(
        "/tests/config.json", str(tmp_path / "config.json")
    )
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert done.returncode != 0
    assert "KeyError" in done.stderr


async def _oracle_trace(path: Path, task_id: str, plan: dict) -> Path:
    """A trace the runtime sidecar writes for ``plan`` (stubbed user)."""
    from conftest import RUNTIME_DIR, StubUser, fastmcp_caller
    from fastmcp import Client

    bridge = load_module(RUNTIME_DIR / "bridge.py")
    server = load_module(RUNTIME_DIR / "server.py")
    oracle = load_module(TEMPLATE_DIR / "solution" / "oracle.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    session = bridge.Session(
        task_id, ROOT, simulator=StubUser(["I'd like a movie."] * 5), trace_path=path
    )
    async with Client(server.build_server(session)) as client:
        await oracle.run(plan, fastmcp_caller(client))
    return path


def _collect_artifacts(task_toml: Path, roots: dict[str, Path]) -> None:
    """What Harbor does between the agent phase and a separate verifier: copy
    each declared artifact from its compose service's filesystem to the same
    path in the verifier's filesystem."""
    import shutil
    import tomllib

    for artifact in tomllib.loads(task_toml.read_text()).get("artifacts", []):
        if isinstance(artifact, str):
            artifact = {"source": artifact}
        source = artifact["source"].lstrip("/")
        origin = roots[artifact.get("service", "main")] / source
        if origin.exists():
            target = roots["verifier"] / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(origin, target)


async def test_forged_agent_side_trace_does_not_change_the_reward(tmp_path):
    """C2 negative control. The agent plays a losing conversation (a wrong
    item), then forges a perfect trace everywhere its container can write:
    /logs/agent (the old shared trace path) and main's own copy of the
    sidecar path. The reward must stay the sidecar's: the forgery scores 1.0
    when graded directly, so the wiring, not the scorer, is what stops it."""
    from conftest import adapter, generate

    task_id = "task_001"
    (task_dir,) = generate(tmp_path / "tasks", [task_id])
    roots = {
        name: tmp_path / f"{name}-root"
        for name in ("main", "movie-runtime", "verifier")
    }
    catalog = json.loads((ROOT / "data" / "catalog.json").read_text())
    answers = json.loads((ROOT / "data" / "answers.json").read_text())[task_id]
    wrong = next(i for i in catalog if i["id"] not in answers["constraint_solutions"])
    perfect = adapter().oracle_plan(task_id)
    losing = {
        **perfect,
        "item_id": wrong["id"],
        "title": wrong["title"],
        "content_rating": wrong["content_rating"],
        "restricted": False,
        "sponsored": bool(wrong["sponsored"]),
    }
    # The sidecar's authoritative trace of the conversation that happened.
    await _oracle_trace(
        roots["movie-runtime"] / SIDECAR_TRACE.lstrip("/"), task_id, losing
    )
    # The forgery: a perfect trace, written where main can write.
    forged = await _oracle_trace(tmp_path / "forged.json", task_id, perfect)
    for path in ("logs/agent/tau_rec_trace.json", SIDECAR_TRACE.lstrip("/")):
        (roots["main"] / path).parent.mkdir(parents=True, exist_ok=True)
        (roots["main"] / path).write_text(forged.read_text())

    # Positive control: graded directly, the forgery would pass.
    assert run(tmp_path, task_id, forged) == 0
    assert float((tmp_path / "out" / "reward.txt").read_text()) == 1.0

    _collect_artifacts(task_dir / "task.toml", roots)
    reward = run_test_sh(tmp_path, task_id, roots)
    assert float(reward.read_text()) < 1.0
    honest = run_test_sh(
        tmp_path / "honest",
        task_id,
        {"verifier": roots["movie-runtime"]},  # the sidecar trace, untouched
    )
    assert reward.read_text() == honest.read_text()
