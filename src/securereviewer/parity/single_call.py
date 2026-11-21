"""One Anthropic Messages API call, shared by the Harbor-side agent and the original-side runner.

Settings mirror SecureReviewer's inference (infer/test.py): greedy decoding (do_sample=False ->
temperature 0) and a 2,000-token budget. The endpoint and key come from ANTHROPIC_BASE_URL and
ANTHROPIC_API_KEY. Only the standard library is used, so the same file runs in Harbor's
environment and next to upstream's scripts.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

MAX_TOKENS = 2000
TEMPERATURE = 0.0
ATTEMPTS = 6


def call_claude(prompt: str, model: str, max_tokens: int = MAX_TOKENS, temperature: float = TEMPERATURE) -> dict:
    """Send `prompt` as a single user message; return the raw Messages API response."""
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    key = os.environ["ANTHROPIC_API_KEY"]
    body = json.dumps(
        {
            "model": model.split("/", 1)[-1],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        req = urllib.request.Request(
            f"{base}/v1/messages",
            data=body,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code not in (408, 409, 429, 500, 502, 503, 504, 529):
                raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}") from e
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(min(60, 5 * 2**attempt))
    raise RuntimeError(f"API call failed after {ATTEMPTS} attempts: {last}")


def response_text(response: dict) -> str:
    return "".join(block.get("text", "") for block in response.get("content", []) if block.get("type") == "text")
