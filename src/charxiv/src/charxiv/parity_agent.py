"""``charxiv-direct``: Harbor port of CharXiv's own response generation, for parity.

Upstream CharXiv (princeton-nlp/CharXiv@7ebe88f, ``src/generate.py``) does not run
an agent. For every question it makes one API call with the chart image and the
question text, retried by ``generate_lib/utils.py:generate_response_remote_wrapper``,
and stores the reply as the response that ``src/evaluate.py`` grades. This agent
reproduces that call inside Harbor, so the parity experiment runs the same
generation on both sides and only the harness (task packaging and the verifier)
differs. The original side runs upstream with three changes forced by hard-coded
values (judge model, ``nq_per_query=1`` for descriptive grading, OpenAI base URL);
see the README.

Matched behaviour (upstream file in parentheses):

- query = the upstream question text, i.e. the task instruction without the two
  lines the adapter adds (image path and answer file); image = the task's chart,
  base64-encoded as ``image/jpeg``;
- OpenAI models (``generate_lib/gpt.py``): one user message with the text part
  first, then the image as a ``data:image/jpeg;base64`` URL; ``max_tokens=1000``,
  ``temperature=0.0``, ``top_p=1.0``, ``seed=42``;
- Anthropic models (``generate_lib/claude.py``): one user message with the image
  block first, then the text block; ``max_tokens=1024``, ``temperature=0.0``,
  ``top_p=1.0``; the reply is ``content[0].text``;
- retries (``generate_response_remote_wrapper``): up to 10 attempts, sleeping
  1 s and multiplying the sleep by 1.6 after each failure; if every attempt
  fails, the response is ``"Error in generating response."``;
- the response is written verbatim to ``/app/answer.txt``.

The client SDKs' own retries are disabled (``max_retries=0``) so that only the
upstream retry loop applies. The agent runs on the host: it reads the chart from
the task container and writes the answer back with ``environment.exec``, and calls
the model API directly. Credentials come from the host environment
(``OPENAI_API_KEY``/``OPENAI_BASE_URL`` or ``ANTHROPIC_API_KEY``/
``ANTHROPIC_BASE_URL``); nothing is passed into the task container.

Some newer Anthropic models reject requests that set both ``temperature`` and
``top_p``. Pass ``top_p: null`` in the agent kwargs to omit ``top_p``, and make the
same one-line change on the original side.
"""

from __future__ import annotations

import asyncio
import base64
import json
import shlex
from typing import Any

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from .adapter import ANSWER_PATH, IMAGE_PATH_IN_CONTAINER

INSTRUCTION_PREFIX = (
    f"The chart for this task is the image file `{IMAGE_PATH_IN_CONTAINER}`. "
    "View the image to answer the question below.\n\n"
)
INSTRUCTION_SUFFIX = f"\n\nWrite your final answer to the file `{ANSWER_PATH}`."

MAX_RETRIES = 10
INIT_SLEEP = 1.0
SLEEP_FACTOR = 1.6
FAILED_RESPONSE = "Error in generating response."


def upstream_query(instruction: str) -> str:
    """Recover the upstream question text from a generated task instruction."""
    text = instruction.rstrip("\n")
    if not text.startswith(INSTRUCTION_PREFIX) or not text.endswith(INSTRUCTION_SUFFIX):
        raise ValueError("instruction does not have the CharXiv adapter wrapper")
    return text[len(INSTRUCTION_PREFIX) : len(text) - len(INSTRUCTION_SUFFIX)]


def openai_request(model: str, query: str, image_b64: str, top_p: float | None) -> dict:
    """Request body of generate_lib/gpt.py (random_baseline=False)."""
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": query},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 1000,
        "temperature": 0.0,
        "seed": 42,
    }
    if top_p is not None:
        body["top_p"] = top_p
    return body


def anthropic_request(
    model: str, query: str, image_b64: str, top_p: float | None
) -> dict:
    """Request body of generate_lib/claude.py."""
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 1024,
        "temperature": 0.0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": query},
                ],
            }
        ],
    }
    if top_p is not None:
        body["top_p"] = top_p
    return body


async def generate_with_retries(call, sleep=asyncio.sleep) -> tuple[str, list[str]]:
    """Mirror of generate_response_remote_wrapper for one query."""
    sleep_time = INIT_SLEEP
    errors: list[str] = []
    for _ in range(MAX_RETRIES):
        try:
            return await call(), errors
        except Exception as e:  # noqa: BLE001 - upstream retries on any error
            errors.append(f"{type(e).__name__}: {e}")
            await sleep(sleep_time)
            sleep_time *= SLEEP_FACTOR
    return FAILED_RESPONSE, errors


class CharxivDirectAgent(BaseAgent):
    def __init__(self, *args, top_p: float | None = 1.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._top_p = top_p

    @staticmethod
    def name() -> str:
        return "charxiv-direct"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    def _provider_and_model(self) -> tuple[str, str]:
        if not self.model_name:
            raise RuntimeError("model_name is required, e.g. openai/gpt-4o-2024-08-06")
        provider, _, model = self.model_name.partition("/")
        if not model:
            raise RuntimeError(
                f"model_name must be <provider>/<model>, got {self.model_name}"
            )
        if provider not in ("openai", "anthropic"):
            raise RuntimeError(
                f"unsupported provider {provider!r}; use openai/ or anthropic/"
            )
        return provider, model

    def _make_call(self, provider: str, model: str, query: str, image_b64: str):
        if provider == "openai":
            import openai

            client = openai.OpenAI(max_retries=0)
            body = openai_request(model, query, image_b64, self._top_p)

            def call() -> str:
                return client.chat.completions.create(**body).choices[0].message.content

        else:
            import anthropic

            client = anthropic.Anthropic(max_retries=0)
            body = anthropic_request(model, query, image_b64, self._top_p)

            def call() -> str:
                return client.messages.create(**body).content[0].text

        async def acall() -> str:
            result = await asyncio.to_thread(call)
            if result is None:
                raise RuntimeError("empty model response")
            return result

        return body, acall

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        provider, model = self._provider_and_model()
        query = upstream_query(instruction)

        img = await environment.exec(
            f"base64 -w0 {shlex.quote(IMAGE_PATH_IN_CONTAINER)}"
        )
        if img.return_code != 0 or not img.stdout:
            raise RuntimeError(f"cannot read {IMAGE_PATH_IN_CONTAINER}: {img.stderr}")
        image_b64 = img.stdout.strip()
        base64.b64decode(image_b64, validate=True)

        body, call = self._make_call(provider, model, query, image_b64)
        response, errors = await generate_with_retries(call)

        encoded = base64.b64encode(response.encode("utf-8")).decode("ascii")
        out = await environment.exec(
            f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(ANSWER_PATH)}"
        )
        if out.return_code != 0:
            raise RuntimeError(f"cannot write {ANSWER_PATH}: {out.stderr}")

        logged = json.loads(json.dumps(body))
        for msg in logged["messages"]:
            for part in msg["content"]:
                if part.get("type") == "image_url":
                    part["image_url"]["url"] = "data:image/jpeg;base64,<omitted>"
                elif part.get("type") == "image":
                    part["source"]["data"] = "<omitted>"
        failed = response == FAILED_RESPONSE
        context.metadata = {
            "provider": provider,
            "attempts": len(errors) + (0 if failed else 1),
            "failed": failed,
        }
        (self.logs_dir / "charxiv_direct.json").write_text(
            json.dumps(
                {"request": logged, "response": response, "errors": errors},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
