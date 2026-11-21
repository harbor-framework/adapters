"""Real Inspect/Anthropic serialization with all external networking prohibited."""
import asyncio
import json
import socket
from pathlib import Path

import httpx2
import pytest
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser, ContentReasoning, ContentImage, get_model
from inspect_ai.tool import ToolCall

from chess_puzzles.original import evaluate
from chess_puzzles.outcomes import IncompleteEvaluation
from chess_puzzles.parity import harbor_config, validate_settings
from chess_puzzles.runtime import make_model, run_upstream
from chess_puzzles.source import upstream
from chess_puzzles.token_counting import configure_token_counting
from fake_anthropic import FakeAnthropic


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Offline counting test attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", denied)


async def test_counts_readable_thinking_and_tools_without_mutating_history(tmp_path):
    model = make_model("anthropic/claude-haiku-5-5", "https://offline.invalid", "offline-key",
                       token_count_mode="local", count_audit_path=tmp_path / "counts.jsonl")
    plain = [ChatMessageUser(content="Question"), ChatMessageAssistant(content="Answer")]
    thought = ChatMessageAssistant(content=[ContentReasoning(
        reasoning="secret-signature", summary="Consider the position. " * 1000, redacted=True)])
    before = thought.model_dump_json()
    base = await model.count_tokens(plain)
    assert await model.count_tokens([*plain, thought]) > base + 1000
    assert thought.model_dump_json() == before
    tool = ChatMessageAssistant(content="", tool_calls=[ToolCall(
        id="t", function="submit_answer", arguments={"answer": "word " * 1000})])
    assert await model.count_tokens([*plain, tool]) > base + 500
    opaque_short = ChatMessageAssistant(content=[ContentReasoning(reasoning="sig", redacted=True)])
    opaque_long = ChatMessageAssistant(content=[ContentReasoning(reasoning="sig" * 1000, redacted=True)])
    assert await model.count_tokens([opaque_short]) == await model.count_tokens([opaque_long])
    audit = (tmp_path / "counts.jsonl").read_text()
    assert "secret-signature" not in audit and "Question" not in audit and "offline-key" not in audit
    assert any(row["opaque_thinking_blocks"] for row in map(json.loads, audit.splitlines()))
    with pytest.raises(ValueError, match="text/reasoning"):
        await model.api.count_tokens([ChatMessageUser(content=[ContentImage(image="https://invalid/image.png")])])


def test_local_mode_explicit_and_fails_closed():
    with pytest.raises(ValueError, match="token_count_mode"):
        make_model("mockllm/model", token_count_mode="typo")
    with pytest.raises(ValueError, match="only for Anthropic"):
        make_model("mockllm/model", token_count_mode="local")
    model = make_model("anthropic/claude-haiku-5-5", "https://offline.invalid", "offline-key")
    native = model.api.count_tokens
    assert configure_token_counting(model, "provider").api.count_tokens == native
    configure_token_counting(model, "local")
    with pytest.raises(ValueError, match="already configured"):
        configure_token_counting(model, "provider")


def test_config_routes_count_mode_to_harbor(tmp_path):
    settings = json.loads(Path("parity_settings.json").read_text())
    settings.update(max_output_tokens=100, response_max_tokens=100, compaction_threshold_tokens=10000)
    validate_settings(settings, for_run=True)
    config = harbor_config(settings, tmp_path, [4], tmp_path, "test")
    assert config["agents"][0]["kwargs"]["token_count_mode"] == "local"
    settings["token_count_mode"] = "provider"
    assert harbor_config(settings, tmp_path, [4], tmp_path, "test")["agents"][0]["kwargs"]["token_count_mode"] == "provider"


@pytest.mark.parametrize("scenario", ["submit", "continue", "forced", "compact", "error", "timeout"])
async def test_real_provider_original_and_worker_identical_without_count_endpoint(tmp_path, monkeypatch, scenario):
    sample = next(s for s in upstream().chess_puzzles(max_output_tokens=64000, compaction_threshold_tokens=200000).dataset if s.id == 4)
    settings = {"model": "anthropic/claude-haiku-5-5", "base_url": "https://offline.invalid",
                "token_count_mode": "local", "max_output_tokens": 1 if scenario == "forced" else 20000,
                "response_max_tokens": 1000, "compaction_threshold_tokens": 1500 if scenario == "compact" else 200000,
                "attempt_timeout_sec": 1 if scenario == "timeout" else 30, "reasoning_effort": None}
    traces, outcomes = [], []
    for side in ("original", "worker"):
        fake = FakeAnthropic(scenario, sample.target)
        async def handle(request):
            body = json.loads(request.content)
            if scenario == "timeout":
                fake.requests.append({"path": request.url.path, "body": body})
                await asyncio.sleep(3)
            status, headers, content = fake.response(request.url.path, body)
            return httpx2.Response(status, headers=headers, content=content)
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
        def factory(*args, **kwargs):
            kwargs.update(http_client=client, api_key="offline-placeholder")
            return get_model(*args, **kwargs)
        monkeypatch.setattr("chess_puzzles.runtime.get_model", factory)
        dest = tmp_path / side
        async def run():
            if side == "original":
                return await evaluate(settings, [4], dest)
            return await run_upstream(sample.input, settings["model"], dest,
                settings["max_output_tokens"], settings["compaction_threshold_tokens"],
                base_url=settings["base_url"], response_max_tokens=settings["response_max_tokens"],
                attempt_timeout_sec=settings["attempt_timeout_sec"], sample_id=4, token_count_mode="local")
        try:
            if scenario in ("error", "timeout"):
                with pytest.raises(IncompleteEvaluation):
                    await run()
            else:
                await run()
        finally:
            await client.aclose()
        outcome = json.loads((dest / "outcome.json").read_text())
        outcomes.append(outcome)
        traces.append(fake.requests)
        assert outcome["token_counting"]["mode"] == "local"
        assert (dest / "token-counts.jsonl").exists()
        assert all(r["path"] == "/v1/messages" for r in fake.requests)
        if scenario not in ("error", "timeout"):
            assert outcome["samples"][0]["answer"] == sample.target
            assert outcome["samples"][0]["metadata"]["forced_final_answer"] == (scenario == "forced")
            assert outcome["usage"]["output_tokens"] == fake.generations * 10
            assert outcome["usage"]["cache_read_tokens"] == fake.generations * 20
            assert bool(outcome["samples"][0]["compactions"]) == (scenario == "compact")
    assert traces[0] == traces[1]
    assert outcomes[0]["status"] == outcomes[1]["status"]
    if scenario in ("continue", "forced"):
        blocks = [b for m in traces[0][1]["body"]["messages"] for b in m["content"] if isinstance(b, dict)]
        assert any(b.get("signature") == "offline-signature" for b in blocks)
