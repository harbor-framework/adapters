"""OpenAI and Anthropic compatible LLM client for standard and custom endpoints.

Uses Python standard library HTTP (``urllib``) so it works with zero extra runtime
dependencies both on the Harbor host and inside the upstream parity runner.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from androidworld.agents.t3a_core import (
    DEFAULT_MAX_RETRY,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
)

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
ERROR_CALLING_LLM = "Error calling LLM"


@dataclass(frozen=True)
class LlmPrediction:
    """Result of a single text-only LLM completion."""

    text: str
    is_safe: bool | None
    raw_response: Any
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


def normalize_api_format(
    model_name: str,
    api_format: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> str:
    """Resolve ``openai`` vs ``anthropic`` protocol from explicit config, model ID, or env."""
    if api_format is not None:
        raw = getattr(api_format, "value", api_format)
        norm = str(raw).strip().lower()
        if norm in {"openai", "openai_chat_completions", "openai-chat", "chat_completions"}:
            return "openai"
        if norm in {"anthropic", "anthropic_messages", "anthropic-messages", "messages"}:
            return "anthropic"
        if norm not in {"", "auto"}:
            raise ValueError(f"Unsupported api_format: {api_format!r}")

    lowered = model_name.strip().lower()
    if lowered.startswith("anthropic/") or "claude" in lowered:
        has_anthropic = bool(_lookup_env(env, "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE"))
        has_openai = bool(_lookup_env(env, "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"))
        if has_anthropic or not has_openai:
            return "anthropic"
        return "openai"

    if lowered.startswith("openai/") or lowered.startswith("gpt-"):
        return "openai"

    if _lookup_env(env, "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE") and not _lookup_env(
        env, "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"
    ):
        return "anthropic"

    return "openai"


def strip_provider_prefix(model_name: str) -> str:
    """Strip ``openai/`` or ``anthropic/`` routing prefix when sending wire model IDs."""
    for prefix in ("openai/", "anthropic/"):
        if model_name.startswith(prefix):
            return model_name[len(prefix) :]
    return model_name


def is_reasoning_or_gpt5_model(model_name: str) -> bool:
    """Return True for OpenAI reasoning / GPT-5 series models with chat-completions quirks."""
    wire = strip_provider_prefix(model_name).strip().lower()
    for prefix in ("gpt-5", "o1", "o3", "o4"):
        if wire == prefix or wire.startswith(f"{prefix}-") or wire.startswith(f"{prefix}."):
            return True
    return False


def build_openai_chat_url(base_url: str | None) -> str:
    base = (base_url or DEFAULT_OPENAI_BASE_URL).strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    parsed = urllib.parse.urlparse(base)
    if parsed.path in ("", "/"):
        return f"{base}/v1/chat/completions"
    return f"{base}/chat/completions"


def build_anthropic_messages_url(base_url: str | None) -> str:
    base = (base_url or DEFAULT_ANTHROPIC_BASE_URL).strip().rstrip("/")
    if base.endswith("/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def _lookup_env(env: Mapping[str, str] | None, *names: str) -> str | None:
    sources: list[Mapping[str, str]] = []
    if env:
        sources.append(env)
    sources.append(os.environ)
    for src in sources:
        for name in names:
            val = src.get(name)
            if val:
                return val
    return None


class T3ALlmClient:
    """Text-only LLM client supporting OpenAI and Anthropic compatible endpoints."""

    def __init__(
        self,
        model_name: str,
        *,
        api_format: str | None = "auto",
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_name: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_retry: int = DEFAULT_MAX_RETRY,
        retry_wait_seconds: float = 2.0,
        timeout_sec: float = 120.0,
        env: Mapping[str, str] | None = None,
    ):
        if not model_name:
            raise ValueError("model_name must be provided for T3ALlmClient")
        self.model_name = model_name
        self.wire_model = strip_provider_prefix(model_name)
        self.env = dict(env) if env else {}
        self.protocol = normalize_api_format(model_name, api_format, env=self.env)
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.max_retry = max(1, min(int(max_retry), 5))
        self.retry_wait_seconds = float(retry_wait_seconds)
        self.timeout_sec = float(timeout_sec)

        if self.protocol == "anthropic":
            resolved_base = base_url or _lookup_env(
                self.env, "ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE"
            )
            self.endpoint_url = build_anthropic_messages_url(resolved_base)
            key_candidates = (
                [api_key_name]
                if api_key_name
                else ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
            )
            self.api_key = api_key or _lookup_env(self.env, *key_candidates)
            if not self.api_key:
                raise RuntimeError(
                    "Anthropic API key not set (checked "
                    + ", ".join(key_candidates)
                    + ")."
                )
        else:
            resolved_base = base_url or _lookup_env(
                self.env, "OPENAI_BASE_URL", "OPENAI_API_BASE"
            )
            self.endpoint_url = build_openai_chat_url(resolved_base)
            key_candidates = (
                [api_key_name]
                if api_key_name
                else ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
            )
            self.api_key = api_key or _lookup_env(self.env, *key_candidates)
            if not self.api_key:
                raise RuntimeError(
                    "OpenAI API key not set (checked "
                    + ", ".join(key_candidates)
                    + ")."
                )

    def build_request(self, prompt: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        if self.protocol == "anthropic":
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "harbor-androidworld/0.1",
                "x-api-key": self.api_key,
                "anthropic-version": DEFAULT_ANTHROPIC_VERSION,
            }
            payload: dict[str, Any] = {
                "model": self.wire_model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            return self.endpoint_url, headers, payload

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "harbor-androidworld/0.1",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.wire_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if is_reasoning_or_gpt5_model(self.wire_model):
            payload["max_completion_tokens"] = self.max_tokens
        else:
            payload["temperature"] = self.temperature
            payload["max_tokens"] = self.max_tokens
        return self.endpoint_url, headers, payload

    def parse_response(self, body: dict[str, Any]) -> LlmPrediction:
        if self.protocol == "anthropic":
            blocks = body.get("content") or []
            texts = [
                str(block.get("text", ""))
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            text = "\n".join(t for t in texts if t) if texts else ""
            usage = body.get("usage") or {}
            in_tok = int(usage.get("input_tokens") or 0)
            out_tok = int(usage.get("output_tokens") or 0)
            stop_reason = body.get("stop_reason")
            is_safe = False if stop_reason == "refusal" else None
            return LlmPrediction(
                text=text,
                is_safe=is_safe,
                raw_response=body,
                prompt_tokens=in_tok,
                completion_tokens=out_tok,
            )

        choices = body.get("choices") or []
        if not choices:
            raise ValueError(f"OpenAI response missing 'choices': {body}")
        first = choices[0]
        message = first.get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            text = "".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict)
            )
        else:
            text = str(content or "")
        finish_reason = first.get("finish_reason")
        is_safe = False if finish_reason == "content_filter" else None
        usage = body.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
        return LlmPrediction(
            text=text,
            is_safe=is_safe,
            raw_response=body,
            prompt_tokens=in_tok,
            completion_tokens=out_tok,
        )

    def _post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)

    def predict_with_usage(self, text_prompt: str) -> LlmPrediction:
        url, headers, payload = self.build_request(text_prompt)
        wait_seconds = self.retry_wait_seconds
        last_error: Exception | None = None

        for attempt in range(self.max_retry):
            try:
                body = self._post_json(url, headers, payload)
                return self.parse_response(body)
            except urllib.error.HTTPError as exc:
                last_error = exc
                err_body = exc.read().decode("utf-8", errors="replace")
                print(
                    f"Error calling {self.protocol} LLM HTTP {exc.code}: {err_body[:400]}"
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                print(f"Error calling {self.protocol} LLM: {exc}")

            if attempt + 1 < self.max_retry:
                time.sleep(wait_seconds)
                wait_seconds *= 2

        return LlmPrediction(
            text=ERROR_CALLING_LLM,
            is_safe=None,
            raw_response=None,
        )

    def predict(self, text_prompt: str) -> tuple[str, bool | None, Any]:
        """Upstream ``infer.LlmWrapper.predict`` compatible signature."""
        pred = self.predict_with_usage(text_prompt)
        return pred.text, pred.is_safe, pred.raw_response


def make_upstream_llm_wrapper(client: T3ALlmClient) -> Any:
    """Wrap ``T3ALlmClient`` as an ``android_world.agents.infer.LlmWrapper``."""
    from android_world.agents import infer

    class _CompatWrapper(infer.LlmWrapper):
        def __init__(self, inner: T3ALlmClient):
            self._inner = inner

        def predict(self, text_prompt: str) -> tuple[str, bool | None, Any]:
            return self._inner.predict(text_prompt)

    return _CompatWrapper(client)
