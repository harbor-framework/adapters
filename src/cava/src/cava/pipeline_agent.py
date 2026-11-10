"""Parity agent reproducing the LLM stage of CAVA's OpenAI pipeline
(src/cava/inference.py::process_with_openai_pipeline, CAVA@1af23b1).

Sends the two pipeline user messages from /app/task.json with temperature 0. For
function calling it passes /app/functions.json as tools with tool_choice="required",
answers every call with MOCK_RESPONSE(<name>) and keeps going with tool_choice="auto"
while the model calls tools and fewer than 10 calls were made, like upstream.
Run with:

    harbor run -p datasets/cava -a cava.pipeline_agent:CavaPipelineAgent -m openai/gpt-4o
"""

from __future__ import annotations

import asyncio
import base64
import json
import shlex

from openai import AsyncOpenAI

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

MAX_RETRIES = 5
INITIAL_SLEEP_SEC = 0.1  # upstream sleep_time, doubled after each failed attempt


class CavaPipelineAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "cava-pipeline"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    async def _read_json(self, environment: BaseEnvironment, path: str):
        result = await environment.exec(command=f"cat {path}")
        if result.return_code != 0:
            raise RuntimeError(f"cannot read {path}: {result.stderr}")
        return json.loads(result.stdout)

    async def _write(self, environment: BaseEnvironment, path: str, text: str) -> None:
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        await environment.exec(
            command=f"printf %s {shlex.quote(encoded)} | base64 -d > {path}"
        )

    async def run(self, instruction: str, environment: BaseEnvironment,
                  context: AgentContext) -> None:
        if not self.model_name:
            raise RuntimeError("model_name is required for CavaPipelineAgent")
        model = self.model_name.split("/", 1)[1] if "/" in self.model_name else self.model_name
        task = await self._read_json(environment, "/app/task.json")
        messages = list(task["messages"])
        client = AsyncOpenAI()

        tools = None
        if task["function_calling"]:
            tools = await self._read_json(environment, "/app/functions.json")

        api_args = {"model": model, "messages": messages, "temperature": 0}
        if tools:
            api_args["tools"] = tools
            api_args["tool_choice"] = "required"

        llm_response = ""
        all_function_calls: list[dict] = []
        sleep_time = INITIAL_SLEEP_SEC
        for attempt in range(MAX_RETRIES):
            try:
                completion = await client.chat.completions.create(**api_args)
                all_function_calls = []
                conversation = list(messages)
                final_response = ""
                while (
                    tools
                    and completion.choices[0].message.tool_calls
                    and len(all_function_calls) < 10
                ):
                    assistant_message = completion.choices[0].message
                    final_response = assistant_message.content or ""
                    conversation.append({
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": [tc.model_dump() for tc in assistant_message.tool_calls],
                    })
                    for tool_call in assistant_message.tool_calls:
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            arguments = {"error": "Failed to parse arguments",
                                         "raw": tool_call.function.arguments}
                        all_function_calls.append(
                            {"name": tool_call.function.name, "arguments": arguments}
                        )
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"MOCK_RESPONSE({tool_call.function.name})",
                        })
                    completion = await client.chat.completions.create(
                        model=model, messages=conversation, temperature=0,
                        tools=tools, tool_choice="auto",
                    )
                if not all_function_calls:
                    llm_response = completion.choices[0].message.content or ""
                else:
                    llm_response = final_response
                break
            except Exception as exc:
                # upstream restarts from the initial request after a backoff and, after
                # the last attempt, returns labels[0] or "" (no shipped subtask has labels)
                self.logger.warning("pipeline LLM call failed (%s/%s): %s",
                                    attempt + 1, MAX_RETRIES, exc)
                llm_response, all_function_calls = "", []
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(sleep_time)
                    sleep_time *= 2

        # inference.py process_sample: >= 10 calls blanks the text response
        if tools and len(all_function_calls) >= 10:
            llm_response = ""
        if tools:
            await self._write(
                environment, "/app/function_calls.jsonl",
                "".join(json.dumps(c) + "\n" for c in all_function_calls),
            )
        await self._write(environment, "/app/answer.txt", llm_response)
        (self.logs_dir / "pipeline_output.json").write_text(json.dumps(
            {"response": llm_response, "function_calls": all_function_calls}, indent=2))
