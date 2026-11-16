"""Model transport for the GDM parity custom agents.

The Inspect solvers call models through Inspect's native tool-calling.
This transport speaks the OpenAI-compatible chat-completions function
calling dialect so any provider endpoint with that dialect can be
pinned for a parity run. A different provider dialect should be added
as a new transport, never by changing prompts or tool semantics.
Tests inject a fake transport.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelTurn:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    raw_reasoning: str = ""


class ModelTransport(Protocol):
    async def generate(
        self, messages: list[dict[str, Any]], tool_schemas: list[dict[str, Any]]
    ) -> ModelTurn: ...


def _strip_provider(model_name: str) -> str:
    return model_name.split("/", 1)[1] if "/" in model_name else model_name


class OpenAICompatibleTransport:
    """POST {base_url}/chat/completions with function tools."""

    def __init__(
        self,
        model_name: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        temperature: float | None = None,
        max_tokens: int | None = None,
        request_timeout_sec: int = 300,
        strip_provider_prefix: bool = True,
        tool_choice: str | None = "required",
    ):
        self.model = (
            _strip_provider(model_name) if strip_provider_prefix else model_name
        )
        self.base_url = (
            base_url
            or os.environ.get("GDM_MODEL_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self.api_key = (
            api_key
            or os.environ.get("GDM_MODEL_API_KEY")
            or os.environ.get(api_key_env)
            or os.environ.get("OPENAI_API_KEY")
        )
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.request_timeout_sec = request_timeout_sec
        self.tool_choice = tool_choice
        self.tool_choice = tool_choice

    async def generate(
        self, messages: list[dict[str, Any]], tool_schemas: list[dict[str, Any]]
    ) -> ModelTurn:
        return await asyncio.to_thread(self._generate_sync, messages, tool_schemas)

    def _generate_sync(
        self, messages: list[dict[str, Any]], tool_schemas: list[dict[str, Any]]
    ) -> ModelTurn:
        if not self.api_key:
            raise RuntimeError(
                "No model API key: set GDM_MODEL_API_KEY or OPENAI_API_KEY"
            )
        body: dict[str, Any] = {"model": self.model, "messages": messages}
        if tool_schemas:
            body["tools"] = [
                {"type": "function", "function": schema} for schema in tool_schemas
            ]
            if self.tool_choice is not None:
                body["tool_choice"] = self.tool_choice
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.max_tokens is not None:
            body["max_tokens"] = self.max_tokens
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.request_timeout_sec
                ) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                return parse_openai_payload(payload)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"Model request failed after retries: {last_error}")


def parse_openai_payload(payload: dict[str, Any]) -> ModelTurn:
    message = payload["choices"][0]["message"]
    tool_calls = []
    for i, call in enumerate(message.get("tool_calls") or []):
        fn = call.get("function", {})
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            args = {"_unparsed_arguments": raw_args}
        tool_calls.append(
            ToolCall(
                id=call.get("id") or f"call_{i}",
                name=fn.get("name", ""),
                arguments=args if isinstance(args, dict) else {"value": args},
            )
        )
    usage_raw = payload.get("usage") or {}
    usage = {
        "prompt_tokens": int(usage_raw.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage_raw.get("completion_tokens", 0) or 0),
        "cached_tokens": int(
            (usage_raw.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            or 0
        ),
    }
    return ModelTurn(
        content=message.get("content") or "",
        tool_calls=tool_calls,
        usage=usage,
        raw_reasoning=message.get("reasoning_content") or "",
    )
