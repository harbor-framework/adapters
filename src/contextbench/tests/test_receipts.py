"""Receipt validation: blank lines, runs, numbered output, diffs, whole-file views."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from contextbench.attribution.trajectory import project_atif
from contextbench.attribution.types import Classification

# Thirty distinct lines; line 13 is blank.
BLANK_AT_13 = "".join(
    "\n" if number == 13 else f"value_{number} = {number}\n" for number in range(1, 31)
)


def _checkout(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8", newline="")
    return root


def _call(
    tool: str, arguments: dict[str, Any], output: str | None, call_id: str
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "tool_calls": [
            {"tool_call_id": call_id, "function_name": tool, "arguments": arguments}
        ]
    }
    if output is not None:
        step["observation"] = {
            "results": [{"source_call_id": call_id, "content": output}]
        }
    return step


def _shell(command: str, output: str, call_id: str = "shell") -> dict[str, Any]:
    return _call("bash", {"command": command}, output, call_id)


def _project(
    root: Path, *steps: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return project_atif({"steps": list(steps)}, root, roots=("/workspace",))


def _lines(text: str, start: int, end: int) -> list[str]:
    return text.split("\n")[start - 1 : end]


def _numbered(text: str, start: int, end: int) -> str:
    return "".join(
        f"{number:6d}\t{line}\n"
        for number, line in enumerate(_lines(text, start, end), start=start)
    )


def _spans(prediction: dict[str, Any], path: str) -> list[tuple[int, int]]:
    return [(span["start"], span["end"]) for span in prediction["pred_spans"][path]]


# --- Blank lines bridge validated lines and are never evidence ---------------


def test_a_blank_line_inside_a_view_joins_one_span_in_every_receipt_shape(
    tmp_path: Path,
) -> None:
    root = _checkout(tmp_path, {"src/blank.py": BLANK_AT_13})
    hunk = "".join(
        " " + line + "\n" if line else "\n" for line in _lines(BLANK_AT_13, 10, 20)
    )
    diff = (
        "diff --git a/src/blank.py b/src/blank.py\n"
        "--- a/src/blank.py\n"
        "+++ b/src/blank.py\n"
        "@@ -10,11 +10,11 @@\n" + hunk
    )
    views = {
        "ranged read": _call(
            "Read",
            {"file_path": "/workspace/src/blank.py", "offset": 10, "limit": 11},
            None,
            "read",
        ),
        "sed -n": _shell(
            "sed -n '10,20p' src/blank.py",
            "\n".join(_lines(BLANK_AT_13, 10, 20)) + "\n",
        ),
        "cat -n": _shell(
            "cat -n src/blank.py | sed -n '10,20p'", _numbered(BLANK_AT_13, 10, 20)
        ),
        # The blank context line is an empty line, its leading space stripped.
        "git diff": _shell("git diff", diff),
    }
    for shape, step in views.items():
        prediction, _ = _project(root, step)

        assert _spans(prediction, "src/blank.py") == [(10, 20)], shape


def test_a_diff_whose_only_base_lines_are_blank_earns_nothing(tmp_path: Path) -> None:
    """Blank lines of a historical commit's diff that match the base earn nothing."""
    root = _checkout(tmp_path, {"src/blank.py": BLANK_AT_13})
    diff = (
        "diff --git a/src/blank.py b/src/blank.py\n"
        "--- a/src/blank.py\n"
        "+++ b/src/blank.py\n"
        "@@ -12,3 +12,3 @@\n"
        "-old_value = 12\n"
        "+new_value = 12\n"
        " \n"
        "-old_value = 14\n"
        "+new_value = 14\n"
    )

    prediction, evidence = _project(root, _shell("git show HEAD~3", diff))

    assert prediction["pred_files"] == []
    assert evidence[0]["classification"] == Classification.NON_BASE_CONTEXT


def test_a_run_padded_with_a_blank_line_is_one_non_blank_line(tmp_path: Path) -> None:
    """A separator line plus a blank line is not a two-line run."""
    root = _checkout(tmp_path, {"doc/notes.rst": "=" * 80 + "\n\nText.\n"})

    prediction, _ = _project(
        root, _shell("cat doc/notes.rst", "=" * 80 + "\n\nOther text.\n")
    )

    assert prediction["pred_files"] == []


# --- Unhinted runs need three non-blank lines --------------------------------

MODULE = "".join(
    f"field_{number} = models.Field({number})\n" for number in range(1, 21)
)


@pytest.mark.parametrize(
    ("command", "output_lines", "credited"),
    [
        # The output names no file: two lines are a chance match.
        ("python generate.py", (4, 5), None),
        ("python generate.py", (4, 6), (4, 6)),
        # A named file, a file under a named directory, or a glob match needs two.
        ("cat app/models.py", (4, 5), (4, 5)),
        ("grep -r -A1 field_4 app", (4, 5), (4, 5)),
        ("find app -name '*.py' | xargs cat | head", (4, 5), (4, 5)),
        ("cat app/*.py", (4, 5), (4, 5)),
        # The working directory is not a hint.
        ("cd app && python generate.py", (4, 5), None),
    ],
)
def test_unhinted_runs_need_three_non_blank_lines(
    tmp_path: Path,
    command: str,
    output_lines: tuple[int, int],
    credited: tuple[int, int] | None,
) -> None:
    root = _checkout(tmp_path, {"app/models.py": MODULE})
    output = "\n".join(_lines(MODULE, *output_lines)) + "\n"

    prediction, _ = _project(root, _shell(command, output))

    if credited is None:
        assert prediction["pred_files"] == []
    else:
        assert _spans(prediction, "app/models.py") == [credited]


def test_path_prefixed_runs_name_their_file_and_need_two_lines(tmp_path: Path) -> None:
    root = _checkout(tmp_path, {"app/models.py": MODULE})
    output = "".join(f"app/models.py-{line}\n" for line in _lines(MODULE, 4, 5))

    prediction, _ = _project(root, _shell("grep -r -A1 field_4", output))

    assert _spans(prediction, "app/models.py") == [(4, 5)]


# --- Numbered output ----------------------------------------------------------


def test_unhinted_numbered_lines_need_two_consecutive_agreeing_lines(
    tmp_path: Path,
) -> None:
    root = _checkout(tmp_path, {"app/models.py": MODULE, "app/other.py": "x = 1\n"})
    single = "4:" + _lines(MODULE, 4, 4)[0] + "\n"
    # Piped grep -n: consecutive in the output, not in line number.
    piped = "".join(
        f"{number}:{_lines(MODULE, number, number)[0]}\n" for number in (4, 9)
    )

    single_prediction, _ = _project(
        root, _shell("git show HEAD:app/x | grep -n field", single)
    )
    piped_prediction, _ = _project(
        root, _shell("git show HEAD:app/x | grep -n field", piped)
    )

    assert single_prediction["pred_files"] == []
    assert _spans(piped_prediction, "app/models.py") == [(4, 4), (9, 9)]


def test_single_file_grep_context_lines_are_numbered_lines(tmp_path: Path) -> None:
    """`grep -n -C` marks context lines `N-` and matches `N:`."""
    root = _checkout(tmp_path, {"app/models.py": MODULE})
    output = "".join(
        f"{number}{':' if number == 5 else '-'}{line}\n"
        for number, line in enumerate(_lines(MODULE, 3, 7), start=3)
    )

    named, _ = _project(root, _shell("grep -n -C2 field_5 app/models.py", output))
    unnamed, _ = _project(root, _shell("python show.py", output))

    assert _spans(named, "app/models.py") == [(3, 7)]
    assert unnamed["pred_files"] == []


def test_grep_context_lines_need_exactly_one_named_file(tmp_path: Path) -> None:
    """With two files named, an `N-` line is not read as a line of either."""
    root = _checkout(tmp_path, {"app/models.py": MODULE, "app/other.py": "x = 1\n"})
    output = "".join(
        f"{number}{':' if number == 5 else '-'}{line}\n"
        for number, line in enumerate(_lines(MODULE, 3, 7), start=3)
    )

    prediction, _ = _project(
        root, _shell("grep -n -C2 field_5 app/models.py app/other.py", output)
    )

    # The `5:` match line still counts on its own in the one file it fits.
    assert prediction["pred_spans"] == {
        "app/models.py": [{"type": "line", "start": 5, "end": 5}]
    }


def test_nested_numbered_grep_output_is_read_by_its_inner_line_numbers(
    tmp_path: Path,
) -> None:
    """`grep -n ... FILE | grep -n ...` numbers the first grep's output lines."""
    root = _checkout(tmp_path, {"app/models.py": MODULE})
    output = f"2:5-{_lines(MODULE, 5, 5)[0]}\n4:7:{_lines(MODULE, 7, 7)[0]}\n"

    prediction, _ = _project(
        root,
        _shell("grep -n -A5 field_4 app/models.py | grep -n 'field_[57]'", output),
    )

    assert _spans(prediction, "app/models.py") == [(5, 5), (7, 7)]


def test_a_single_path_line_content_hit_credits_its_file(tmp_path: Path) -> None:
    root = _checkout(tmp_path, {"app/models.py": MODULE})

    prediction, _ = _project(
        root, _shell("grep -rn field_7 .", "app/models.py:7:" + _lines(MODULE, 7, 7)[0])
    )

    assert _spans(prediction, "app/models.py") == [(7, 7)]


# --- Diffs consume only diff-shaped lines --------------------------------------

A_PY = "".join(
    f"def func_{number}(value):\n    return value + {number}\n" for number in range(15)
)
B_PY = "".join(f"CONSTANT_{number} = {number * 7}\n" for number in range(30))


def _b_diff() -> str:
    return (
        "diff --git a/b.py b/b.py\n"
        "index 1111111..2222222 100644\n"
        "--- a/b.py\n"
        "+++ b/b.py\n"
        "@@ -5,7 +5,7 @@\n"
        + "".join(f" CONSTANT_{n} = {n * 7}\n" for n in range(4, 7))
        + "-CONSTANT_7 = 49\n"
        "+CONSTANT_7 = 0\n"
        + "".join(f" CONSTANT_{n} = {n * 7}\n" for n in range(8, 11))
    )


def test_a_diff_after_other_output_leaves_that_output_to_the_other_receipts(
    tmp_path: Path,
) -> None:
    root = _checkout(tmp_path, {"a.py": A_PY, "b.py": B_PY})

    prediction, _ = _project(root, _shell("cat a.py; git diff", A_PY + _b_diff()))

    assert prediction["pred_files"] == ["a.py", "b.py"]
    # The cat of a.py is a whole-file view; the diff shows lines 5-11 of b.py.
    assert prediction["pred_spans"] == {
        "b.py": [{"type": "line", "start": 5, "end": 11}]
    }


def test_a_two_commit_log_is_read_hunk_by_hunk(tmp_path: Path) -> None:
    root = _checkout(tmp_path, {"a.py": A_PY, "b.py": B_PY})
    log = (
        "commit 3333333333333333333333333333333333333333\n"
        "Author: Someone <someone@example.invalid>\n"
        "Date:   Mon Nov 16 10:00:00 2026 +0000\n"
        "\n"
        "    Change b\n"
        "\n" + _b_diff() + "\n"
        "commit 4444444444444444444444444444444444444444\n"
        "Author: Someone <someone@example.invalid>\n"
        "Date:   Sun Nov 15 10:00:00 2026 +0000\n"
        "\n"
        "    Change a\n"
        "\n"
        "diff --git a/a.py b/a.py\n"
        "--- a/a.py\n"
        "+++ b/a.py\n"
        "@@ -21,3 +21,3 @@\n"
        " def func_10(value):\n"
        "-    return value + 10\n"
        "+    return value - 10\n"
        " def func_11(value):\n"
    )

    prediction, _ = _project(root, _shell("git log -p -2", log))

    assert prediction["pred_spans"] == {
        "a.py": [{"type": "line", "start": 21, "end": 23}],
        "b.py": [{"type": "line", "start": 5, "end": 11}],
    }


def test_a_hunk_line_that_fails_validation_stays_consumed(tmp_path: Path) -> None:
    """Moved code: a historical hunk's lines no longer fit the file it names.

    Read with their diff prefix, the lines are verbatim lines of another file.
    Diff-shaped lines are consumed whether or not they validate, so no other
    receipt credits them as a run of that file.
    """
    moved = "".join(
        f" {line}\n"
        for line in ("def scale(value):", "    factor = 3", "    return value * factor")
    )
    root = _checkout(
        tmp_path,
        {
            "src/old.py": "".join(f"OLD_{number} = {number}\n" for number in range(10)),
            "docs/moved.txt": "Example:\n" + moved + "End.\n",
        },
    )
    diff = (
        "diff --git a/src/old.py b/src/old.py\n"
        "--- a/src/old.py\n"
        "+++ b/src/old.py\n"
        "@@ -4,3 +4,3 @@\n" + moved
    )

    in_hunk, evidence = _project(root, _shell("git show HEAD~5 -- src/old.py", diff))
    outside_a_diff, _ = _project(root, _shell("python show.py", moved))

    assert in_hunk["pred_files"] == []
    assert evidence[0]["classification"] == Classification.NON_BASE_CONTEXT
    assert _spans(outside_a_diff, "docs/moved.txt") == [(2, 4)]


def test_a_dashed_line_in_a_file_does_not_start_a_diff(tmp_path: Path) -> None:
    text = (
        "def parse(text):\n"
        '    """Parse a header block.\n'
        "\n"
        "    The block ends at a rule line:\n"
        "--- end of header\n"
        '    """\n'
        "    rows = text.split()\n"
        "    return rows\n"
        "\n"
        "def other():\n"
        "    return 2\n"
    )
    root = _checkout(tmp_path, {"doc.py": text})

    prediction, _ = _project(
        root, _shell("sed -n '2,8p' doc.py", "\n".join(_lines(text, 2, 8)) + "\n")
    )

    assert _spans(prediction, "doc.py") == [(2, 8)]


def test_a_hunk_is_read_by_its_header_counts(tmp_path: Path) -> None:
    """A line after the counted hunk is not part of it, even if it starts with ' '."""
    root = _checkout(tmp_path, {"b.py": B_PY})
    output = (
        "--- a/b.py\n"
        "+++ b/b.py\n"
        "@@ -5,2 +5,2 @@\n"
        " CONSTANT_4 = 28\n"
        " CONSTANT_5 = 35\n"
        " CONSTANT_6 = 42\n"
    )

    prediction, evidence = _project(root, _shell("git diff -U1 b.py | cat", output))

    assert _spans(prediction, "b.py") == [(5, 6)]
    assert "ignored 1 unattributed line(s)" in evidence[0]["reason"]


# --- Whole-file views credit the file without spans ---------------------------


def test_unranged_read_cat_and_cat_n_of_one_file_project_identically(
    tmp_path: Path,
) -> None:
    root = _checkout(tmp_path, {"src/blank.py": BLANK_AT_13})
    views = [
        _call("Read", {"file_path": "/workspace/src/blank.py"}, None, "read"),
        _shell("cat src/blank.py", BLANK_AT_13),
        _shell("cat -n src/blank.py", _numbered(BLANK_AT_13, 1, 30)),
        _shell("sed -n '1,200p' src/blank.py", BLANK_AT_13),
    ]

    projections = [_project(root, view)[0] for view in views]

    assert projections == [
        {
            "pred_steps": [{"files": ["src/blank.py"], "spans": {}, "symbols": {}}],
            "pred_files": ["src/blank.py"],
            "pred_spans": {},
        }
    ] * len(views)


def test_a_whole_file_view_needs_every_non_blank_line(tmp_path: Path) -> None:
    text = "\nfirst = 1\nsecond = 2\nthird = 3\n\n"
    root = _checkout(tmp_path, {"leading_blank.py": text})

    whole, _ = _project(root, _shell("cat leading_blank.py", text))
    partial, _ = _project(
        root, _shell("head -3 leading_blank.py", "\nfirst = 1\nsecond = 2\n")
    )

    assert whole["pred_files"] == ["leading_blank.py"]
    assert whole["pred_spans"] == {}
    assert _spans(partial, "leading_blank.py") == [(2, 3)]


# --- Lines are counted by newline, as ContextBench counts them -----------------


def test_a_form_feed_does_not_shift_line_numbers(tmp_path: Path) -> None:
    text = "".join(
        "\x0c\n" if number == 10 else f"line_{number} = {number}\n"
        for number in range(1, 31)
    )
    root = _checkout(tmp_path, {"ff.py": text})

    sed, _ = _project(
        root, _shell("sed -n '20,25p' ff.py", "\n".join(_lines(text, 20, 25)) + "\n")
    )
    numbered, _ = _project(
        root, _shell("cat -n ff.py | sed -n '20,25p'", _numbered(text, 20, 25))
    )

    assert _spans(sed, "ff.py") == [(20, 25)]
    assert _spans(numbered, "ff.py") == [(20, 25)]


def test_crlf_line_endings_are_line_endings(tmp_path: Path) -> None:
    text = "".join(f"crlf_{number} = {number}\r\n" for number in range(1, 11))
    root = _checkout(tmp_path, {"crlf.py": text})
    output = "".join(f"crlf_{number} = {number}\r\n" for number in range(3, 6))

    prediction, _ = _project(root, _shell("sed -n '3,5p' crlf.py", output))

    assert _spans(prediction, "crlf.py") == [(3, 5)]


# --- Failure-output filters -----------------------------------------------------

DOCTEST = (
    "def scale(values, factor):\n"
    '    """Scale every value.\n'
    "\n"
    "    >>> scale([1, 2], 3)\n"
    "    [3, 6]\n"
    "    >>> scale([], 3)\n"
    "    []\n"
    '    """\n'
    "    return [value * factor for value in values]\n"
    "\n"
    "\n"
    "def unchanged():\n"
    "    return None\n"
)


def test_doctest_prompts_are_source(tmp_path: Path) -> None:
    root = _checkout(tmp_path, {"dt.py": DOCTEST})

    partial, _ = _project(
        root, _shell("sed -n '1,9p' dt.py", "\n".join(_lines(DOCTEST, 1, 9)) + "\n")
    )
    whole, _ = _project(root, _shell("cat dt.py", DOCTEST))

    assert _spans(partial, "dt.py") == [(1, 9)]
    assert whole["pred_files"] == ["dt.py"]
    assert whole["pred_spans"] == {}


def test_pytest_failure_lines_and_traceback_source_are_not_receipts(
    tmp_path: Path,
) -> None:
    """pytest marks the failing line `>` and the error `E`, both in column 0.

    A Python traceback repeats one source line after each frame. Neither is a
    view of the file.
    """
    root = _checkout(tmp_path, {"app/models.py": MODULE})
    first, second, third = _lines(MODULE, 4, 6)
    pytest_output = (
        f"    def test_fields():\n>       {first}\nE       {second}\n>       {third}\n"
    )
    traceback = (
        "Traceback (most recent call last):\n"
        '  File "app/models.py", line 4, in <module>\n'
        f"{first}\n"
        '  File "app/models.py", line 5, in <module>\n'
        f"{second}\n"
        '  File "app/models.py", line 6, in <module>\n'
        f"{third}\n"
        "RuntimeError: failure\n"
    )

    for output in (pytest_output, traceback):
        prediction, _ = _project(root, _shell("pytest -q", output))

        assert prediction["pred_files"] == [], output
