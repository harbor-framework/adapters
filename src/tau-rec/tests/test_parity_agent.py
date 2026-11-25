"""The parity agent: tau-Rec's own ``LiteLLMAgent`` driving the runtime over MCP.

No model calls: ``litellm.acompletion`` is replaced by a recorder that returns
scripted model outputs, and the user is a ``StubUser``. The same script runs
through the native ``Orchestrator`` and through ``run_loop`` against a
``Session``; the requests the agent sends and the traces must match.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import types
from pathlib import Path

import litellm
import pytest
from conftest import (
    ADAPTER_DIR,
    TEMPLATE_DIR,
    ROOT,
    RUNTIME_DIR,
    StubUser,
    fastmcp_caller,
    load_module,
    native_setup,
    strip_timings,
)
from fastmcp import Client
from fastmcp.exceptions import ToolError
from tau_rec.agents.litellm_agent import LiteLLMAgent
from tau_rec.data_model.conversation import ConversationTrace
from tau_rec.domain import MOVIES
from tau_rec.orchestrator.orchestrator import Orchestrator

bridge = load_module(RUNTIME_DIR / "bridge.py")
server = load_module(RUNTIME_DIR / "server.py")
runner = load_module(ADAPTER_DIR / "run_tau_rec_parity_agent.py")

TASK = "task_001"
MODEL = "gpt-5-mini"
EFFORT = "low"
COMEDY = "tmdb_803796"  # KPop Demon Hunters: Comedy, Netflix, PG
USER_LINES = [
    "I want a comedy for Friday night with friends.",
    "Something fun and upbeat.",
    "Animated is fine.",
    "Anything recent.",
]


def tool_call(call_id: str, name: str, **arguments) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def reply(content: str | None, *calls: dict, tokens: int = 100):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = list(calls)
    return litellm.ModelResponse(
        model=MODEL,
        choices=[
            {
                "index": 0,
                "finish_reason": "tool_calls" if calls else "stop",
                "message": message,
            }
        ],
        usage={
            "prompt_tokens": tokens,
            "completion_tokens": 7,
            "total_tokens": tokens + 7,
        },
    )


def recommend_script():
    return [
        reply(None, tool_call("c1", "get_user_history", user_id="user_1"), tokens=100),
        # A message with a batch of tool calls: the tools run, the text is dropped.
        reply(
            "Let me look.",
            tool_call("c2", "search_catalog", query="comedy friends"),
            tool_call("c3", "get_metadata", item_id=COMEDY),
            tokens=200,
        ),
        reply("Do you want something animated or live action?", tokens=300),
        # Neither text nor calls: the orchestrator asks again without a user turn.
        reply("", tokens=400),
        reply(
            None,
            tool_call("c4", "check_availability", item_id=COMEDY, services=["Netflix"]),
            tokens=500,
        ),
        reply(
            "I recommend KPop Demon Hunters.",
            tool_call("c5", "recommend", item_id=COMEDY),
            tokens=600,
        ),
    ]


def turn_limit_script():
    return [
        reply("Any genre in mind?", tokens=100),
        reply(
            None, tool_call("c1", "search_catalog", query="animated comedy"), tokens=200
        ),
        reply("Animated or live action?", tokens=300),
        reply("How recent?", tokens=400),
    ]


OVERFLOW = litellm.ContextWindowExceededError(
    message="This model's maximum context length is 128000 tokens.",
    model=MODEL,
    llm_provider="openai",
)
# Not retryable (LiteLLMAgent retries only transient provider errors).
BAD_REQUEST = litellm.BadRequestError(
    message="Invalid schema for function search_catalog.",
    model=MODEL,
    llm_provider="openai",
)


def error_script(error):
    def script():
        return [
            reply(
                None, tool_call("c1", "get_user_history", user_id="user_1"), tokens=100
            ),
            reply("Do you want something animated or live action?", tokens=300),
            error,
        ]

    return script


SCENARIOS = {
    # name: (script, max_turns, stop reason in the trace, label in the summary)
    "recommend": (recommend_script, 20, "recommended", "recommended"),
    "turn_limit": (turn_limit_script, 3, "timeout", "turn_limit"),
    # The model call raises a context overflow: the legacy harness ends the
    # trial with "timeout" and the trace is scored.
    "context_overflow": (error_script(OVERFLOW), 20, "timeout", "context_overflow"),
}


class Recorder:
    """Stands in for ``litellm.acompletion``: records each request, returns the script."""

    def __init__(self, script):
        self.script = list(script)
        self.requests: list[dict] = []

    async def __call__(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        item = self.script[len(self.requests) - 1]
        if isinstance(item, Exception):
            raise item
        return item


async def run_native(monkeypatch, script, max_turns, raises=None):
    recorder = Recorder(script())
    monkeypatch.setattr(litellm, "acompletion", recorder)
    tk, system_prompt, harness = native_setup(TASK)
    # As tau-Rec's cli.py builds a trial.
    agent = LiteLLMAgent(
        model=MODEL,
        system_prompt=system_prompt,
        tool_definitions=tk.tool_definitions(),
        reasoning_effort=EFFORT,
        provider_order=None,
        harness=harness,
    )
    trace = ConversationTrace(task_id=TASK, model=bridge.TRACE_MODEL, trial=0)
    orchestrator = Orchestrator(
        agent=agent,
        simulator=StubUser(USER_LINES),
        toolkit=tk,
        max_turns=max_turns,
        spec=MOVIES,
        trial_timeout_seconds=None,
        harness=harness,
    )
    if raises is None:
        await orchestrator.run(TASK, bridge.TRACE_MODEL, 0, trace=trace)
    else:
        # A native trial that fails: the partial trace is what is left.
        with pytest.raises(raises):
            await orchestrator.run(TASK, bridge.TRACE_MODEL, 0, trace=trace)
    return recorder.requests, trace, agent


async def run_bridged(monkeypatch, tmp_path, script, max_turns, pass_greeting=True):
    recorder = Recorder(script())
    monkeypatch.setattr(litellm, "acompletion", recorder)
    trace_path = tmp_path / "trace.json"
    session = bridge.Session(
        TASK,
        ROOT,
        simulator=StubUser(USER_LINES),
        trace_path=trace_path,
        max_turns=max_turns,
    )
    async with Client(server.build_server(session)) as client:
        call = fastmcp_caller(client)
        agent, setup = await runner.build_agent(call, MODEL, EFFORT)
        if pass_greeting:
            summary = await runner.run_loop(agent, call, greeting=setup["greeting"])
        else:
            summary = await runner.run_loop(agent, call)
    trace = ConversationTrace.model_validate_json(trace_path.read_text())
    return recorder.requests, trace, agent, summary


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
async def test_parity_agent_matches_native(monkeypatch, tmp_path, scenario):
    script, max_turns, stop_reason, label = SCENARIOS[scenario]
    native_requests, native_trace, native_agent = await run_native(
        monkeypatch, script, max_turns
    )
    bridged_requests, bridged_trace, bridged_agent, summary = await run_bridged(
        monkeypatch, tmp_path, script, max_turns, pass_greeting=scenario == "recommend"
    )

    # Every scripted output was used, and each request is the same, call for
    # call: messages, tools, model, reasoning effort, timeout and the rest.
    assert len(native_requests) == len(script())
    assert len(bridged_requests) == len(native_requests)
    for native, bridged in zip(native_requests, bridged_requests):
        assert bridged == native
    assert native_requests[0]["model"] == MODEL
    assert native_requests[0]["reasoning_effort"] == EFFORT
    assert native_requests[0]["tools"]

    assert native_trace.stop_reason.value == stop_reason
    assert strip_timings(bridged_trace) == strip_timings(native_trace)
    assert len(bridged_agent.call_log) == len(native_agent.call_log)

    rows = [r for r in native_agent.call_log if "tokens" in r]
    assert summary["n_input_tokens"] == sum(r["tokens"]["input"] for r in rows)
    assert summary["n_output_tokens"] == 7 * len(rows)
    assert summary["n_cache_tokens"] == 0
    assert summary["cost_usd"] == pytest.approx(
        sum(r["estimated_cost_usd"] for r in rows)
    )
    assert summary["cost_usd"] > 0
    assert summary["metadata"]["stop_reason"] == label
    assert summary["metadata"]["model"] == MODEL
    assert summary["metadata"]["model_calls"] == len(rows)


async def test_agent_error_fails_trial_as_native(monkeypatch, tmp_path):
    """A model error that is not a context overflow: the native orchestrator
    re-raises it, so the bridged trial fails and keeps the same partial trace."""
    script = error_script(BAD_REQUEST)
    _, native_trace, _ = await run_native(
        monkeypatch, script, 20, raises=litellm.BadRequestError
    )
    assert native_trace.stop_reason is None
    with pytest.raises(ToolError, match="trial failed: BadRequestError: "):
        await run_bridged(monkeypatch, tmp_path, script, 20)
    bridged_trace = ConversationTrace.model_validate_json(
        (tmp_path / "trace.json").read_text()
    )
    assert strip_timings(bridged_trace) == strip_timings(native_trace)


async def test_report_agent_error_validation(tmp_path):
    session = bridge.Session(
        TASK, ROOT, simulator=StubUser(USER_LINES), trace_path=tmp_path / "t.json"
    )
    async with Client(server.build_server(session)) as client:
        with pytest.raises(ToolError, match="call start_conversation first"):
            await client.call_tool(
                "report_agent_error", {"error_type": "X", "message": "m"}
            )
        await client.call_tool("start_conversation", {})
        with pytest.raises(ToolError, match="class name"):
            await client.call_tool(
                "report_agent_error", {"error_type": "not a name", "message": "m"}
            )


HTTP_SCENARIOS = {
    # name: (script, native error, exit status, summary stop reason, tokens)
    "recommend": (recommend_script, None, 0, "recommended", 2100),
    "context_overflow": (error_script(OVERFLOW), None, 0, "context_overflow", 400),
    "agent_error": (
        error_script(BAD_REQUEST),
        litellm.BadRequestError,
        1,
        "error",
        400,
    ),
}


@pytest.mark.parametrize("scenario", sorted(HTTP_SCENARIOS))
async def test_runner_main_over_http(monkeypatch, tmp_path, scenario):
    """The shipped path: ``main`` with the ``mcp`` streamable-http client against
    the real server over localhost HTTP sends the native requests, writes the
    summary (with the usage spent so far on failure) and exits 1 only when the
    trial fails."""
    import socket

    script, raises, status, stop_reason, tokens = HTTP_SCENARIOS[scenario]
    native_requests, native_trace, _ = await run_native(
        monkeypatch, script, 20, raises=raises
    )
    recorder = Recorder(script())
    monkeypatch.setattr(litellm, "acompletion", recorder)
    trace_path = tmp_path / "trace.json"
    session = bridge.Session(
        TASK, ROOT, simulator=StubUser(USER_LINES), trace_path=trace_path
    )
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    serving = asyncio.create_task(
        server.build_server(session).run_http_async(
            host="127.0.0.1", port=port, show_banner=False, log_level="error"
        )
    )
    summary_path = tmp_path / "summary.json"
    try:
        for _ in range(100):  # wait for the listener
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
                break
            except OSError:
                await asyncio.sleep(0.1)
        argv = [
            "--model", MODEL, "--reasoning-effort", EFFORT,
            "--mcp-url", f"http://127.0.0.1:{port}/mcp",
            "--summary-path", str(summary_path),
        ]  # fmt: skip
        exit_status = await asyncio.wait_for(
            asyncio.to_thread(runner.main, argv), timeout=120
        )
    finally:
        serving.cancel()
    assert exit_status == status
    assert recorder.requests == native_requests
    trace = ConversationTrace.model_validate_json(trace_path.read_text())
    assert strip_timings(trace) == strip_timings(native_trace)
    summary = json.loads(summary_path.read_text())
    assert summary["metadata"]["stop_reason"] == stop_reason
    assert summary["n_input_tokens"] == tokens
    assert summary["cost_usd"] > 0
    assert len(summary["api_calls"]) == len(native_requests)
    if raises is not None:
        assert "trial failed: BadRequestError" in summary["metadata"]["error"]


def test_summary_without_prices():
    agent = types.SimpleNamespace(
        model="unpriced/model",
        call_log=[
            {"status": "ok", "tokens": {"input": 5, "cached": 2, "cache_write": 0, "output": 1},
             "estimated_cost_usd": None, "provider_reported_cost_usd": None},
            {"status": "error", "error_type": "Timeout"},
        ],
    )  # fmt: skip
    summary = runner.summarize(agent, {"stop_reason": "recommended"})
    assert summary["n_input_tokens"] == 5
    assert summary["n_cache_tokens"] == 2
    assert summary["n_output_tokens"] == 1
    assert summary["cost_usd"] is None
    assert summary["metadata"]["model_calls"] == 1


# -- the Harbor agent class ----------------------------------------------------
#
# Harbor itself is not installed in the adapter's test venv (its dependencies
# are not in the tau-Rec lock), so the class is imported against minimal
# stand-ins for the two Harbor names it uses at runtime.


class _StubInstalledAgent:
    def __init__(self, logs_dir, model_name=None, mcp_servers=None, extra_env=None,
                 version=None, **kwargs):  # fmt: skip
        self.logs_dir = Path(logs_dir)
        self.model_name = model_name
        self.mcp_servers = mcp_servers or []
        self._extra_env = dict(extra_env or {})
        self._version = version
        self.commands: list[tuple[str, str, dict | None]] = []

    def _get_env(self, key):
        import os

        return self._extra_env.get(key) or os.environ.get(key)

    async def exec_as_agent(self, environment, command, env=None, **kwargs):
        self.commands.append(("agent", command, env))

    async def exec_as_root(self, environment, command, env=None, **kwargs):
        self.commands.append(("root", command, env))


class _StubEnvironment:
    def __init__(self):
        self.uploads: list[tuple[Path, str, str]] = []

    async def upload_file(self, source, target):
        self.uploads.append((Path(source), target, Path(source).read_text()))


@pytest.fixture
def agent_module(monkeypatch):
    stubs = {
        "harbor": types.ModuleType("harbor"),
        "harbor.agents": types.ModuleType("harbor.agents"),
        "harbor.agents.capabilities": types.ModuleType("harbor.agents.capabilities"),
        "harbor.agents.installed": types.ModuleType("harbor.agents.installed"),
        "harbor.agents.installed.base": types.ModuleType(
            "harbor.agents.installed.base"
        ),
    }
    stubs["harbor.agents.capabilities"].AgentCapabilities = lambda **kw: kw
    stubs["harbor.agents.installed.base"].BaseInstalledAgent = _StubInstalledAgent
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(sys.modules, "tau_rec_parity_agent", raising=False)
    module = load_module(ADAPTER_DIR / "tau_rec_parity_agent.py")
    yield module
    sys.modules.pop("tau_rec_parity_agent", None)


def _server(**overrides):
    fields = {
        "name": "movie-runtime",
        "transport": "streamable-http",
        "url": "http://movie-runtime:8000/mcp",
    }
    return types.SimpleNamespace(**{**fields, **overrides})


ALL_PROVIDER_KEYS = [
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE",
    "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE",
    "GEMINI_API_KEY", "OPENROUTER_API_KEY",
    "AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION",
    "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_BASE", "AZURE_OPENAI_API_VERSION",
]  # fmt: skip


@pytest.fixture
def host_env(monkeypatch):
    """Every provider key set on the host, plus LiteLLM and unrelated vars."""
    import os

    for key in list(os.environ):
        if key.startswith("LITELLM_"):
            monkeypatch.delenv(key)
    for key in ALL_PROVIDER_KEYS:
        monkeypatch.setenv(key, f"host-{key}")
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    monkeypatch.setenv("LITELLM_LOG", "DEBUG")  # not allow-listed
    monkeypatch.setenv("UNRELATED_SECRET", "x")


def test_parity_agent_class(agent_module, tmp_path, host_env):
    cls = agent_module.TauRecParityAgent
    assert cls.name() == "tau-rec-parity-agent"
    assert cls.capabilities == {"mcp_servers": True, "reasoning_effort": True}
    assert cls.DEFAULT_SETUP_TIMEOUT_SEC >= 600
    agent = cls(
        tmp_path,
        model_name="openrouter/qwen/qwen3-max",
        mcp_servers=[_server()],
        reasoning_effort="high",
    )
    assert agent.version() == "1.0"

    environment = _StubEnvironment()
    asyncio.run(agent.install(environment))
    [(_, constraints_target, constraints), (_, target, text)] = environment.uploads
    assert constraints_target == agent_module.CONSTRAINTS_TARGET_PATH
    assert constraints == (TEMPLATE_DIR / "environment" / "constraints.txt").read_text()
    assert target == agent_module.RUNNER_TARGET_PATH
    assert text == (ADAPTER_DIR / "run_tau_rec_parity_agent.py").read_text()
    [(user, script, env)] = agent.commands
    assert user == "root" and env is None
    assert script == agent_module.INSTALL_SCRIPT
    agent.commands.clear()

    asyncio.run(agent.run("ignored instruction", environment, None))
    [(user, command, env)] = agent.commands
    assert user == "agent"
    assert "/opt/tau-rec/.venv/bin/python" in command
    assert agent_module.RUNNER_TARGET_PATH in command
    assert "--model openrouter/qwen/qwen3-max" in command
    assert "--mcp-url http://movie-runtime:8000/mcp" in command
    assert "--reasoning-effort high" in command
    assert f"--summary-path /logs/agent/{agent_module.SUMMARY_FILENAME}" in command
    # Only the model's provider's key and the allow-listed LiteLLM setting.
    assert env == {
        "OPENROUTER_API_KEY": "host-OPENROUTER_API_KEY",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    }


def test_install_script_pins_tau_rec_like_the_sidecar(agent_module):
    """install() builds the same environment as the runtime sidecar image:
    the v2.1.0 tag, checked against the pinned commit, the locked sync, mcp
    under the shared constraints; then drops everything but the code."""
    script = agent_module.INSTALL_SCRIPT
    sidecar = (TEMPLATE_DIR / "environment/runtime-server/Dockerfile").read_text()
    pin = "8b4c3e6823add74f6c209fff864e2eae6849880c"
    assert script.startswith("set -eu\n")
    for needle in (
        "git clone --depth 1 --branch v2.1.0 https://github.com/nbharaths/tau-rec",
        "uv sync --frozen --project /opt/tau-rec",
        "uv==0.13.8",
    ):
        assert needle in script and needle in sidecar, needle
    assert f'if [ "$head" != {pin} ]' in script and pin in sidecar
    assert "-c /installed-agent/constraints.txt mcp==2.3.0" in script
    assert (
        "find /opt/tau-rec -mindepth 1 -maxdepth 1 ! -name src ! -name .venv" in script
    )


@pytest.mark.parametrize(
    "model, expected",
    [
        ("openai/gpt-5-mini-2025-08-07", ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"]),
        ("gpt-5-mini", ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"]),
        ("anthropic/claude-haiku-5-5", ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE"]),
        ("claude-haiku-5-5", ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE"]),
        ("gemini/gemini-3-pro", ["GEMINI_API_KEY"]),
        ("azure/my-deployment", [k for k in ALL_PROVIDER_KEYS if k.startswith("AZURE")]),
    ],
)  # fmt: skip
def test_runner_env_is_scoped_to_the_model_provider(
    agent_module, tmp_path, host_env, model, expected
):
    agent = agent_module.TauRecParityAgent(
        tmp_path, model_name=model, mcp_servers=[_server()]
    )
    asyncio.run(agent.run("", _StubEnvironment(), None))
    [(_, _, env)] = agent.commands
    assert env == {
        **{key: f"host-{key}" for key in expected},
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    }


def test_runner_env_rejects_an_unknown_provider(agent_module, tmp_path):
    agent = agent_module.TauRecParityAgent(
        tmp_path, model_name="together_ai/some-model", mcp_servers=[_server()]
    )
    with pytest.raises(ValueError, match="together_ai"):
        asyncio.run(agent.run("", _StubEnvironment(), None))


def test_parity_agent_requires_model_and_server(agent_module, tmp_path):
    cls = agent_module.TauRecParityAgent
    with pytest.raises(ValueError, match="model_name"):
        asyncio.run(cls(tmp_path, mcp_servers=[_server()]).run("", None, None))
    for servers, match in [
        ([], "exactly one"),
        ([_server(), _server(name="other")], "exactly one"),
        ([_server(transport="sse")], "streamable-http"),
        ([_server(url=None)], "URL"),
    ]:
        agent = cls(tmp_path, model_name=MODEL, mcp_servers=servers)
        with pytest.raises(ValueError, match=match):
            asyncio.run(agent.run("", None, None))


def test_populate_context_post_run(agent_module, tmp_path):
    agent = agent_module.TauRecParityAgent(tmp_path, model_name=MODEL)
    context = types.SimpleNamespace(
        n_input_tokens=None, n_output_tokens=None, n_cache_tokens=None,
        cost_usd=None, metadata=None,
    )  # fmt: skip
    agent.populate_context_post_run(context)  # no summary yet: left alone
    assert context.n_input_tokens is None
    (tmp_path / agent_module.SUMMARY_FILENAME).write_text(
        json.dumps(
            {
                "n_input_tokens": 2100,
                "n_output_tokens": 42,
                "n_cache_tokens": 0,
                "cost_usd": None,
                "metadata": {
                    "agent": "tau-rec-parity-agent",
                    "stop_reason": "recommended",
                },
                "api_calls": [{"status": "ok"}],
            }
        )
    )
    agent.populate_context_post_run(context)
    assert (
        context.n_input_tokens,
        context.n_output_tokens,
        context.n_cache_tokens,
    ) == (
        2100,
        42,
        0,
    )
    assert context.cost_usd is None
    assert context.metadata == {
        "agent": "tau-rec-parity-agent",
        "stop_reason": "recommended",
    }
