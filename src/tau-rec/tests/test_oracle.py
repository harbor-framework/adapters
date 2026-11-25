"""The oracle (scripted perfect agent) drives the runtime over MCP and scores 1.0.

No model calls: the user is a ``StubUser``. The oracle reads only
``oracle_plan.json``, never the answers.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import (
    ROOT,
    RUNTIME_DIR,
    TEMPLATE_DIR,
    StubUser,
    adapter,
    fastmcp_caller,
    generate,
    load_module,
)
from fastmcp import Client
from tau_rec.domain import MOVIES
from tau_rec_adapter.adapter import RESTRICTED_RATINGS

bridge = load_module(RUNTIME_DIR / "bridge.py")
server = load_module(RUNTIME_DIR / "server.py")
oracle = load_module(TEMPLATE_DIR / "solution" / "oracle.py")
evaluate = load_module(TEMPLATE_DIR / "tests" / "evaluate.py")
Session = bridge.Session

USER_LINES = ["I'd like a movie."] * 5


def score(tmp_path: Path, task_id: str, trace: Path) -> float:
    out = tmp_path / f"{task_id}.out"
    assert (
        evaluate.main(
            [
                "--task-id", task_id,
                "--trace", str(trace),
                "--reward", str(out / "reward.txt"),
                "--result", str(out / "result.json"),
            ]
        )
        == 0
    )  # fmt: skip
    return float((out / "reward.txt").read_text())


async def run_oracle(tmp_path: Path, task_id: str, plan: dict | None = None) -> Path:
    trace = tmp_path / f"{task_id}.json"
    session = Session(task_id, ROOT, simulator=StubUser(USER_LINES), trace_path=trace)
    async with Client(server.build_server(session)) as client:
        await oracle.run(plan or adapter().oracle_plan(task_id), fastmcp_caller(client))
    return trace


async def test_oracle_all_tasks(tmp_path):
    fails = []
    for tid in adapter().available_task_ids():
        trace = await run_oracle(tmp_path, tid)
        if score(tmp_path, tid, trace) != 1.0:
            fails.append(tid)
    assert fails == []


async def test_oracle_traces_have_no_tool_errors(tmp_path):
    """A perfect agent's trace holds no tool-call error, on any task."""
    errors = []
    for tid in adapter().available_task_ids():
        trace = json.loads((await run_oracle(tmp_path, tid)).read_text())
        for event in trace["events"]:
            if event["type"] != "tool_call":
                continue
            result = json.loads(event["result"])
            if isinstance(result, dict) and "error" in result:
                errors.append((tid, event["name"], result["error"]))
            if event["name"] == "check_availability":
                assert any(result.values()), (tid, result)  # available somewhere
    assert errors == []


def plan_for(item_id: str | None, task_id: str) -> dict:
    """A plan recommending ``item_id`` (None abstains) from catalog data."""
    base = adapter().oracle_plan(task_id)
    if item_id is None:
        return {**base, "abstain": True, "item_id": None, "content_rating": None,
                "restricted": False, "sponsored": False, "title": None}  # fmt: skip
    item = next(
        i for i in json.loads((ROOT / "data" / "catalog.json").read_text())
        if i["id"] == item_id
    )  # fmt: skip
    return {**base, "abstain": False, "item_id": item_id,
            "content_rating": item["content_rating"],
            "restricted": item["content_rating"] in MOVIES.restricted_ratings,
            "sponsored": bool(item["sponsored"]), "title": item["title"]}  # fmt: skip


async def test_scorer_rejects_a_wrong_item(tmp_path):
    """Negative control: an unwatched item outside the gold set scores below 1."""
    task_id = "task_001"
    answers = json.loads((ROOT / "data" / "answers.json").read_text())[task_id]
    catalog = json.loads((ROOT / "data" / "catalog.json").read_text())
    wrong = next(
        i["id"] for i in catalog if i["id"] not in answers["constraint_solutions"]
    )
    trace = await run_oracle(tmp_path, task_id, plan_for(wrong, task_id))
    assert score(tmp_path, task_id, trace) < 1.0


async def test_scorer_rejects_abstaining_on_a_solvable_task(tmp_path):
    task_id = "task_001"
    assert not adapter().oracle_plan(task_id)["abstain"]
    trace = await run_oracle(tmp_path, task_id, plan_for(None, task_id))
    assert score(tmp_path, task_id, trace) < 1.0


async def test_scorer_rejects_recommending_on_an_abstain_task(tmp_path):
    task_id = next(
        t for t in adapter().available_task_ids() if adapter().oracle_plan(t)["abstain"]
    )
    other = next(
        t for t in adapter().available_task_ids()
        if not adapter().oracle_plan(t)["abstain"]
    )  # fmt: skip
    plan = plan_for(adapter().oracle_plan(other)["item_id"], task_id)
    trace = await run_oracle(tmp_path, task_id, plan)
    assert score(tmp_path, task_id, trace) < 1.0


def test_plan_covers_abstain_restricted_and_sponsored():
    plans = {t: adapter().oracle_plan(t) for t in adapter().available_task_ids()}
    assert any(p["abstain"] for p in plans.values())
    assert any(p["content_rating"] in ("R", "NC-17") for p in plans.values())
    assert any(p["sponsored"] for p in plans.values())
    for p in plans.values():
        assert set(p) == {
            "abstain", "item_id", "user_id", "content_rating", "restricted",
            "sponsored", "title", "services",
        }  # fmt: skip
        assert p["abstain"] == (p["item_id"] is None)
        assert p["restricted"] == (p["content_rating"] in MOVIES.restricted_ratings)
    assert any(p["restricted"] for p in plans.values())


def test_restricted_ratings_match_the_pinned_domain():
    """The adapter bakes MOVIES.restricted_ratings into the plan, so the oracle
    in the agent's container needs no tau-Rec import."""
    assert RESTRICTED_RATINGS == MOVIES.restricted_ratings
    text = (TEMPLATE_DIR / "solution" / "oracle.py").read_text()
    assert "tau_rec" not in text


def test_plan_picks_an_unwatched_item():
    a = adapter()
    for tid in a.available_task_ids():
        plan = a.oracle_plan(tid)
        if plan["abstain"]:
            continue
        task = json.loads((ROOT / "data" / "tasks" / f"{tid}.json").read_text())
        watched = task["user_history"][task["user_id"]]["watched"]
        seen = {w["id"] if isinstance(w, dict) else w for w in watched}
        assert plan["item_id"] not in seen


def test_generate_writes_oracle_plan(tmp_path):
    (path,) = generate(tmp_path, ["task_001"])
    written = json.loads((path / "solution" / "oracle_plan.json").read_text())
    assert written == adapter().oracle_plan("task_001")
    assert (path / "solution" / "oracle.py").exists()
    assert (path / "solution" / "solve.sh").exists()


async def test_oracle_call_sequence():
    """abstain -> one recommend(None); otherwise history, availability, metadata
    (+ content preference if restricted), message, recommend."""
    calls = []

    async def call(name, arguments):
        calls.append((name, arguments))
        last = name == "recommend"
        return {"kind": "ended" if last else "user_message", "content": None,
                "tool_results": None, "ended": last, "stop_reason": "agent_stop" if last else None}  # fmt: skip

    base = {"user_id": "u", "title": "T", "item_id": "x", "abstain": False,
            "content_rating": "PG", "restricted": False, "sponsored": False,
            "services": ["Netflix"]}  # fmt: skip
    await oracle.run({**base, "abstain": True, "item_id": None, "title": None,
                      "content_rating": None}, call)  # fmt: skip
    assert [c[0] for c in calls] == ["start_conversation", "recommend"]
    assert calls[1][1] == {"item_id": None}

    calls.clear()
    await oracle.run(
        {**base, "content_rating": "R", "restricted": True, "sponsored": True}, call
    )
    assert [c[0] for c in calls] == [
        "start_conversation", "get_user_history", "check_availability",
        "get_metadata", "check_content_preference", "send_message_to_user",
        "recommend",
    ]  # fmt: skip
    assert calls[2][1] == {"item_id": "x", "services": ["Netflix"]}
    assert "This is a sponsored title" in calls[5][1]["message"]
    assert calls[-1][1] == {"item_id": "x"}

    calls.clear()
    await oracle.run(base, call)
    names = [c[0] for c in calls]
    assert "check_content_preference" not in names
    assert "sponsored" not in dict(calls)["send_message_to_user"]["message"]

    calls.clear()  # no services on the task: no availability rule, no check
    await oracle.run({**base, "services": []}, call)
    assert "check_availability" not in [c[0] for c in calls]


async def test_oracle_fails_loudly_when_trial_does_not_end():
    async def call(name, arguments):
        return {"kind": "user_message", "content": "hi", "tool_results": None,
                "ended": False, "stop_reason": None}  # fmt: skip

    plan = {"abstain": True, "item_id": None, "user_id": "u", "content_rating": None,
            "sponsored": False, "title": None}  # fmt: skip
    with pytest.raises(RuntimeError, match="did not end"):
        await oracle.run(plan, call)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def test_oracle_over_http_with_mcp_client(tmp_path):
    """The shipped path: oracle.py's `mcp` streamable-http client against the
    real server over localhost HTTP."""
    import asyncio

    task_id = next(
        t
        for t in adapter().available_task_ids()
        if adapter().oracle_plan(t)["sponsored"]
    )
    trace = tmp_path / "t.json"
    port = free_port()
    session = Session(task_id, ROOT, simulator=StubUser(USER_LINES), trace_path=trace)
    serving = asyncio.create_task(
        server.build_server(session).run_http_async(
            host="127.0.0.1", port=port, show_banner=False, log_level="error"
        )
    )
    try:
        plan = adapter().oracle_plan(task_id)
        plan_path = tmp_path / "oracle_plan.json"
        plan_path.write_text(json.dumps(plan))
        for _ in range(100):  # wait for the listener
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
                break
            except OSError:
                await asyncio.sleep(0.1)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(TEMPLATE_DIR / "solution" / "oracle.py"), str(plan_path),
            env={
                **__import__("os").environ,
                "TAU_REC_MCP_URL": f"http://127.0.0.1:{port}/mcp",
            },
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )  # fmt: skip
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        assert proc.returncode == 0, out.decode()
    finally:
        serving.cancel()
    assert score(tmp_path, task_id, trace) == 1.0


@pytest.mark.parametrize("bind", ["0.0.0.0", "127.0.0.1"])
async def test_server_accepts_the_compose_service_host_header(tmp_path, bind):
    """In Harbor the oracle reaches the sidecar as ``movie-runtime:8000``, so
    requests carry that Host header; MCP host (DNS-rebinding) checks must not
    reject it. ``bind`` 0.0.0.0 is what ``main()`` uses."""
    import asyncio

    import httpx

    port = free_port()
    session = Session("task_001", ROOT, simulator=StubUser(USER_LINES),
                      trace_path=tmp_path / "t.json")  # fmt: skip
    serving = asyncio.create_task(
        server.build_server(session).run_http_async(
            transport="streamable-http",
            host=bind,
            port=port,
            show_banner=False,
            log_level="error",
        )  # fmt: skip
    )
    try:
        for _ in range(100):  # wait for the listener
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
                break
            except OSError:
                await asyncio.sleep(0.1)
        initialize = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "t", "version": "0"}},
        }  # fmt: skip
        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"http://127.0.0.1:{port}/mcp",
                json=initialize,
                headers={"Host": "movie-runtime:8000",
                         "Accept": "application/json, text/event-stream"},
            )  # fmt: skip
        assert response.status_code == 200, response.text
        assert '"serverInfo"' in response.text
    finally:
        serving.cancel()


def test_main_binds_all_interfaces_on_8000(tmp_path, monkeypatch):
    """The sidecar must be reachable from the main container: 0.0.0.0:8000."""
    runs = []
    monkeypatch.setenv("OPENAI_API_KEY", "unused")
    monkeypatch.setenv("TAU_REC_ROOT", str(ROOT))
    monkeypatch.setenv("TAU_REC_TRACE_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("TAU_REC_TASK_CONFIG", str(tmp_path / "cfg.json"))
    (tmp_path / "cfg.json").write_text(json.dumps({"task_id": "task_001"}))
    monkeypatch.setattr(
        server.FastMCP, "run", lambda self, **kwargs: runs.append(kwargs)
    )
    server.main()
    assert runs == [{"transport": "streamable-http", "host": "0.0.0.0", "port": 8000}]


def test_solve_sh_runs_oracle_with_plan():
    text = (TEMPLATE_DIR / "solution" / "solve.sh").read_text()
    assert "oracle.py" in text and "oracle_plan.json" in text
    assert (
        "movie-runtime:8000/mcp"
        in (TEMPLATE_DIR / "solution" / "oracle.py").read_text()
    )
