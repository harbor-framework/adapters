from __future__ import annotations

import shlex
import tomllib
from pathlib import Path

import pytest

import adapter
import utils
from utils import get_test_commands

# Repos whose SWE-Gym images ship pytest-xdist; only these may receive -n0.
XDIST_REPOS = {
    "conan-io/conan",
    "dask/dask",
    "getmoto/moto",
    "modin-project/modin",
    "python/mypy",
    "bokeh/bokeh",
}
NON_XDIST_REPOS = {
    "pydantic/pydantic",
    "facebookresearch/hydra",
    "pandas-dev/pandas",
    "iterative/dvc",
    "Project-MONAI/MONAI",
}


def run_tests(repo: str, fail_to_pass: list[str], pass_to_pass: list[str]) -> list[str]:
    """Return the argv of the unbatched pytest command in the generated script."""
    script = get_test_commands("", repo, "1.0", "deadbeef", fail_to_pass, pass_to_pass)
    pytest_lines = [
        line.strip() for line in script.splitlines() if line.strip().startswith("pytest ")
    ]
    (batched,) = [line for line in pytest_lines if "${BATCH[@]}" in line]
    (unbatched,) = [line for line in pytest_lines if "${BATCH[@]}" not in line]
    # Both branches of the script must use the same pytest flags.
    assert batched.split('"${BATCH[@]}"')[0].strip() in unbatched
    return shlex.split(unbatched)


@pytest.mark.parametrize("repo", sorted(XDIST_REPOS | NON_XDIST_REPOS))
def test_pytest_reports_every_result(repo: str) -> None:
    # Without -rA pytest prints no per-test PASSED lines and the grader scores 0
    # (harbor-framework/adapters#12).
    argv = run_tests(repo, ["tests/test_a.py::test_fixed"], [])
    assert "-rA" in argv
    assert ("-n0" in argv) == (repo in XDIST_REPOS)


def test_unknown_repo_gets_default_flags() -> None:
    argv = run_tests("example/unknown", ["tests/test_a.py::test_fixed"], [])
    assert argv[:6] == ["pytest", "-rA", "-p", "no:pretty", "--color=no", "tests/test_a.py::test_fixed"]


def test_flaky_tests_are_dropped_from_pass_to_pass_only() -> None:
    flaky = "tests/test_generics.py::test_circular_generic_refs_get_cleaned_up"

    argv = run_tests("pydantic/pydantic", ["tests/test_a.py::test_fixed"], [flaky])
    assert flaky not in argv

    argv = run_tests("pydantic/pydantic", [flaky], [])
    assert flaky in argv


def test_modin_runs_only_fail_to_pass() -> None:
    argv = run_tests(
        "modin-project/modin",
        ["modin/tests/test_a.py::test_fixed"],
        ["modin/tests/test_a.py::test_other"],
    )
    assert "modin/tests/test_a.py::test_fixed" in argv
    assert "modin/tests/test_a.py::test_other" not in argv


@pytest.mark.parametrize(
    "node_id",
    [
        "tests/test_a.py::test_x[truncated",
        "tests/test_a.py::test_x[café]",
        "tests/test_a.py::test_x[\\]",
        "tests/test_a.py::test_x[\x12]",
    ],
)
def test_problematic_fail_to_pass_runs_whole_file(node_id: str) -> None:
    assert utils._is_problematic(node_id)
    argv = run_tests("dask/dask", [node_id], ["tests/test_b.py::test_ok"])
    assert "tests/test_a.py" in argv
    assert "tests/test_b.py::test_ok" in argv


def test_clean_node_id_is_not_problematic() -> None:
    assert not utils._is_problematic("tests/test_a.py::test_x[1-2]")


@pytest.mark.parametrize(
    ("instance_id", "repo", "verifier_timeout"),
    [
        ("Project-MONAI__MONAI-1121", "Project-MONAI/MONAI", 30000),
        ("modin-project__modin-5940", "modin-project/modin", 24000),
        ("getmoto__moto-4799", "getmoto/moto", 6000),
    ],
)
def test_task_config_name_and_verifier_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    instance_id: str,
    repo: str,
    verifier_timeout: int,
) -> None:
    record = {
        "instance_id": instance_id,
        "repo": repo,
        "version": "1.0",
        "base_commit": "deadbeef",
        "problem_statement": "Fix the failing test.",
        "difficulty": "hard",
        "patch": "",
        "test_patch": "",
        "FAIL_TO_PASS": ["tests/test_a.py::test_fixed"],
        "PASS_TO_PASS": [],
    }
    monkeypatch.setattr(adapter, "load_dataset", lambda name: {"train": [record]})
    converter = adapter.SWEGymToHarbor(harbor_tasks_root=tmp_path)

    task_dir = converter.generate_task(instance_id, instance_id)

    config = tomllib.loads((task_dir / "task.toml").read_text())
    assert config["task"]["name"] == f"swe-gym/{instance_id.lower()}"
    assert config["verifier"]["timeout_sec"] == verifier_timeout
    assert config["agent"]["timeout_sec"] == 3000
