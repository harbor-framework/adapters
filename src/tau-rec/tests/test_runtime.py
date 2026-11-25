"""The runtime sidecar: bridge agent, Session and MCP server. No model calls;
the only network use is a localhost MCP server."""

from __future__ import annotations

import asyncio
import json
import socket

import pytest
from conftest import (
    ROOT,
    RUNTIME_DIR,
    ScriptedAgent,
    StubUser,
    load_module,
    native_setup,
    strip_timings,
    toolkit,
)
from fastmcp import Client
from fastmcp.exceptions import ToolError
from tau_rec.agents.base import AgentResponse
from tau_rec.data_model.conversation import ConversationTrace, Role, ToolCallEvent
from tau_rec.domain import MOVIES
from tau_rec.orchestrator.orchestrator import Orchestrator

bridge = load_module(RUNTIME_DIR / "bridge.py")
server = load_module(RUNTIME_DIR / "server.py")
Session, SessionError = bridge.Session, bridge.SessionError

USER_LINES = [
    "I want a comedy for Friday night with friends.",
    "Something fun and upbeat.",
]
COMEDY = "tmdb_803796"  # KPop Demon Hunters: Comedy, Netflix, PG


def call(name: str, **arguments) -> dict:
    return {"id": f"call_{name}", "name": name, "arguments": arguments}


RESPONSES = [
    AgentResponse(None, [call("get_user_history", user_id="user_1")]),
    AgentResponse(
        None,
        [
            call("search_catalog", query="comedy friends"),
            call("get_metadata", item_id=COMEDY),
        ],
    ),
    AgentResponse("Do you want something animated or live action?"),
    AgentResponse(
        None, [call("check_availability", item_id=COMEDY, services=["Netflix"])]
    ),
    AgentResponse(
        "I recommend KPop Demon Hunters.", [call("recommend", item_id=COMEDY)]
    ),
]


def read_trace(path) -> ConversationTrace:
    return ConversationTrace.model_validate_json(path.read_text())


def session(tmp_path, user=None, **kwargs):
    return Session(
        "task_001",
        ROOT,
        simulator=user or StubUser(USER_LINES),
        trace_path=tmp_path / "t.json",
        **kwargs,
    )


def observation(result) -> dict:
    return json.loads(result.content[0].text)


async def test_replay_equivalence(tmp_path):
    native = await Orchestrator(
        ScriptedAgent(RESPONSES),
        StubUser(USER_LINES),
        toolkit("task_001"),
        max_turns=20,
        spec=MOVIES,
    ).run("task_001", bridge.TRACE_MODEL, 0)
    s = session(tmp_path)
    first = await s.start()
    assert first == {
        "kind": "user_message",
        "content": USER_LINES[0],
        "tool_results": None,
        "ended": False,
        "stop_reason": None,
    }
    observations = [await s.submit(r) for r in RESPONSES]
    bridged = read_trace(tmp_path / "t.json")
    assert strip_timings(bridged) == strip_timings(native)
    assert [o["kind"] for o in observations] == [
        "tool_results",
        "tool_results",
        "user_message",
        "tool_results",
        "ended",
    ]
    assert [r["tool_call_id"] for r in observations[1]["tool_results"]] == [
        "call_search_catalog",
        "call_get_metadata",
    ]
    assert observations[2]["content"] == USER_LINES[1]
    obs = observations[-1]
    assert obs["ended"] and obs["stop_reason"] == "recommended"
    assert obs["tool_results"][0]["tool_call_id"] == "call_recommend"


async def test_tool_listing(tmp_path):
    async with Client(server.build_server(session(tmp_path))) as client:
        tools = {t.name: t for t in await client.list_tools()}
    native = {
        d["function"]["name"]: d["function"]
        for d in toolkit("task_001").tool_definitions()
    }
    assert set(tools) == set(native) | {
        "get_agent_setup",
        "report_agent_error",
        "start_conversation",
        "send_message_to_user",
        "submit_agent_response",
    }
    for name, definition in native.items():
        assert tools[name].input_schema == definition["parameters"]
        assert tools[name].description == definition["description"]


async def test_get_agent_setup(tmp_path):
    """The native agent's prompt, tools, greeting and harness, from the session."""
    tk, system_prompt, harness = native_setup("task_001")
    async with Client(server.build_server(session(tmp_path))) as client:
        setup = observation(await client.call_tool("get_agent_setup", {}))
        # Pure: it does not start the trial.
        await client.call_tool("start_conversation", {})
    assert setup == {
        "system_prompt": system_prompt,
        "tool_definitions": tk.tool_definitions(),
        "greeting": MOVIES.greeting,
        "harness": harness.id,
    }


def test_instruction_names_every_tool():
    text = (RUNTIME_DIR.parents[1] / "instruction.md").read_text()
    for definition in toolkit("task_001").tool_definitions():
        assert f"`{definition['function']['name']}(" in text


async def test_trace_after_every_event(tmp_path):
    s = session(tmp_path)
    await s.start()
    assert len(read_trace(tmp_path / "t.json").events) == len(s.trace.events) == 2
    for r in RESPONSES:
        await s.submit(r)
        assert read_trace(tmp_path / "t.json").events == s.trace.events
    assert read_trace(tmp_path / "t.json") == s.trace
    assert not list(tmp_path.glob("*.tmp"))


async def test_cancel_mid_trial_leaves_trace(tmp_path):
    s = session(tmp_path)
    await s.start()
    for r in RESPONSES[:2]:
        await s.submit(r)
    s.task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await s.task
    saved = read_trace(tmp_path / "t.json")
    assert saved.events == s.trace.events
    assert [e.name for e in saved.events if isinstance(e, ToolCallEvent)] == [
        "get_user_history",
        "search_catalog",
        "get_metadata",
    ]
    assert saved.stop_reason is None
    with pytest.raises(SessionError, match="trial failed"):
        await s.submit(RESPONSES[2])


class GatedUser(StubUser):
    """Holds its second reply until ``gate`` is set."""

    def __init__(self, lines):
        super().__init__(lines)
        self.gate = asyncio.Event()

    async def respond(self, conversation):
        if self.calls == 1:
            await self.gate.wait()
        return await super().respond(conversation)


async def test_cancelled_call_does_not_shift_replies(tmp_path):
    user = GatedUser([*USER_LINES, "Third line."])
    s = session(tmp_path, user=user)
    await s.start()
    pending = asyncio.create_task(s.submit(AgentResponse("First question?")))
    await asyncio.sleep(0.05)  # the simulator is now holding its reply
    pending.cancel()
    user.gate.set()
    obs = await asyncio.wait_for(s.submit(AgentResponse("Second question?")), timeout=5)
    assert obs["content"] == "Third line."


async def test_parallel_calls_serialize(tmp_path):
    s = session(tmp_path)
    ids = ["tmdb_467905", "tmdb_639988", "tmdb_696393"]
    async with Client(server.build_server(s)) as client:
        await client.call_tool("start_conversation", {})
        results = await asyncio.wait_for(
            asyncio.gather(
                *[client.call_tool("get_metadata", {"item_id": i}) for i in ids]
            ),
            timeout=10,
        )
    events = [e for e in s.trace.events if isinstance(e, ToolCallEvent)]
    assert [e.arguments["item_id"] for e in events] == ids
    contents = [observation(r)["tool_results"][0]["content"] for r in results]
    assert contents == [e.result for e in events]
    assert len(set(contents)) == 3
    for item_id, content in zip(ids, contents):
        assert json.loads(content)["id"] == item_id


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def test_parallel_calls_over_http(tmp_path):
    s = session(tmp_path)
    port = free_port()
    serving = asyncio.create_task(
        server.build_server(s).run_http_async(
            transport="streamable-http", host="127.0.0.1", port=port, show_banner=False
        )
    )
    try:
        for _ in range(100):
            try:
                _, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close()
                break
            except OSError:
                await asyncio.sleep(0.05)
        ids = ["tmdb_467905", "tmdb_639988", "tmdb_696393", COMEDY]
        async with Client(f"http://127.0.0.1:{port}/mcp") as client:
            await client.call_tool("start_conversation", {})
            results = await asyncio.wait_for(
                asyncio.gather(
                    *[client.call_tool("get_metadata", {"item_id": i}) for i in ids]
                ),
                timeout=20,
            )
    finally:
        serving.cancel()
        await asyncio.gather(serving, return_exceptions=True)
    events = [e for e in s.trace.events if isinstance(e, ToolCallEvent)]
    # Arrival order over HTTP is not guaranteed: one event per call, matched results.
    assert sorted(e.arguments["item_id"] for e in events) == sorted(ids)
    by_item = {e.arguments["item_id"]: e.result for e in events}
    for item_id, result in zip(ids, results):
        obs = observation(result)
        assert obs["kind"] == "tool_results" and len(obs["tool_results"]) == 1
        content = obs["tool_results"][0]["content"]
        assert content == by_item[item_id]
        assert json.loads(content)["id"] == item_id


async def test_calls_out_of_order(tmp_path):
    s = session(tmp_path)
    async with Client(server.build_server(s)) as client:
        for name, args in [
            ("get_metadata", {"item_id": COMEDY}),
            ("send_message_to_user", {"message": "hi"}),
        ]:
            with pytest.raises(ToolError, match="call start_conversation first"):
                await asyncio.wait_for(client.call_tool(name, args), timeout=5)
        await client.call_tool("start_conversation", {})
        with pytest.raises(ToolError, match="already started"):
            await client.call_tool("start_conversation", {})
        end = observation(await client.call_tool("recommend", {"item_id": COMEDY}))
        assert end["ended"] and end["stop_reason"] == "recommended"
        for name, args in [
            ("send_message_to_user", {"message": "hi"}),
            ("get_metadata", {"item_id": COMEDY}),
            ("start_conversation", {}),
        ]:
            with pytest.raises(ToolError, match="conversation is over: recommended"):
                await asyncio.wait_for(client.call_tool(name, args), timeout=5)


async def test_submit_agent_response_batches(tmp_path):
    s = session(tmp_path)
    async with Client(server.build_server(s)) as client:
        await client.call_tool("start_conversation", {})
        obs = observation(
            await client.call_tool(
                "submit_agent_response",
                {
                    "message": None,
                    "tool_calls": RESPONSES[1].tool_calls,
                },
            )
        )
        assert [r["tool_call_id"] for r in obs["tool_results"]] == [
            "call_search_catalog",
            "call_get_metadata",
        ]
        obs = observation(
            await client.call_tool("send_message_to_user", {"message": "hi"})
        )
        assert obs["kind"] == "user_message" and obs["content"] == USER_LINES[1]


async def test_malformed_tool_calls_are_rejected(tmp_path):
    s = session(tmp_path)
    async with Client(server.build_server(s)) as client:
        await client.call_tool("start_conversation", {})
        for bad in [
            {"name": "get_metadata", "arguments": {"item_id": COMEDY}},
            {"id": "c1", "arguments": {"item_id": COMEDY}},
            {"id": "c1", "name": "get_metadata"},
            {"id": "c1", "name": "get_metadata", "arguments": "{}"},
        ]:
            with pytest.raises(ToolError, match=r"tool_calls\[1\] must be an object"):
                await client.call_tool(
                    "submit_agent_response",
                    {
                        "message": None,
                        "tool_calls": [call("get_user_history", user_id="user_1"), bad],
                    },
                )
        obs = observation(
            await client.call_tool("send_message_to_user", {"message": "hi"})
        )
    assert obs["kind"] == "user_message" and obs["content"] == USER_LINES[1]
    assert not any(isinstance(e, ToolCallEvent) for e in s.trace.events)


@pytest.mark.parametrize(
    "response",
    [RESPONSES[-1], AgentResponse("Any genre in mind?")],
    ids=["after-recommend", "mid-trial"],
)
async def test_trace_write_failure_does_not_hang(tmp_path, response):
    s = session(tmp_path)
    await s.start()

    def broken_write():
        raise OSError("disk full")

    s._write_trace = broken_write  # the end-of-trial (and bridge) writes now fail
    with pytest.raises(SessionError, match="disk full"):
        await asyncio.wait_for(s.submit(response), timeout=5)
    with pytest.raises(SessionError):
        await asyncio.wait_for(s.submit(AgentResponse("hello?")), timeout=5)


async def test_simulator_error_persists_trace(tmp_path):
    s = session(tmp_path, user=StubUser(USER_LINES, fail_on=2))
    await s.start()
    with pytest.raises(SessionError, match="simulated provider error"):
        await asyncio.wait_for(s.submit(AgentResponse("Any genre in mind?")), timeout=5)
    saved = read_trace(tmp_path / "t.json")
    assert [(e.role, e.content) for e in saved.events] == [
        (Role.AGENT, MOVIES.greeting),
        (Role.USER, USER_LINES[0]),
        (Role.AGENT, "Any genre in mind?"),
    ]
    with pytest.raises(SessionError, match="simulated provider error"):
        await s.submit(AgentResponse("hello?"))


async def test_turn_limit_reports_end(tmp_path):
    s = session(tmp_path, max_turns=1)
    async with Client(server.build_server(s)) as client:
        await client.call_tool("start_conversation", {})
        obs = observation(
            await client.call_tool("send_message_to_user", {"message": "Any genre?"})
        )
    assert obs == {
        "kind": "ended",
        "content": USER_LINES[1],
        "tool_results": None,
        "ended": True,
        "stop_reason": "turn_limit",
    }
    # The trace keeps the native legacy-harness record of the same stop.
    assert read_trace(tmp_path / "t.json").stop_reason.value == "timeout"


def test_startup_requires_key(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exit_info:
        server.main()
    assert exit_info.value.code not in (0, None)
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().err


async def test_agent_visible_server_surface_does_not_name_the_benchmark(tmp_path):
    """I2: the MCP server name and every tool description an agent is shown
    (native tools keep their native text) carry no benchmark name."""
    import re

    pattern = re.compile(r"tau[-_ ]?rec|τ", re.IGNORECASE)
    async with Client(server.build_server(session(tmp_path))) as client:
        tools = await client.list_tools()
        server_name = client.server_info.name
    assert server_name == "movie-runtime"
    for tool in tools:
        text = json.dumps([tool.name, tool.description, tool.input_schema])
        assert not pattern.search(text), tool.name


def test_trace_defaults_to_the_sidecar_only_path():
    """C2: the authoritative trace goes to the sidecar's own filesystem, the
    path task.toml collects as an artifact, not to /logs/agent."""
    import inspect

    path = "/var/lib/tau-rec/trace.json"
    assert server.DEFAULT_TRACE_PATH == path
    default = inspect.signature(Session).parameters["trace_path"].default
    assert str(default) == path
    for module in (server, bridge):
        assert "/logs/agent" not in inspect.getsource(module)
