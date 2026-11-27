"""Pinned upstream AgentDojo pipeline, with native and MCP runtime transports."""

import argparse
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
from agentdojo.functions_runtime import EmptyEnv
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.task_suite.task_suite import (
    functions_stack_trace_from_messages,
    model_output_from_messages,
)
from agentdojo.types import get_text_content_as_str
from openai import OpenAI

MODEL = "deepseek-v4.1-flash"


def encode(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else str(value)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=encode) + "\n")


class CapturedPipeline(AgentPipeline):
    def query(self, *args, **kwargs):
        result = super().query(*args, **kwargs)
        self.messages = result[3]
        return result


def make_pipeline(system_message, output):
    client = OpenAI(api_key=os.environ["API_KEY"], base_url=os.environ["API_BASE"],
                    timeout=180, max_retries=0)
    create = client.chat.completions.create

    def recorded(**kwargs):
        # Only request bodies and model responses, never auth headers.
        with (output / "requests.jsonl").open("a") as handle:
            handle.write(json.dumps(kwargs, default=encode) + "\n")
        response = create(**kwargs)
        with (output / "responses.jsonl").open("a") as handle:
            handle.write(response.model_dump_json() + "\n")
        return response

    client.chat.completions.create = recorded
    llm = OpenAILLM(client, MODEL)  # Preserve upstream sampling/retry defaults.
    llm.name = MODEL
    return CapturedPipeline.from_config(PipelineConfig(
        llm=llm, model_id=None, defense=None, system_message_name=None,
        system_message=system_message, tool_output_format="yaml",
    ))


def finalize(pipeline, output):
    messages = pipeline.messages
    save(output / "messages.json", messages)
    final = {"model_output": model_output_from_messages(messages) or [],
             "calls": functions_stack_trace_from_messages(messages)}
    save(output / "final.json", final)
    return final


def native(config, output):
    suite = get_suite(config["benchmark_version"], config["suite"])
    user_task = suite.get_user_task_by_id(config["user_task_id"])
    injection = (suite.get_injection_task_by_id(config["injection_task_id"])
                 if config.get("injection_task_id") else None)
    pipeline = make_pipeline(config["system_message"], output)
    utility, security = suite.run_task_with_pipeline(
        pipeline, user_task, injection, config["injections"],
    )
    finalize(pipeline, output)
    save(output / "result.json", {"status": "completed", "utility": int(utility),
                                  "security": int(security) if injection else None})


class Schema:
    def __init__(self, value):
        self.value = value

    def model_json_schema(self):
        return self.value


def inline_refs(value, root=None):
    """Compare FastMCP's inlined schema with the original JSON Schema."""
    root = value if root is None else root
    if isinstance(value, list):
        return [inline_refs(item, root) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        if not value["$ref"].startswith("#/"):
            raise ValueError("External tool schema reference")
        target = root
        for part in value["$ref"][2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        value = {**target, **{k: v for k, v in value.items() if k != "$ref"}}
    return {k: inline_refs(v, root) for k, v in value.items() if k != "$defs"}


class RemoteRuntime:
    def __init__(self, tools, order, client, loop, definitions):
        by_name = {tool.name: tool for tool in tools if tool.name != "submit_answer"}
        if set(by_name) != set(order):
            raise ValueError("MCP tool coverage differs from upstream")
        for name in order:
            expected = definitions[name]
            if (expected["description"] != by_name[name].description
                    or inline_refs(expected["parameters"]) != inline_refs(by_name[name].input_schema)):
                raise ValueError(f"MCP tool definition differs from upstream: {name}")
        self.functions = {
            name: SimpleNamespace(name=name, description=definitions[name]["description"],
                                  parameters=Schema(definitions[name]["parameters"]))
            for name in order
        }
        self.client, self.loop = client, loop

    def run_function(self, _env, name, args):
        result = asyncio.run_coroutine_threadsafe(
            self.client.call_tool(name, args, raise_on_error=False), self.loop
        ).result(timeout=120)
        if result.is_error:
            raise RuntimeError(f"MCP transport failed for {name}")
        text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
        if (result.meta or {}).get("runtime_error"):
            return None, text
        return text, None


async def remote(config, output):
    from fastmcp import Client

    pipeline = make_pipeline(config["system_message"], output)
    async with Client("http://tool-server:8000/mcp") as client:
        runtime = RemoteRuntime(await client.list_tools(), config["tool_order"],
                                client, asyncio.get_running_loop(), config["tool_definitions"])

        def run_loop():
            # Same three outer attempts and 15-step inner loop as the pinned
            # TaskSuite.run_task_with_pipeline and AgentPipeline.from_config.
            for _ in range(3):
                pipeline.query(config["prompt"], runtime, EmptyEnv())
                if model_output_from_messages(pipeline.messages) is not None:
                    break
            return finalize(pipeline, output)

        final = await asyncio.to_thread(run_loop)
        await client.call_tool("submit_answer", {
            "answer": get_text_content_as_str(final["model_output"]),
        })
    save(output / "completed.json", {"status": "completed"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["native", "remote"], required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.config.read_text())
    if args.mode == "native":
        native(data, args.output)
    else:
        asyncio.run(remote(data, args.output))
