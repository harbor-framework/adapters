"""Structured reads: repository roots, declared ranges, clamping, mutations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from contextbench.adapter import OracleRead, oracle_trajectory
from contextbench.attribution.trajectory import project_atif
from contextbench.attribution.types import Classification

TEN_LINES = "".join(f"line {number}\n" for number in range(1, 11))


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    files = {
        "src/example.py": TEN_LINES,
        "Makefile": "all:\n\techo root\n",
        "lib/Makefile": "all:\n\techo lib\n",
        "package.json": '{"name": "root"}\n',
        "packages/svelte/package.json": '{"name": "svelte"}\n',
        "build/build": "#!/bin/sh\necho build\n",
        "setup.py": "from setuptools import setup\nsetup(name='example')\n",
    }
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    return root


def _read(
    arguments: dict[str, Any],
    content: str | None = None,
    *,
    tool: str = "Read",
    call_id: str = "read",
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "tool_calls": [
            {"tool_call_id": call_id, "function_name": tool, "arguments": arguments}
        ]
    }
    if content is not None:
        step["observation"] = {
            "results": [{"source_call_id": call_id, "content": content}]
        }
    return step


def _project(
    root: Path,
    *steps: dict[str, Any],
    roots: tuple[str, ...] = ("/workspace",),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return project_atif({"steps": list(steps)}, root, roots=roots)


def _spans(prediction: dict[str, Any], path: str) -> list[tuple[int, int]]:
    return [
        (span["start"], span["end"]) for span in prediction["pred_spans"].get(path, [])
    ]


# --- Repository roots -----------------------------------------------------------


def test_the_native_repository_path_is_a_root(checkout: Path) -> None:
    """A read under the native repository path is credited when it is a root."""
    step = _read({"file_path": "/home/cli/src/example.py", "offset": 2, "limit": 2})

    workspace_only, _ = _project(checkout, step)
    with_native, _ = _project(checkout, step, roots=("/workspace", "/home/cli"))

    assert workspace_only["pred_files"] == []
    assert _spans(with_native, "src/example.py") == [(2, 3)]


@pytest.mark.parametrize(
    ("path", "credited"),
    [
        ("/workspace/lib/Makefile", "lib/Makefile"),
        ("/workspace/packages/svelte/package.json", "packages/svelte/package.json"),
        ("/workspace/build/build", "build/build"),
        ("/workspace/nonexistent/Makefile", None),
    ],
)
def test_a_path_under_a_root_resolves_exactly(
    checkout: Path, path: str, credited: str | None
) -> None:
    """A root `Makefile` does not make `/workspace/lib/Makefile` ambiguous."""
    prediction, _ = _project(checkout, _read({"file_path": path}))

    assert prediction["pred_files"] == ([credited] if credited else [])


def test_a_parity_task_resolves_under_its_workspace_and_testbed(checkout: Path) -> None:
    roots = ("/workspace/owner__repo__1.0", "/testbed")
    workspace = _read({"path": "/workspace/owner__repo__1.0/src/example.py"})
    testbed = _read({"path": "/testbed/setup.py"}, call_id="testbed")
    # This path does not exist in the parity container.
    outside = _read({"path": "/workspace/src/example.py"}, call_id="outside")

    prediction, evidence = _project(checkout, workspace, testbed, outside, roots=roots)

    assert prediction["pred_files"] == ["setup.py", "src/example.py"]
    assert [item["classification"] for item in evidence] == [
        Classification.PROJECTED,
        Classification.PROJECTED,
        Classification.NON_BASE_CONTEXT,
    ]


def test_a_path_outside_the_roots_earns_nothing_for_agent_written_content(
    checkout: Path,
) -> None:
    """Stripping `/tmp/` to find the repository's setup.py is only a receipt hint."""
    written = "import setuptools\nsetuptools.setup(name='scratch')\n"
    read = _read({"file_path": "/tmp/setup.py"}, written)
    cat = {
        "tool_calls": [
            {
                "tool_call_id": "cat",
                "function_name": "bash",
                "arguments": {"command": "cat /tmp/setup.py"},
            }
        ],
        "observation": {"results": [{"source_call_id": "cat", "content": written}]},
    }

    prediction, _ = _project(checkout, read, cat)

    assert prediction["pred_files"] == []


def test_a_path_outside_the_roots_is_credited_for_validated_content(
    checkout: Path,
) -> None:
    numbered = "     1\tfrom setuptools import setup\n     2\tsetup(name='example')\n"

    prediction, evidence = _project(
        checkout, _read({"file_path": "/tmp/setup.py"}, numbered)
    )

    assert prediction["pred_files"] == ["setup.py"]
    assert evidence[0]["heuristic"] == "common.observation"


# --- Declared ranges, clamped to the base file ---------------------------------


def test_a_range_ending_past_the_end_is_clamped(checkout: Path) -> None:
    prediction, _ = _project(
        checkout, _read({"file_path": "src/example.py", "offset": 8, "limit": 10})
    )

    assert _spans(prediction, "src/example.py") == [(8, 10)]


def test_a_range_starting_past_the_end_credits_the_file_only(checkout: Path) -> None:
    prediction, evidence = _project(
        checkout, _read({"file_path": "src/example.py", "view_range": [12, 15]})
    )

    assert prediction["pred_files"] == ["src/example.py"]
    assert prediction["pred_spans"] == {}
    assert "past the end of the base file" in evidence[0]["reason"]


def test_the_oracle_keeps_reads_that_end_past_the_end_of_the_file(
    checkout: Path,
) -> None:
    """A gold range one line past the end still earns its file and lines."""
    trajectory = oracle_trajectory(
        "instance", [OracleRead("src/example.py", 9, 11), OracleRead("setup.py", 1, 2)]
    )

    prediction, _ = project_atif(trajectory, checkout, roots=("/workspace",))

    assert prediction["pred_files"] == ["setup.py", "src/example.py"]
    assert _spans(prediction, "src/example.py") == [(9, 10)]


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        # kimi-code and kimi-cli: a 1-based line_offset and a line count.
        ("Read", {"path": "src/example.py", "line_offset": 2, "n_lines": 2}, [(2, 3)]),
        # A negative line_offset reads the tail; its lines are not declared.
        ("Read", {"path": "src/example.py", "line_offset": -3}, []),
        # fx: a 1-based start_line and a line count.
        (
            "read_file",
            {"path": "src/example.py", "start_line": 4, "line_count": 3},
            [(4, 6)],
        ),
        # Gemini CLI: 1-based start_line and end_line.
        (
            "read_file",
            {"file_path": "src/example.py", "start_line": 4, "end_line": 5},
            [(4, 5)],
        ),
        # Qwen Code: a 0-based offset.
        (
            "read_file",
            {"file_path": "src/example.py", "offset": 2, "limit": 3},
            [(3, 5)],
        ),
        (
            "read_file",
            {"file_path": "src/example.py", "offset": 0, "limit": 1},
            [(1, 1)],
        ),
        # Claude Code, Pi and OpenCode: a 1-based offset.
        ("Read", {"file_path": "src/example.py", "offset": 2, "limit": 3}, [(2, 4)]),
        ("read", {"path": "src/example.py", "offset": 2, "limit": 3}, [(2, 4)]),
    ],
)
def test_each_read_schema_counts_lines_from_its_own_base(
    checkout: Path,
    tool: str,
    arguments: dict[str, Any],
    expected: list[tuple[int, int]],
) -> None:
    prediction, _ = _project(checkout, _read(arguments, tool=tool))

    assert prediction["pred_files"] == ["src/example.py"]
    assert _spans(prediction, "src/example.py") == expected


@pytest.mark.parametrize(
    ("producer", "tool", "arguments", "expected"),
    [
        # Mistral Vibe and Cortex Code: a 0-based offset.
        ("vibe", "read_file", {"path": "src/example.py"}, [(2, 3)]),
        ("cortex-code", "read", {"file_path": "src/example.py"}, [(2, 3)]),
        # muse-code and Claude Code share those schemas with a 1-based offset.
        ("muse-code", "read_file", {"path": "src/example.py"}, [(1, 2)]),
        ("claude-code", "read", {"file_path": "src/example.py"}, [(1, 2)]),
    ],
)
def test_the_producer_sets_the_base_of_a_shared_read_schema(
    checkout: Path,
    producer: str,
    tool: str,
    arguments: dict[str, Any],
    expected: list[tuple[int, int]],
) -> None:
    trajectory = {
        "agent": {"name": producer},
        "steps": [_read({**arguments, "offset": 1, "limit": 2}, tool=tool)],
    }

    prediction, _ = project_atif(trajectory, checkout, roots=("/workspace",))

    assert _spans(prediction, "src/example.py") == expected


# --- After a structured mutation, spans come from receipts ----------------------


def test_a_read_after_an_edit_is_credited_from_its_output(checkout: Path) -> None:
    edit = _read(
        {
            "file_path": "/workspace/src/example.py",
            "old_string": "x",
            "new_string": "y",
        },
        "The file has been updated.",
        tool="Edit",
        call_id="edit",
    )
    # The edit inserted a line after line 2, so the read shows lines 3-4 of
    # the base file at the numbers 4-5.
    read = _read(
        {"file_path": "/workspace/src/example.py", "offset": 2, "limit": 4},
        "     2\tline 2\n     3\tinserted\n     4\tline 3\n     5\tline 4\n",
        call_id="read-after-edit",
    )

    prediction, evidence = _project(checkout, edit, read)

    assert prediction["pred_files"] == ["src/example.py"]
    assert _spans(prediction, "src/example.py") == [(2, 2)]
    assert "changed earlier in the trajectory" in evidence[1]["reason"]


def test_a_failed_edit_leaves_declared_ranges_alone(checkout: Path) -> None:
    edit = _read(
        {"command": "str_replace", "path": "/workspace/src/example.py"},
        "No replacement was performed.",
        tool="str_replace_editor",
        call_id="edit",
    )
    edit["observation"]["results"][0]["extra"] = {"is_error": True}
    read = _read(
        {"command": "view", "path": "/workspace/src/example.py", "view_range": [2, 4]},
        call_id="view",
    )

    prediction, _ = _project(checkout, edit, read)

    assert _spans(prediction, "src/example.py") == [(2, 4)]
