"""Structural checks on the task template's separate-verifier configuration.

These pin the migration requested in harbor-framework/adapters#14 (review
comment): grading must run in a separate verifier container, the scored
submission must cross over as a declared artifact (while the agent logs use
the conventional /logs/artifacts/ publish dir, since /logs/agent may not be
declared), and the agent allowlist must let the claude-code agent bootstrap
itself.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ADAPTER_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ADAPTER_DIR / "src" / "itbench_aa" / "task-template"


def _load_task_toml() -> dict:
    return tomllib.loads((TEMPLATE_DIR / "task.toml").read_text())


def test_artifacts_declared_at_top_level() -> None:
    # tomllib only surfaces `artifacts` at the root if the key sits before any
    # section header; a misplaced copy would land under the last-open section.
    cfg = _load_task_toml()
    sources = [a["source"] for a in cfg["artifacts"]]
    assert "/workspace/answer.json" in sources
    # /logs/agent is harness-managed: harbor lint REJECTS declaring it
    # (artifact-log-overlap). Agent logs reach the separate verifier through
    # the conventional /logs/artifacts/ publish dir instead, which Harbor
    # collects without a declaration.
    assert "/logs/agent" not in sources
    # The heavy telemetry workspace must NOT be copied into the verifier.
    assert all(s != "/workspace" for s in sources)


def test_verifier_mode_is_separate_with_no_network() -> None:
    cfg = _load_task_toml()
    verifier = cfg["verifier"]
    assert verifier["environment_mode"] == "separate"
    assert verifier["network_mode"] == "no-network"
    # Baseline must equal the phase override (a PUBLIC baseline would rely on
    # dynamic network switching at verify time).
    assert verifier["environment"]["network_mode"] == "no-network"


def test_verifier_image_bakes_tests_dir() -> None:
    dockerfile = (TEMPLATE_DIR / "tests" / "Dockerfile").read_text()
    assert "COPY . /tests/" in dockerfile
    # The grader's only dependency.
    assert "pyyaml" in dockerfile
    # The Dockerfile must not ship inside the image's /tests/.
    assert "rm -f /tests/Dockerfile" in dockerfile
    # Match the agent image's Python minor so grading cannot drift.
    agent_dockerfile = (TEMPLATE_DIR / "environment" / "Dockerfile").read_text()
    assert "python:3.13-slim" in dockerfile
    assert "python:3.13-slim" in agent_dockerfile


def test_agent_allowlist_covers_claude_code_bootstrap() -> None:
    cfg = _load_task_toml()
    hosts = cfg["agent"]["allowed_hosts"]
    assert "downloads.claude.ai" in hosts
    assert "models.dev" in hosts


def test_grade_paths_match_artifact_sources() -> None:
    # The grader reads /workspace/answer.json (a declared artifact) and
    # scans TRANSCRIPT_DIRS for agent transcripts: /logs/agent exists only
    # where the agent log mount reaches (same-container verifier), while
    # /logs/artifacts/agent is where the separate verifier finds the
    # convention-dir-published trajectory. Neither may be a declared
    # artifact source that harbor lint would reject.
    grade_src = (TEMPLATE_DIR / "tests" / "grade.py").read_text()
    assert '"/workspace/answer.json"' in grade_src
    assert '"/logs/agent"' in grade_src
    assert '"/logs/artifacts/agent"' in grade_src
