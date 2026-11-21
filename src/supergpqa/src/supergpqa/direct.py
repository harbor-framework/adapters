"""Shared single-turn Chat Completions transport; no model tools or hidden retries."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

VERSION = "0.1.0"
EXPECTED_RETURNED_MODEL = "gpt-6-luna-2026-09-22"
DEFAULT_SETTINGS: dict[str, Any] = {
    "model": "gpt-6-luna",
    "reasoning_effort": "none",
    "temperature": 0,
    "max_completion_tokens": 2048,
    "stream": False,
}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def payload(instruction: str, model: str = DEFAULT_SETTINGS["model"]) -> dict:
    return {
        **DEFAULT_SETTINGS,
        "model": model,
        "messages": [{"role": "user", "content": instruction}],
    }


def endpoint_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Use a confirmed HTTPS API base URL without credentials/query/fragment"
        )
    return base_url.rstrip("/") + "/chat/completions"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError(
            "API redirect refused; confirm the endpoint before sending credentials"
        )


def complete(
    instruction: str,
    output: Path,
    *,
    model: str = DEFAULT_SETTINGS["model"],
    base_url: str | None = None,
    timeout: float = 120,
) -> str:
    """Persist request/response once. Pending/failed calls require explicit diagnosis.

    Reusing a completed response is only for resuming the SAME task and run.
    Every side/repetition must have a distinct output directory.
    """
    base_url = base_url or os.environ.get("SUPERGPQA_BASE_URL", "")
    url = endpoint_url(base_url)
    body = payload(instruction, model)
    fingerprint = digest(
        {
            "url": url,
            "request": body,
            "timeout": timeout,
            "agent_version": VERSION,
            "expected_returned_model": EXPECTED_RETURNED_MODEL,
            "python": platform.python_version(),
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "call.json"
    if state_path.exists():
        previous = json.loads(state_path.read_text())
        if previous["fingerprint"] != fingerprint:
            raise ValueError(
                "Existing call uses a different configuration; use a new experiment"
            )
        if previous["status"] != "complete":
            raise RuntimeError(
                "Ambiguous/failed previous call: diagnose before explicitly retrying"
            )
        text = (output / "response.txt").read_bytes().decode("utf-8")
        response = json.loads((output / "response.json").read_text())
        if response.get("model") != EXPECTED_RETURNED_MODEL:
            raise ValueError(
                "Cached response model version differs from the locked version"
            )
        if (
            digest(text) != previous["response_hash"]
            or response["choices"][0]["message"]["content"] != text
        ):
            raise ValueError("Saved response evidence is inconsistent")
        return text
    key = os.environ.get("SUPERGPQA_API_KEY")
    if not key:
        raise ValueError("Set SUPERGPQA_API_KEY in the process environment")
    state = {
        "fingerprint": fingerprint,
        "status": "pending",
        "started_at": time.time(),
        "url": url,
        "agent_version": VERSION,
        "python": platform.python_version(),
        "transport": "python-stdlib-urllib",
        "timeout_sec": timeout,
        "automatic_retries": 0,
    }
    # Exclusive creation prevents duplicate paid calls from concurrent resumes.
    with state_path.open("x") as handle:
        json.dump(state, handle)
    save_json(output / "request.json", body)
    started = time.monotonic()
    try:
        request = Request(
            url,
            json.dumps(body).encode(),
            {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key,
            },
        )
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            raw = json.load(response)
        save_json(output / "response.json", raw)
        if raw.get("model") != EXPECTED_RETURNED_MODEL:
            raise ValueError("Provider model version changed; stop the experiment")
        choice = raw["choices"][0]
        if choice["message"].get("tool_calls"):
            raise ValueError("Unexpected tool calls in a no-tools experiment")
        text = choice["message"]["content"]
        if not isinstance(text, str):
            raise TypeError(
                "Expected a text response; null is an API failure, not an answer"
            )
        (output / "response.txt").write_bytes(text.encode("utf-8"))
        state.update(
            status="complete",
            response_hash=digest(text),
            returned_model=raw.get("model"),
            usage=raw.get("usage"),
            finish_reason=choice.get("finish_reason"),
            system_fingerprint=raw.get("system_fingerprint"),
        )
    except Exception as exc:  # noqa: BLE001 -- redact all transport/provider errors
        # Never persist exception messages or provider error bodies: they may echo credentials.
        state.update(status="failed", error_type=type(exc).__name__)
        if isinstance(exc, HTTPError):
            state["http_status"] = exc.code
        raise RuntimeError(
            "API call failed; see redacted call.json; automatic retry disabled"
        ) from None
    finally:
        state.update(ended_at=time.time(), elapsed_sec=time.monotonic() - started)
        save_json(state_path, state)
    return text
