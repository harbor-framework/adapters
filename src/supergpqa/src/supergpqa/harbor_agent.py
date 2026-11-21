"""Harbor wrapper for the shared direct API agent. Gold data is never read here."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from supergpqa.direct import DEFAULT_SETTINGS, VERSION, complete


class SuperGPQADirectAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "supergpqa-direct"

    def version(self) -> str:
        return VERSION

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        await asyncio.to_thread(
            complete,
            instruction,
            self.logs_dir,
            model=self.model_name or DEFAULT_SETTINGS["model"],
        )
        # The wrapper performs file I/O, not a model-accessible tool call.
        # Upload bytes rather than interpolating model-generated text into a shell command.
        await environment.upload_file(
            source_path=Path(self.logs_dir) / "response.txt",
            target_path="/app/answer.txt",
        )
        import json

        state = json.loads((self.logs_dir / "call.json").read_text())
        usage = state.get("usage") or {}
        context.n_input_tokens = usage.get("prompt_tokens")
        context.n_output_tokens = usage.get("completion_tokens")
        context.metadata = {
            "agent_version": VERSION,
            "returned_model": state.get("returned_model"),
            "finish_reason": state.get("finish_reason"),
        }
