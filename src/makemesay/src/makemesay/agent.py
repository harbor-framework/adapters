"""Harbor external agent that runs MakeMeSay's three completion roles."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from litellm import acompletion
from pydantic import Field

from harbor.agents.agent_auth_resolution import ModelConnectionSpec, ProviderAccess
from harbor.agents.base import AgentOptions, BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.model_api_format import ModelApiFormat

from .adapter import UPSTREAM_REVISION, SPLIT_MANIFEST, get_codeword_for_task
from .core import Game, run_auto_eval
from .scoring import ensure_nltk_resources, remove_internal_monologue


class MakeMeSayOptions(AgentOptions):
    """Optional role models; omitted roles reuse Harbor's selected model."""

    manipulatee_model: str | None = Field(default=None, min_length=1)
    request_timeout_sec: float = Field(default=120.0, gt=0)


class MakeMeSayAgent(BaseAgent):
    """Run one original MakeMeSay sample as manipulator, target, and judge."""

    capabilities = AgentCapabilities(base_url=True)
    options_model = MakeMeSayOptions
    MODEL_CONNECTION = ModelConnectionSpec(
        default_provider="openai",
        agent_provider_access=ProviderAccess(
            api_key_candidate_names=["OPENAI_API_KEY"],
            base_url_candidate_names=["OPENAI_BASE_URL", "OPENAI_API_BASE"],
        ),
        supported_api_formats=[
            ModelApiFormat.OPENAI_CHAT_COMPLETIONS,
        ],
        default_api_format_by_provider={
            "default": ModelApiFormat.OPENAI_CHAT_COMPLETIONS,
        },
    )

    @staticmethod
    def name() -> str:
        return "makemesay"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        del environment

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        task_data = self._parse_task_data(instruction)
        manipulator_model = self.model_name
        if not manipulator_model:
            raise ValueError("A manipulator model is required; pass Harbor's --model option")
        options = self.options or MakeMeSayOptions()
        manipulatee_model = options.manipulatee_model or manipulator_model

        ensure_nltk_resources()
        token_usage = {"input": 0, "output": 0, "cache": 0, "calls": 0}

        def completion_for(model_name: str, role: str):
            connection = self._resolve_model_connection(model_name)
            if connection.api_key is None and connection.api_key_candidate_names:
                names = " or ".join(connection.api_key_candidate_names)
                raise RuntimeError(
                    f"Missing credentials for MakeMeSay {role} model {model_name}; "
                    f"set {names} or pass the key through Harbor's agent environment"
                )

            async def complete(messages: list[dict[str, str]]) -> str:
                kwargs: dict[str, Any] = {
                    "model": model_name,
                    "messages": messages,
                    "timeout": options.request_timeout_sec,
                    "num_retries": 3,
                }
                if connection.api_key is not None:
                    kwargs["api_key"] = connection.api_key
                if connection.execution_base_url is not None:
                    kwargs["api_base"] = connection.execution_base_url

                response = await acompletion(**kwargs)

                content = response.choices[0].message.content
                if not isinstance(content, str):
                    raise RuntimeError(f"{role} model returned a non-text completion")
                usage = getattr(response, "usage", None)
                if usage is not None:
                    token_usage["input"] += int(getattr(usage, "prompt_tokens", 0) or 0)
                    token_usage["output"] += int(
                        getattr(usage, "completion_tokens", 0) or 0
                    )
                    details = getattr(usage, "prompt_tokens_details", None)
                    token_usage["cache"] += int(
                        getattr(details, "cached_tokens", 0) or 0
                    )
                token_usage["calls"] += 1
                return content

            return complete

        manipulator_completion = completion_for(manipulator_model, "manipulator")
        manipulatee_completion = completion_for(manipulatee_model, "manipulatee")

        game = await run_auto_eval(
            codeword=task_data["codeword"],
            manipulator_completion_fn=manipulator_completion,
            manipulatee_completion_fn=manipulatee_completion,
            max_turns=task_data["max_turns"],
        )

        public_messages = self._public_messages(game)
        result = {
            "schema_version": 1,
            "task_id": task_data["task_id"],
            "task_name": task_data["task_name"],
            "split": task_data["split"],
            "index": task_data["index"],
            "upstream_commit": task_data["upstream_commit"],
            "manipulator_model": manipulator_model,
            "manipulatee_model": manipulatee_model,
            "max_turns": game.max_turns,
            "turn": game.turn,
            "messages": public_messages,
        }
        await self._write_result(environment, result)

        context.n_input_tokens = token_usage["input"]
        context.n_output_tokens = token_usage["output"]
        context.n_cache_tokens = token_usage["cache"]
        context.metadata = {
            "task_id": task_data["task_id"],
            "split": task_data["split"],
            "max_turns": game.max_turns,
            "role_completion_calls": token_usage["calls"],
        }

    @staticmethod
    def _parse_task_data(instruction: str) -> dict[str, Any]:
        match = re.search(r"<!--\s*MAKEMESAY_DATA:(.*?)-->", instruction, re.DOTALL)
        if match is None:
            raise ValueError("Instruction is missing its MakeMeSay data block")
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError("MakeMeSay task data is not valid JSON") from exc
        required = {
            "task_id",
            "task_name",
            "split",
            "index",
            "upstream_commit",
        }
        if not isinstance(data, dict) or not required.issubset(data):
            raise ValueError("MakeMeSay task data is missing required fields")
        split = data["split"]
        index = data["index"]
        if split not in SPLIT_MANIFEST:
            raise ValueError(f"Unknown MakeMeSay split in task data: {split}")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError("MakeMeSay task index must be a non-negative integer")
        expected_task_id = f"make-me-say-{split}-{index:05d}"
        if data["task_id"] != expected_task_id:
            raise ValueError("MakeMeSay task ID does not match its split and index")
        if data["task_name"] != f"openai/{expected_task_id}":
            raise ValueError("MakeMeSay task name does not match its task ID")
        if data["upstream_commit"] != UPSTREAM_REVISION:
            raise ValueError("MakeMeSay task data uses an unexpected upstream revision")
        if data.get("max_turns") != 30:
            raise ValueError("This adapter preserves MakeMeSay's 30-turn default")
        data["codeword"] = get_codeword_for_task(split, index)
        return data

    @staticmethod
    def _public_messages(game: Game) -> list[dict[str, str]]:
        players = {
            game.manipulator.id: "manipulator",
            game.manipulatee.id: "manipulatee",
        }
        return [
            {
                "speaker": players[message.name],
                "content": remove_internal_monologue(message.content),
            }
            for message in game.messages
            if message.role != "system" and message.name in players
        ]

    @staticmethod
    async def _write_result(
        environment: BaseEnvironment, result: dict[str, Any]
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="makemesay-result-") as temp_dir:
            local_path = Path(temp_dir) / "makemesay_result.json"
            local_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            await environment.upload_file(
                source_path=local_path,
                target_path="/workspace/makemesay_result.json",
            )
