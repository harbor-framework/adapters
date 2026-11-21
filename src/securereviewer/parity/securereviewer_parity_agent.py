"""Single-call parity agent for the SecureReviewer adapter.

Sends the task instruction (upstream's review prompt, the code change and the output format)
to the model in one Messages API call and writes the reply verbatim to /workspace/review.txt.
The original-side runner makes the same call with the same prompt and settings
(see single_call.py), so both sides differ only in where the review is graded.

Usage (from src/securereviewer):
    PYTHONPATH=parity harbor run -p ../../datasets/securereviewer-parity \
        --agent-import-path securereviewer_parity_agent:SecureReviewerSingleCallAgent \
        -m anthropic/claude-haiku-4-5 --env-file ../../../.env
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from single_call import MAX_TOKENS, TEMPERATURE, call_claude, response_text


class SecureReviewerSingleCallAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "securereviewer-single-call"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        return None

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        if not self.model_name:
            raise ValueError("Pass the model with -m, e.g. anthropic/claude-haiku-4-5")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "prompt.txt").write_text(instruction, encoding="utf-8", newline="")

        response = await asyncio.to_thread(call_claude, instruction, self.model_name)
        text = response_text(response)
        (self.logs_dir / "response.json").write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
        review = self.logs_dir / "review.txt"
        review.write_text(text, encoding="utf-8", newline="\n")

        await environment.upload_file(review, "/workspace/review.txt")

        usage = response.get("usage") or {}
        context.n_input_tokens = usage.get("input_tokens")
        context.n_output_tokens = usage.get("output_tokens")
        context.metadata = {
            "model": response.get("model"),
            "stop_reason": response.get("stop_reason"),
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "base_url": os.environ.get("ANTHROPIC_BASE_URL"),
        }
