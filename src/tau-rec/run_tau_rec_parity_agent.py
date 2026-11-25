"""Parity agent runner: tau-Rec's own ``LiteLLMAgent`` against the runtime sidecar.

Runs in Harbor's ``main`` container with the Python of the pinned tau-Rec
checkout that ``TauRecParityAgent.install`` sets up (``/opt/tau-rec/.venv``). The agent is built from ``get_agent_setup`` (the
sidecar session's own system prompt, tool definitions and harness profile), and
``run_loop`` feeds it exactly what the native ``Orchestrator`` feeds a
``LiteLLMAgent``, so every model request matches a native ``tau-rec run``.

Usage: python run_tau_rec_parity_agent.py --model MODEL [--reasoning-effort E]
       [--mcp-url URL] [--summary-path PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import traceback
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from tau_rec.agents.litellm_agent import LiteLLMAgent
from tau_rec.harness import get_harness_profile

AGENT_NAME = "tau-rec-parity-agent"
DEFAULT_MCP_URL = "http://movie-runtime:8000/mcp"
DEFAULT_SUMMARY_PATH = "/logs/agent/tau-rec-parity-agent-summary.json"
# One MCP call can wait on a user-simulator turn. A native simulator call has a
# 120 s timeout and up to 8 attempts with backoff (roughly 30 min worst case),
# and a native run waits for it, so neither limit may cut it short.
MCP_READ_TIMEOUT_S = 1800.0
MCP_OPERATION_TIMEOUT_S = 1800.0
# Opening a connection to the sidecar, or waiting for a pooled one, is never
# that slow: fail fast instead.
MCP_CONNECT_TIMEOUT_S = 30.0

# call(tool_name, arguments) -> the tool's JSON result
Call = Callable[[str, dict], Awaitable[Any]]


async def build_agent(
    call: Call, model: str, reasoning_effort: str | None = None
) -> tuple[LiteLLMAgent, dict]:
    """The agent a native run builds for this trial, and the setup it came from.

    ``provider_order`` is None: the native run's default without a manifest.
    """
    setup = await call("get_agent_setup", {})
    agent = LiteLLMAgent(
        model=model,
        system_prompt=setup["system_prompt"],
        tool_definitions=setup["tool_definitions"],
        reasoning_effort=reasoning_effort,
        provider_order=None,
        harness=get_harness_profile(setup["harness"]),
    )
    return agent, setup


async def run_loop(
    agent: LiteLLMAgent, call: Call, greeting: str | None = None
) -> dict:
    """Play one trial; return the token and cost summary.

    Mirrors ``Orchestrator._run_trace`` for an agent with ``add_*_message``:
    the greeting and the user's opening go into the agent's history, then each
    ``respond`` gets the previous turn's tool results (or None after a user
    turn). The orchestrator in the sidecar asks again without a user turn when
    a response has neither text nor tool calls; the bridge then repeats the
    last user message, which is not added again.

    If ``respond`` raises, the error goes to ``report_agent_error`` and is
    raised inside the orchestrator, as a native agent's would be: a context
    overflow ends the trial (summarised as usual), any other error fails it
    (the call raises).
    """
    if greeting is None:
        greeting = (await call("get_agent_setup", {}))["greeting"]
    observation = await call("start_conversation", {})
    agent.add_assistant_message(greeting)
    agent.add_user_message(observation["content"])
    tool_results = None
    while not observation["ended"]:
        try:
            response = await agent.respond(tool_results)
        except Exception as error:  # noqa: BLE001 - the orchestrator classifies it
            observation = await call(
                "report_agent_error",
                {"error_type": type(error).__name__, "message": str(error)},
            )
            break
        observation = await call(
            "submit_agent_response",
            {"message": response.message, "tool_calls": response.tool_calls},
        )
        tool_results = None
        if observation["kind"] == "tool_results":
            tool_results = observation["tool_results"]
        elif observation["kind"] == "user_message" and response.message:
            agent.add_user_message(observation["content"])
    return summarize(agent, observation)


def summarize(agent: LiteLLMAgent, final: dict) -> dict:
    """Totals over the agent's answered model calls (tau-Rec's ``call_log``).

    ``n_cache_tokens`` counts cache reads, a subset of ``n_input_tokens``.
    ``cost_usd`` is tau-Rec's token-priced estimate, None when any call's model
    has no price.
    """
    calls = [row for row in agent.call_log if "tokens" in row]

    def total(field: str) -> int:
        return sum(row["tokens"][field] for row in calls)

    def cost(field: str) -> float | None:
        values = [row.get(field) for row in calls]
        return None if None in values else float(sum(values))

    return {
        "n_input_tokens": total("input"),
        "n_cache_tokens": total("cached"),
        "n_output_tokens": total("output"),
        "cost_usd": cost("estimated_cost_usd"),
        "metadata": {
            "agent": AGENT_NAME,
            "model": agent.model,
            "stop_reason": final.get("stop_reason"),
            "model_calls": len(calls),
            "cache_write_tokens": total("cache_write"),
            "provider_reported_cost_usd": cost("provider_reported_cost_usd"),
        },
        # tau-Rec's per-call log, as a native run stores it under api_calls.agent.
        "api_calls": agent.call_log,
    }


def mcp_caller(client) -> Call:
    async def call(name: str, arguments: dict) -> Any:
        result = await client.call_tool(name, arguments)
        text = result.content[0].text if result.content else ""
        if result.is_error:
            raise RuntimeError(f"{name} failed: {text}")
        return json.loads(text)

    return call


async def run_with_mcp(
    model: str, reasoning_effort: str | None, mcp_url: str, state: dict
) -> dict:
    """One trial over streamable HTTP. ``state["agent"]`` is set once the agent
    is built, so a caller can still summarise its usage if the trial fails."""
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    timeout = httpx2.Timeout(
        MCP_OPERATION_TIMEOUT_S,
        read=MCP_READ_TIMEOUT_S,
        connect=MCP_CONNECT_TIMEOUT_S,
        pool=MCP_CONNECT_TIMEOUT_S,
    )
    async with httpx2.AsyncClient(timeout=timeout) as http:
        transport = streamable_http_client(mcp_url, http_client=http)
        async with Client(transport, read_timeout_seconds=MCP_READ_TIMEOUT_S) as client:
            call = mcp_caller(client)
            agent, setup = await build_agent(call, model, reasoning_effort)
            state["agent"] = agent
            return await run_loop(agent, call, greeting=setup["greeting"])


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    """Run one trial and write the summary. Exit status 0 if the trial ended
    with a stop reason, else 1."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument(
        "--mcp-url", default=os.environ.get("TAU_REC_MCP_URL", DEFAULT_MCP_URL)
    )
    parser.add_argument("--summary-path", type=Path, default=Path(DEFAULT_SUMMARY_PATH))
    args = parser.parse_args(argv)
    state: dict = {}
    try:
        summary = asyncio.run(
            run_with_mcp(args.model, args.reasoning_effort, args.mcp_url, state)
        )
    except Exception as error:  # noqa: BLE001 - reported in the summary
        traceback.print_exc()
        if "agent" in state:  # usage spent before the failure
            summary = summarize(state["agent"], {"stop_reason": "error"})
        else:
            summary = {
                "n_input_tokens": None,
                "n_cache_tokens": None,
                "n_output_tokens": None,
                "cost_usd": None,
                "metadata": {
                    "agent": AGENT_NAME,
                    "model": args.model,
                    "stop_reason": "error",
                },
            }
        while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
            error = error.exceptions[0]  # the MCP client's task group wraps errors
        summary["metadata"]["error"] = f"{type(error).__name__}: {error}"
        _write_json(args.summary_path, summary)
        return 1
    _write_json(args.summary_path, summary)
    return 0 if summary["metadata"]["stop_reason"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
