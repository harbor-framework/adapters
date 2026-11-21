"""Shared Anthropic input-length estimation, never generation or billing.

This is not Anthropic's tokenizer. The pinned provider's count-time normalization
is reused: readable thinking becomes text; opaque signatures are not tokenized.
Inspect still calibrates context length from actual API usage after each turn.
"""
import functools
import json
import math
from pathlib import Path
from types import MethodType

from inspect_ai.model import ChatMessageUser, ContentReasoning, ContentText

ALGORITHM = "anthropic-json-o200k-1.1-v1"
MULTIPLIER = 1.1


def validate_count_mode(mode):
    if mode not in ("provider", "local"):
        raise ValueError("token_count_mode must be 'provider' or 'local'")


def count_settings(mode):
    validate_count_mode(mode)
    return {"mode": mode, "algorithm": ALGORITHM if mode == "local" else None,
            "is_estimate": mode == "local"}


def configure_token_counting(model, mode="provider", audit_path=None):
    """Override this instance only; never silently fall back after an API error.

    Local mode supports the pinned Anthropic provider and text/reasoning/tool-call
    histories. Unsupported content fails instead of silently counting as zero.
    """
    validate_count_mode(mode)
    if getattr(model.api, "_chess_local_counter", False):
        raise ValueError("Token counting already configured; create a fresh model")
    if mode == "provider":
        return model
    from inspect_ai.model._providers.anthropic import (
        AnthropicAPI,
        consecutive_user_message_reducer,
        message_param,
        neutralize_thinking_for_token_counting,
        pad_tool_messages_for_token_counting,
    )
    from inspect_ai.solver._task_state import sample_state
    from anthropic.types import MessageTokensCount
    import tiktoken

    if not isinstance(model.api, AnthropicAPI):
        raise ValueError("Local counting is validated only for Anthropic models")
    encoding = tiktoken.get_encoding("o200k_base")
    sequence = 0

    def estimate(converted, *, purpose, message_count, readable_thinking=0, opaque_thinking=0):
        nonlocal sequence
        serialized = json.dumps(converted, ensure_ascii=False, separators=(",", ":"))
        raw = len(encoding.encode(serialized, disallowed_special=()))
        result = max(1, math.ceil(raw * MULTIPLIER))
        sequence += 1
        state = sample_state()
        if audit_path is not None:
            path = Path(audit_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Counts only: never write message text, signatures, headers or keys.
            row = {"sequence": sequence, "sample_id": state.sample_id if state else None,
                   **count_settings(mode), "purpose": purpose, "base_tokens": raw,
                   "multiplier": MULTIPLIER, "estimated_tokens": result,
                   "message_count": message_count,
                   "readable_thinking_blocks": readable_thinking,
                   "opaque_thinking_blocks": opaque_thinking}
            with path.open("a") as output:
                output.write(json.dumps(row) + "\n")
        return result

    async def local_count(_api, input, config=None):
        messages = [ChatMessageUser(content=input)] if isinstance(input, str) else input
        readable_thinking = 0
        opaque_thinking = 0
        for message in messages:
            if isinstance(message.content, list):
                for content in message.content:
                    if not isinstance(content, (ContentText, ContentReasoning)):
                        raise ValueError("Local counting supports text/reasoning/tool calls only")
                    if isinstance(content, ContentReasoning):
                        if content.summary or (not content.redacted and content.reasoning):
                            readable_thinking += 1
                        else:
                            opaque_thinking += 1

        # Same count-time conversion as Inspect 0.3.273's AnthropicAPI.
        # Generation retains the original messages and thinking signatures.
        converted = [await message_param(message) for message in messages]
        converted = functools.reduce(consecutive_user_message_reducer, converted, [])
        converted = pad_tool_messages_for_token_counting(converted)
        converted = neutralize_thinking_for_token_counting(converted)
        return estimate(converted, purpose="context", message_count=len(messages),
                        readable_thinking=readable_thinking, opaque_thinking=opaque_thinking)

    async def local_reasoning_count(*, model, messages, **options):
        # Inspect also calls the SDK directly after generation when the response
        # lacks output_tokens_details.thinking_tokens. That is diagnostic only;
        # output_tokens (which includes thinking) still comes from actual usage.
        if options or any(m.get("role") != "user" or not isinstance(m.get("content"), str)
                          for m in messages):
            raise ValueError("Unexpected auxiliary count request in pinned provider")
        tokens = estimate(messages, purpose="reasoning_usage_estimate", message_count=len(messages))
        return MessageTokensCount(input_tokens=tokens)

    async def local_text_count(api, text):
        return await local_count(api, text)

    model.api.count_tokens = MethodType(local_count, model.api)
    model.api.count_text_tokens = MethodType(local_text_count, model.api)
    model.api.client.messages.count_tokens = local_reasoning_count
    model.api._chess_local_counter = True
    return model
