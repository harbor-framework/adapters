"""Run generated verifier entry points the way Harbor runs them."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from pyarrow import parquet

from contextbench.adapter import CONTEXTBENCH_COMMIT, ContextBenchAdapter
from tests.helpers import (
    LANGUAGE_SAMPLES,
    commit_files,
    git,
    whole_file_gold,
    whole_file_reads,
)

INSTANCE_ID = "owner__repo-1"
# A small public repository the verifier image's source stage can fetch.
IMAGE_SOURCE = ("octocat/Hello-World", "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d")
# A Python checkout, so the oracle's symbol metrics run through a real grammar.
SOURCE = (
    "def unrelated():\n"
    "    return 0\n"
    "\n"
    "\n"
    "def relevant(value):\n"
    "    total = value + 1\n"
    "    return total\n"
)
GOLD_CONTEXT = [{"file": "src/example.py", "start_line": 5, "end_line": 7}]


def _generate_task(
    tmp_path: Path,
    *,
    repository: str,
    commit: str,
    gold_context: list[dict[str, Any]],
    patch: str = "",
) -> Path:
    dataset = tmp_path / "contextbench.parquet"
    row = {
        "instance_id": INSTANCE_ID,
        "original_inst_id": f"{repository.replace('/', '__')}-1",
        "repo_url": f"https://github.com/{repository}",
        "base_commit": commit,
        "language": "python",
        "source": "Verified",
        "problem_statement": "Find the code that needs to change.",
        "gold_context": json.dumps(gold_context),
        "patch": patch,
    }
    parquet.write_table(pa.Table.from_pylist([row]), dataset)
    [task] = ContextBenchAdapter(dataset, tmp_path / "tasks").run(
        task_ids=[INSTANCE_ID]
    )
    return task


def _atif(steps: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "schema_version": "ATIF-v1.7",
            "session_id": "test",
            "agent": {"name": "test", "version": "1"},
            "steps": steps,
        }
    )


def _write_logs(
    logs: Path, steps: list[dict[str, Any]], patch: str = ""
) -> tuple[Path, Path, Path]:
    agent, artifacts, verifier = (
        logs / name for name in ("agent", "artifacts", "verifier")
    )
    for directory in (agent, artifacts, verifier):
        directory.mkdir(parents=True)
    (agent / "trajectory.json").write_text(_atif(steps), encoding="utf-8")
    (artifacts / "contextbench-model.patch").write_text(patch, encoding="utf-8")
    (artifacts / "contextbench-collect-error.txt").write_text("", encoding="utf-8")
    return agent, artifacts, verifier


@pytest.fixture(scope="module")
def oracle_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A verifier root holding a generated task's tests and the oracle's logs.

    test.sh reads /logs, /tests and /workspace under CONTEXTBENCH_VERIFIER_ROOT.
    """
    base = tmp_path_factory.mktemp("verifier")
    root = base / "root"
    workspace = root / "workspace"
    commit = commit_files(workspace, {"src/example.py": SOURCE})
    (workspace / "src/example.py").write_text(
        SOURCE.replace("value + 1", "value + 2"), encoding="utf-8"
    )
    patch = git(workspace, "diff", "--binary", commit, "--", ".")
    git(workspace, "checkout", "--", ".")
    task = _generate_task(
        base,
        repository="owner/repo",
        commit=commit,
        gold_context=GOLD_CONTEXT,
        patch=patch,
    )

    shutil.copytree(task / "tests", root / "tests")
    # The patch is what the collection command records after the oracle runs.
    agent, _, _ = _write_logs(root / "logs", [], patch)
    # solve.sh copies the generated oracle trajectory unchanged.
    shutil.copyfile(task / "solution/oracle-trajectory.json", agent / "trajectory.json")
    return root


def _run_test_sh(root: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "CONTEXTBENCH_VERIFIER_ROOT": str(root),
        "CONTEXTBENCH_TMP_ROOT": str(tmp_path / "worktrees"),
        # test.sh runs `python`, which must have the grammar pack installed.
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
    }
    return subprocess.run(
        ["sh", str(root / "tests/test.sh")],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _remove(root: Path, relative: str) -> None:
    path = root / relative
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _write(root: Path, relative: str, text: str) -> None:
    (root / relative).write_text(text, encoding="utf-8")


def _write_steps(root: Path, steps: list[dict[str, Any]]) -> None:
    _write(root, "logs/agent/trajectory.json", _atif(steps))


def _oracle_steps(root: Path) -> list[dict[str, Any]]:
    trajectory = json.loads((root / "logs/agent/trajectory.json").read_text())
    return trajectory["steps"]


def _call(
    call_id: str, tool: str, arguments: dict[str, Any], content: str
) -> dict[str, Any]:
    return {
        "tool_calls": [
            {"tool_call_id": call_id, "function_name": tool, "arguments": arguments}
        ],
        "observation": {"results": [{"source_call_id": call_id, "content": content}]},
    }


OUTSIDE_STEPS = [
    _call("o1", "Read", {"file_path": "/etc/passwd"}, "root:x:0:0:root:/root:/bin/sh"),
    _call("o2", "Read", {"file_path": "/workspace/../etc/hostname"}, "box"),
    _call("o3", "Bash", {"command": "cat ../../etc/passwd"}, "root:x:0:0::/root:"),
]


def _stale_rewards(root: Path) -> None:
    _write(root, "logs/verifier/reward.txt", "0.123\n")
    _write(root, "logs/verifier/reward.json", '{"reward": 0.123}\n')
    _write(root, "logs/verifier/contextbench-metrics.json", '{"status": "stale"}\n')


def _stale_rewards_without_trajectory(root: Path) -> None:
    _stale_rewards(root)
    _remove(root, "logs/agent/trajectory.json")


def _interrupt_collection(root: Path) -> None:
    """The state a collect step leaves when Harbor's timeout cuts it short."""
    _write(
        root, "logs/artifacts/contextbench-collect-error.txt", "collect_incomplete\n"
    )
    patch = root / "logs/artifacts/contextbench-model.patch"
    partial = patch.read_text(encoding="utf-8")
    patch.with_name(f"{patch.name}.partial").write_text(
        partial[: len(partial) // 2], encoding="utf-8"
    )
    patch.unlink()


def _commit_after_base(root: Path) -> None:
    _write(root, "workspace/extra.py", "EXTRA = 1\n")
    git(root / "workspace", "add", ".")
    git(root / "workspace", "commit", "--quiet", "-m", "after base")


# Verifier inputs and their outcomes, following Harbor's separate verifier
# layout. A failed score exits 1 and leaves no reward file.
EXIT_PATHS: list[tuple[str, Callable[[Path], object], float | None, str]] = [
    ("oracle", lambda root: None, 1.0, "ok"),
    (
        "empty-patch",
        lambda root: _write(root, "logs/artifacts/contextbench-model.patch", ""),
        1.0,
        "ok",
    ),
    (
        "missing-trajectory",
        lambda root: _remove(root, "logs/agent/trajectory.json"),
        None,
        "input_error",
    ),
    (
        "missing-agent-logs",
        lambda root: _remove(root, "logs/agent"),
        None,
        "input_error",
    ),
    (
        "malformed-json",
        lambda root: _write(root, "logs/agent/trajectory.json", '{"steps": ['),
        None,
        "input_error",
    ),
    (
        "array-root",
        lambda root: _write(root, "logs/agent/trajectory.json", "[]"),
        None,
        "input_error",
    ),
    (
        "empty-file",
        lambda root: _write(root, "logs/agent/trajectory.json", ""),
        None,
        "input_error",
    ),
    ("empty-steps", lambda root: _write_steps(root, []), 0.0, "no_context_extracted"),
    (
        "no-steps-key",
        lambda root: _write(
            root, "logs/agent/trajectory.json", '{"schema_version": "ATIF-v1.7"}'
        ),
        None,
        "input_error",
    ),
    (
        "unmapped-calls-only",
        lambda root: _write_steps(
            root,
            [
                _call("u1", "mystery_probe", {"q": "src/example.py"}, "def relevant("),
                _call("u2", "mcp__search__code", {"query": "x"}, "src/example.py:5"),
            ],
        ),
        0.0,
        "no_context_extracted",
    ),
    (
        "patch-for-missing-file",
        lambda root: _write(
            root,
            "logs/artifacts/contextbench-model.patch",
            "diff --git a/missing.py b/missing.py\n--- a/missing.py\n"
            "+++ b/missing.py\n@@ -10,2 +10,2 @@\n-absent\n+replacement\n context\n",
        ),
        1.0,
        "ok",
    ),
    (
        "binary-garbage-patch",
        lambda root: (root / "logs/artifacts/contextbench-model.patch").write_bytes(
            bytes(range(256)) * 256
        ),
        1.0,
        "ok",
    ),
    (
        "outside-paths-only",
        lambda root: _write_steps(root, OUTSIDE_STEPS),
        0.0,
        "no_context_extracted",
    ),
    (
        "outside-paths-and-oracle",
        lambda root: _write_steps(root, OUTSIDE_STEPS + _oracle_steps(root)),
        1.0,
        "ok",
    ),
    (
        "continuation-escape",
        lambda root: _write(
            root,
            "logs/agent/trajectory.json",
            '{"steps": [], "continued_trajectory_ref": "../verifier/x.json"}',
        ),
        None,
        "input_error",
    ),
    (
        "stale-reward-missing-trajectory",
        _stale_rewards_without_trajectory,
        None,
        "input_error",
    ),
    ("stale-reward-oracle", _stale_rewards, 1.0, "ok"),
    (
        "repository-past-base-commit",
        _commit_after_base,
        None,
        "infrastructure_error",
    ),
    (
        "gold-not-an-object",
        lambda root: _write(root, "tests/gold.json", "[]"),
        None,
        "infrastructure_error",
    ),
    (
        "attribution-config-without-roots",
        lambda root: _write(root, "tests/attribution.json", "{}"),
        None,
        "infrastructure_error",
    ),
]


@pytest.mark.parametrize(
    ("mutate", "reward", "status"),
    [pytest.param(*case[1:], id=case[0]) for case in EXIT_PATHS],
)
def test_verifier_exit_paths(
    oracle_root: Path,
    tmp_path: Path,
    mutate: Callable[[Path], object],
    reward: float | None,
    status: str,
) -> None:
    root = tmp_path / "root"
    shutil.copytree(oracle_root, root, symlinks=True)
    mutate(root)

    result = _run_test_sh(root, tmp_path)

    verifier = root / "logs/verifier"
    diagnostics = json.loads((verifier / "contextbench-metrics.json").read_text())
    assert diagnostics["status"] == status, result.stderr
    if reward is None:
        assert result.returncode == 1
        assert not (verifier / "reward.json").exists()
        assert not (verifier / "reward.txt").exists()
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads((verifier / "reward.json").read_text())["reward"] == reward
        assert float((verifier / "reward.txt").read_text()) == reward


def test_an_interrupted_collection_keeps_the_context_score(
    oracle_root: Path, tmp_path: Path
) -> None:
    """test_scoring.py covers each way a collection fails, in process."""
    root = tmp_path / "root"
    shutil.copytree(oracle_root, root, symlinks=True)
    _interrupt_collection(root)

    result = _run_test_sh(root, tmp_path)

    assert result.returncode == 0, result.stderr
    verifier = root / "logs/verifier"
    diagnostics = json.loads((verifier / "contextbench-metrics.json").read_text())
    reward = json.loads((verifier / "reward.json").read_text())
    assert diagnostics["status"] == "ok"
    assert diagnostics["patch_collection"] == {
        "status": "failed",
        "reason": "collect_incomplete",
    }
    assert reward["reward"] == 1.0
    assert reward["contextbench_symbol_coverage"] == 1.0
    assert reward["contextbench_editloc_present"] == 0.0
    assert reward["contextbench_editloc_pred_size"] == 0.0
    assert float((verifier / "reward.txt").read_text()) == 1.0


def test_oracle_scores_symbols_and_edit_location(
    oracle_root: Path, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    shutil.copytree(oracle_root, root, symlinks=True)

    result = _run_test_sh(root, tmp_path)

    assert result.returncode == 0, result.stderr
    reward = json.loads((root / "logs/verifier/reward.json").read_text())
    # tree-sitter finds `relevant` inside the gold lines and the oracle's read.
    assert reward["contextbench_final_symbol_gold_size"] == 1.0
    assert reward["contextbench_symbol_coverage"] == 1.0
    # The oracle patch deletes line 6, inside the gold lines 5-7.
    assert reward["contextbench_editloc_pred_size"] == 1.0
    assert reward["contextbench_editloc_recall"] == 1.0
    diagnostics = json.loads(
        (root / "logs/verifier/contextbench-metrics.json").read_text()
    )
    assert diagnostics["patch_collection"] == {"status": "collected"}


def test_metric_script_aggregates_rewards_and_skips_null_lines(
    oracle_root: Path, tmp_path: Path
) -> None:
    metric = oracle_root.parent / "tasks/metric.py"
    rewards = tmp_path / "rewards.jsonl"
    output = tmp_path / "metrics.json"
    scored = {
        "reward": 0.5,
        "contextbench_final_file_present": 1.0,
        "contextbench_final_file_intersection": 1.0,
        "contextbench_final_file_gold_size": 2.0,
        "contextbench_final_file_pred_size": 4.0,
    }
    no_context = {"reward": 0.0, "contextbench_final_file_present": 0.0}
    rewards.write_text(
        f"{json.dumps(scored)}\n{json.dumps(no_context)}\nnull\n", encoding="utf-8"
    )

    subprocess.run(
        [sys.executable, str(metric), "-i", str(rewards), "-o", str(output)],
        check=True,
    )

    assert json.loads(output.read_text()) == {
        "contextbench_num_total": 3,
        "contextbench_num_valid": 1,
        "contextbench_file_coverage": 0.5,
        "contextbench_file_precision": 0.25,
        "reward": 0.5,
    }


def test_metric_script_rejects_a_reward_that_is_not_an_object(
    oracle_root: Path, tmp_path: Path
) -> None:
    rewards = tmp_path / "rewards.jsonl"
    rewards.write_text("[1.0]\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(oracle_root.parent / "tasks/metric.py"),
            "-i",
            str(rewards),
            "-o",
            str(tmp_path / "metrics.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "reward on line 1 is not an object or null" in result.stderr


@pytest.mark.docker
def test_verifier_image_scores_every_language_without_network(tmp_path: Path) -> None:
    """The image carries every LANG_MAP grammar, so grading needs no network.

    The image's only grammars are in CONTEXTBENCH_TREE_SITTER_CACHE, so an
    offline score that finds a definition in every sample also shows scoring
    reads that cache.
    """
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker is not available")
    source_repository, source_commit = IMAGE_SOURCE
    task = _generate_task(
        tmp_path,
        repository=source_repository,
        commit=source_commit,
        gold_context=[{"file": "README", "start_line": 1, "end_line": 1}],
    )
    image = f"contextbench-verifier-test:{task.name}"
    subprocess.run(
        [docker, "build", "--quiet", "--tag", image, str(task / "tests")],
        check=True,
        capture_output=True,
    )

    workspace = tmp_path / "workspace"
    commit = commit_files(workspace, LANGUAGE_SAMPLES)
    gold = tmp_path / "gold.json"
    gold.write_text(
        json.dumps(
            {
                "instance_id": INSTANCE_ID,
                "base_commit": commit,
                "contextbench_commit": CONTEXTBENCH_COMMIT,
                "gold_context": whole_file_gold(LANGUAGE_SAMPLES),
            }
        ),
        encoding="utf-8",
    )
    agent, artifacts, verifier = _write_logs(
        tmp_path / "logs", whole_file_reads(LANGUAGE_SAMPLES)
    )
    try:
        result = subprocess.run(
            [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                # Run as the owner of the mounted checkout and logs.
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--volume",
                f"{workspace}:/workspace",
                "--volume",
                f"{gold}:/tests/gold.json:ro",
                "--volume",
                f"{agent}:/logs/agent:ro",
                "--volume",
                f"{artifacts}:/logs/artifacts:ro",
                "--volume",
                f"{verifier}:/logs/verifier",
                image,
                "/tests/test.sh",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        subprocess.run(
            [docker, "image", "rm", "--force", image], check=False, capture_output=True
        )

    assert result.returncode == 0, result.stdout + result.stderr
    reward = json.loads((verifier / "reward.json").read_text(encoding="utf-8"))
    assert reward["contextbench_final_symbol_gold_size"] == len(LANGUAGE_SAMPLES)
    assert reward["contextbench_symbol_coverage"] == 1.0
