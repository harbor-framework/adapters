"""Shared helpers for the tau-Rec adapter tests.

Every helper builds on the pinned tau-Rec checkout named by ``TAU_REC_ROOT``.
Tests never call a model: users are ``StubUser`` and agents ``ScriptedAgent``.
"""

from __future__ import annotations

import functools
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

ADAPTER_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(ADAPTER_DIR / "src"))

from tau_rec_adapter import TauRecAdapter  # noqa: E402

TEMPLATE_DIR = ADAPTER_DIR / "src" / "tau_rec_adapter" / "task-template"
RUNTIME_DIR = TEMPLATE_DIR / "environment" / "runtime-server"

if not os.environ.get("TAU_REC_ROOT"):
    pytest.fail(
        "TAU_REC_ROOT is not set: point it at a tau-Rec v2.1.0 checkout, e.g. "
        "TAU_REC_ROOT=$HOME/tau-rec-worktrees/v2.1.0",
        pytrace=False,
    )
ROOT = Path(os.environ["TAU_REC_ROOT"])

from tau_rec.agents.base import AgentResponse, BaseAgent  # noqa: E402
from tau_rec.data_model.conversation import ConversationTrace, Message, Role  # noqa: E402


@functools.cache
def adapter() -> TauRecAdapter:
    """An adapter on the pinned checkout, for reading tasks and oracle plans."""
    return TauRecAdapter(Path("unused-output-dir"), tau_rec_root=ROOT)


def generate(
    output_dir: Path,
    task_ids: list[str] | None = None,
    limit: int | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Generate tasks into ``output_dir`` through the adapter's ``run()``."""
    return TauRecAdapter(
        output_dir,
        limit=limit,
        overwrite=overwrite,
        task_ids=task_ids,
        tau_rec_root=ROOT,
    ).run()


@functools.cache
def _environment():
    from tau_rec.inspect_support.solver import MoviesEnvironment

    return MoviesEnvironment.load(ROOT / "data")


def toolkit(task_id: str):
    """The task's native ToolKit, built as the Inspect solver builds it."""
    return _environment().setup(task_id)[0]


def native_setup(task_id: str):
    """The task's native (ToolKit, agent system prompt, harness profile)."""
    env = _environment()
    return (*env.setup(task_id), env.harness)


def strip_timings(trace: ConversationTrace) -> dict:
    """The trace's model dump with wall-clock timings blanked."""
    data = trace.model_dump(mode="json")
    data["agent_step_latencies_s"] = len(data["agent_step_latencies_s"])
    data["trial_runtime_s"] = None
    return data


def fastmcp_caller(client):
    """``call(name, arguments) -> Observation`` over a FastMCP client."""

    async def call(name: str, arguments: dict) -> dict:
        result = await client.call_tool(name, arguments)
        return json.loads(result.content[0].text)

    return call


class StubUser:
    """A user simulator that replies with scripted lines.

    ``fail_on`` makes the Nth call (1-based) raise, as a provider error would.
    """

    def __init__(self, lines: list[str], fail_on: int | None = None):
        self.lines = list(lines)
        self.fail_on = fail_on
        self.calls = 0

    async def respond(self, conversation: list[Message]) -> Message:
        self.calls += 1
        if self.calls == self.fail_on:
            raise RuntimeError("simulated provider error")
        return Message(role=Role.USER, content=self.lines[self.calls - 1])


class ScriptedAgent(BaseAgent):
    """An agent that returns a fixed sequence of responses."""

    def __init__(self, responses: list[AgentResponse]):
        self.responses = list(responses)
        self.tool_results: list[list[dict] | None] = []

    async def respond(self, tool_results: list[dict] | None = None) -> AgentResponse:
        self.tool_results.append(tool_results)
        return self.responses[len(self.tool_results) - 1]

    def reset(self) -> None:
        self.tool_results = []


def load_module(path: Path) -> ModuleType:
    """Import a template file by path, under its file stem.

    The file's directory goes on ``sys.path`` so sibling imports (``server.py``
    importing ``bridge``) resolve to the same module objects the test uses.
    """
    path = Path(path).resolve()
    name = path.stem
    existing = sys.modules.get(name)
    if (
        existing is not None
        and Path(getattr(existing, "__file__", "")).resolve() == path
    ):
        return existing
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # No __pycache__ inside the task template: the adapter copies it verbatim.
    write_bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = write_bytecode
    return module
