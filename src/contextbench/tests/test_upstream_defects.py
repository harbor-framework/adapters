"""The scans in scripts/upstream_defects.py that need no network."""

from __future__ import annotations

import pytest

from scripts.upstream_defects import (
    _dotted_path,
    misplaced_statements,
    statement_provenance,
)

# Independent descriptions of four instances, such as SWE-bench Pro's
# requirements and interface.
REFERENCES = {
    "chat": "Endpoint edits chat message content after permission check.",
    "graph": "DirectedGraph class stores nodes, edges; link analysis uses it.",
    "email": "Admin panel shows email validation status; confirmation logic.",
    "uptime": "BSD hosts report uptime seconds from sysctl boot time.",
}
STATEMENTS = {
    # Another instance's statement.
    "chat": "Refactor link analysis into a DirectedGraph class holding nodes plus edges.",
    "graph": "Link analysis needs a DirectedGraph over nodes plus edges.",
    "email": "Email validation status missing from admin panel.",
    "uptime": "Uptime seconds missing on BSD hosts.",
}


def test_statement_provenance_requires_the_stored_statement() -> None:
    rows = {
        "same": {"original_inst_id": "a", "problem_statement": '"Quoted\\ntext"'},
        "other": {"original_inst_id": "b", "problem_statement": "Issue of c."},
        "unknown": {"original_inst_id": "z", "problem_statement": "Issue of z."},
    }

    result = statement_provenance(rows, {"a": '"Quoted\\ntext"', "b": "Issue of b."})

    assert result == {
        "rows": 3,
        "identical": 1,
        "different": ["other"],
        "missing_from_source": ["unknown"],
    }


def test_misplaced_statements_flags_another_instances_statement() -> None:
    [flagged] = misplaced_statements(
        STATEMENTS, REFERENCES, dict.fromkeys(REFERENCES, "owner/repo")
    )

    assert flagged["instance"] == "chat"
    assert flagged["best_match"] == "graph"
    assert flagged["own_similarity"] < flagged["best_similarity"] / 2


def test_misplaced_statements_compares_within_one_repository() -> None:
    repositories = {
        "chat": "owner/app",
        "graph": "owner/graph",
        "email": "owner/app",
        "uptime": "owner/app",
    }

    assert misplaced_statements(STATEMENTS, REFERENCES, repositories) == []


@pytest.mark.parametrize(
    ("path", "dotfile"),
    [
        (".github/workflows/ci.yml", ".github/workflows/ci.yml"),
        ("./.eslintrc.yml", ".eslintrc.yml"),
        ("./src/main.c", None),
        ("src/.hidden/a.py", None),
        # Absolute annotations keep their dot.
        ("/workspace/owner__repo__0.1/.github/ci.yml", None),
        ("/testbed/.github/ci.yml", None),
    ],
)
def test_mangled_gold_paths_are_repository_relative_dotfiles(
    path: str, dotfile: str | None
) -> None:
    assert _dotted_path(path) == dotfile
