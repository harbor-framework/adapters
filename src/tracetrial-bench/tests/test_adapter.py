"""Unit tests for the Harbor TraceTrial-Bench adapter."""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from tracetrial_bench.adapter import TraceTrialBenchAdapter
from tracetrial_bench.atif_bridge import convert_atif_to_tracetrial_events


def _make_synthetic_source(root: Path) -> Path:
    src = root / "tt_repo"
    # Single-turn task
    t1 = src / "Task" / "C1-demo-001"
    (t1 / "workspace" / "input").mkdir(parents=True)
    (t1 / "verifier").mkdir(parents=True)
    (t1 / "task.yaml").write_text(
        """id: C1-demo-001
title: "Demo truncation disclosure task"
input_mode: single_turn
harness:
  dimension: C
  subdimension: C1
intensity:
  level: L2
scenario:
  primary_subscenario: "Truncation disclosure"
budget:
  max_turns: 1
  max_wall_time_sec: 900
""",
        encoding="utf-8",
    )
    (t1 / "prompt.md").write_text("Deliver workspace/output/summary.json.\n", encoding="utf-8")
    (t1 / "workspace" / "input" / "data.txt").write_text("alpha\n", encoding="utf-8")
    (t1 / "verifier" / "secret_gold.txt").write_text("TOP_SECRET_VERIFIER_ONLY", encoding="utf-8")
    (t1 / "verifier" / "score.py").write_text(
        """#!/usr/bin/env python3
import json, os
from pathlib import Path
ws = Path(os.environ["HARNESSBENCH_WORKSPACE"])
ok = (ws / "output" / "summary.json").is_file()
print(json.dumps({
    "schema_version": "harnessbench_rule_results_v1",
    "rule_results": {
        "harness": [{"id": "hr_ok", "passed": ok}],
        "agent": [{"id": "ar_ok", "passed": ok}],
    },
}))
""",
        encoding="utf-8",
    )
    run_sh = t1 / "verifier" / "run.sh"
    run_sh.write_text(
        "#!/bin/sh\nset -eu\nexec python3 \"$(dirname \"$0\")/score.py\"\n",
        encoding="utf-8",
    )
    run_sh.chmod(0o755)

    # Multi-turn task (filtered out in single-turn split)
    t2 = src / "Task" / "L1-multiturn-002"
    (t2 / "workspace").mkdir(parents=True)
    (t2 / "verifier").mkdir(parents=True)
    (t2 / "task.yaml").write_text(
        "id: L1-multiturn-002\ninput_mode: fixed_turns\nharness:\n  dimension: L\n  subdimension: L1\n",
        encoding="utf-8",
    )
    (t2 / "prompt.md").write_text("Turn 1 prompt.\n", encoding="utf-8")
    return src


def test_split_filtering_and_generation_isolation(tmp_path: Path) -> None:
    src = _make_synthetic_source(tmp_path)
    out = tmp_path / "out"

    adapter_st = TraceTrialBenchAdapter(out, source_dir=src, split="single-turn")
    assert adapter_st.list_available_tasks() == ["C1-demo-001"]

    adapter_all = TraceTrialBenchAdapter(out, source_dir=src, split="all")
    assert adapter_all.list_available_tasks() == ["C1-demo-001", "L1-multiturn-002"]

    written = adapter_st.run(overwrite=True)
    assert len(written) == 1
    task_dir = out / "c1-demo-001"
    assert (task_dir / "instruction.md").read_text(encoding="utf-8") == "Deliver workspace/output/summary.json.\n"

    # Verify task.toml is valid TOML and has registry-compliant name + authors
    cfg = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
    assert cfg["task"]["name"] == "tracelite-ai/tracetrial-bench__c1-demo-001"
    assert cfg["metadata"]["dimension"] == "C"
    assert cfg["verifier"]["environment_mode"] == "separate"
    assert cfg["artifacts"] == ["/workspace"]
    assert (task_dir / "tests" / "Dockerfile").is_file()

    # Verify strict isolation: workspace has input/data.txt, NEVER verifier files
    assert (task_dir / "environment" / "workspace" / "input" / "data.txt").is_file()
    assert not (task_dir / "environment" / "verifier").exists()
    assert not list((task_dir / "environment").rglob("secret_gold.txt"))
    assert (task_dir / "tests" / "verifier" / "secret_gold.txt").is_file()


def test_atif_bridge_and_end_to_end_verify_reward(tmp_path: Path) -> None:
    src = _make_synthetic_source(tmp_path)
    out = tmp_path / "out"
    TraceTrialBenchAdapter(out, source_dir=src).run(overwrite=True)
    task_dir = out / "c1-demo-001"

    logs_agent = tmp_path / "logs" / "agent"
    logs_verifier = tmp_path / "logs" / "verifier"
    logs_agent.mkdir(parents=True)
    logs_verifier.mkdir(parents=True)

    atif = {
        "schema_version": "ATIF-v1.2",
        "steps": [
            {
                "step_id": 1,
                "source": "agent",
                "message": "Inspecting input and writing summary.",
                "tool_calls": [
                    {
                        "tool_call_id": "call-1",
                        "function_name": "bash",
                        "arguments": {"command": "cat input/data.txt"},
                    }
                ],
                "observation": {
                    "results": [{"source_call_id": "call-1", "content": "alpha\n"}]
                },
            }
        ],
    }
    atif_path = logs_agent / "trajectory.json"
    atif_path.write_text(json.dumps(atif), encoding="utf-8")

    events = convert_atif_to_tracetrial_events(atif_path)
    assert [e["event_type"] for e in events] == ["run_started", "assistant_message", "tool", "run_finished"]
    assert events[2]["tool_call"]["arguments"]["command"] == "cat input/data.txt"
    assert events[2]["tool_result"]["content"] == "alpha\n"

    ws = task_dir / "environment" / "workspace"
    env = dict(os.environ)
    env["HARNESSBENCH_WORKSPACE"] = str(ws)
    env["HARBOR_AGENT_LOG_DIR"] = str(logs_agent)
    env["HARBOR_VERIFIER_LOG_DIR"] = str(logs_verifier)

    # Missing output/summary.json -> reward 0.0
    subprocess.run(["python3", str(task_dir / "tests" / "verify.py")], env=env, check=True)
    assert float((logs_verifier / "reward.txt").read_text().strip()) == pytest.approx(0.0)

    # Deliver output/summary.json -> reward 1.0
    (ws / "output").mkdir(parents=True, exist_ok=True)
    (ws / "output" / "summary.json").write_text("{\"ok\": true}\n", encoding="utf-8")
    subprocess.run(["python3", str(task_dir / "tests" / "verify.py")], env=env, check=True)
    assert float((logs_verifier / "reward.txt").read_text().strip()) == pytest.approx(1.0)
