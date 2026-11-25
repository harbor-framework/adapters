"""Self-check: trajectory.json records the system prompt the parity agent actually sent.

Run: PYTHONPATH=src/vita-bench uv run --project src/vita-bench python src/vita-bench/scripts/test_atif_system_prompt.py
"""

import json
import tempfile
from pathlib import Path

from vita_llm_agent import SUMMARY_FILENAME, TRAJECTORY_FILENAME, TRANSCRIPT_FILENAME, VitaLLMAgent

with tempfile.TemporaryDirectory() as d:
    logs = Path(d)
    (logs / TRANSCRIPT_FILENAME).write_text(json.dumps([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello ###STOP###"},
    ]))
    (logs / SUMMARY_FILENAME).write_text(json.dumps({
        "model": "x", "termination_reason": "agent_stop",
        "system_prompt": "UPSTREAM POLICY rendered by LLMAgent",
    }))
    # The Harbor task instruction (MCP notes etc.) is NOT what the model received.
    (logs / "vita-llm-agent.instruction.md").write_text("HARBOR INSTRUCTION with MCP notes")

    agent = VitaLLMAgent(logs_dir=logs, model_name="openai/x")
    agent._write_atif_trajectory()
    traj = json.loads((logs / TRAJECTORY_FILENAME).read_text())
    text = json.dumps(traj)
    assert "UPSTREAM POLICY rendered by LLMAgent" in text, "actual system prompt missing"
    assert "HARBOR INSTRUCTION" not in text, "trajectory claims the Harbor instruction was sent"
print("test_atif_system_prompt: OK")
