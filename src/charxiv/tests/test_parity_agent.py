"""Tests for the charxiv-direct parity agent helpers (need the `parity` extra)."""

import asyncio
import json
import os
from pathlib import Path

import pytest

pytest.importorskip("harbor.agents.base")
from charxiv import adapter as A
from charxiv import parity_agent as P

UPSTREAM = Path(os.environ.get("CHARXIV_UPSTREAM_DIR", "/nonexistent"))


def _instruction(question: str) -> str:
    template = (A.TEMPLATE_DIR / "instruction.md").read_text(encoding="utf-8")
    return A.render(
        template,
        {
            "image_path": A.IMAGE_PATH_IN_CONTAINER,
            "answer_path": A.ANSWER_PATH,
            "question": question,
        },
    )


def test_upstream_query_roundtrip_simple():
    q = "What is the title?\n    * Answer briefly.\n    "
    assert P.upstream_query(_instruction(q)) == q


def test_upstream_query_rejects_foreign_instruction():
    with pytest.raises(ValueError):
        P.upstream_query("Answer this question.")


@pytest.mark.skipif(not (UPSTREAM / "data").exists(), reason="set CHARXIV_UPSTREAM_DIR")
def test_upstream_query_roundtrip_all_tasks():
    tasks = A.load_tasks(A.CharXivSource(source_dir=UPSTREAM))
    assert len(tasks) == 5000
    for t in tasks:
        assert P.upstream_query(_instruction(t.question)) == t.question


def test_request_bodies_match_upstream_parameters():
    o = P.openai_request("gpt-4o-mini-2024-07-18", "Q", "AAAA", 1.0)
    assert [p["type"] for p in o["messages"][0]["content"]] == ["text", "image_url"]
    assert (
        o["messages"][0]["content"][1]["image_url"]["url"]
        == "data:image/jpeg;base64,AAAA"
    )
    assert (o["max_tokens"], o["temperature"], o["top_p"], o["seed"]) == (
        1000,
        0.0,
        1.0,
        42,
    )
    a = P.anthropic_request("claude-x", "Q", "AAAA", 1.0)
    assert [p["type"] for p in a["messages"][0]["content"]] == ["image", "text"]
    assert (a["max_tokens"], a["temperature"], a["top_p"]) == (1024, 0.0, 1.0)
    assert "top_p" not in P.anthropic_request("claude-x", "Q", "AAAA", None)
    json.dumps(o), json.dumps(a)


def test_retries_follow_upstream_schedule():
    sleeps = []

    async def fake_sleep(t):
        sleeps.append(t)

    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("boom")
        return "ok"

    resp, errors = asyncio.run(P.generate_with_retries(flaky, sleep=fake_sleep))
    assert resp == "ok" and len(errors) == 2
    assert sleeps == pytest.approx([1.0, 1.6])

    async def always_fail():
        raise RuntimeError("down")

    sleeps.clear()
    resp, errors = asyncio.run(P.generate_with_retries(always_fail, sleep=fake_sleep))
    assert resp == P.FAILED_RESPONSE and len(errors) == 10
    assert sleeps[-1] == pytest.approx(1.6**9)
