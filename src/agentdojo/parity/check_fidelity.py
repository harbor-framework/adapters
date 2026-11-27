"""Offline differential check: native runtime versus actual MCP transport."""

import argparse
import asyncio
import datetime
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentdojo.agent_pipeline.llms.openai_llm import (
    _function_to_openai,
    _message_to_openai,
)
from agentdojo.agent_pipeline.tool_execution import ToolsExecutor
from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import text_content_block_from_string
from fastmcp import Client
from pipeline import RemoteRuntime


async def check(task):
    config = json.loads((task / "environment/runtime-server/task_config.json").read_text())
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        source = task / "environment/runtime-server/server.py"
        shutil.copy2(source, folder / "server.py")
        (folder / "task_config.json").write_text(json.dumps(config))
        spec = importlib.util.spec_from_file_location("transport_check_server", folder / "server.py")
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
        suite = get_suite(config["benchmark_version"], config["suite"])
        user = suite.get_user_task_by_id(config["user_task_id"])
        env = user.init_environment(suite.load_and_inject_default_environment(config["injections"]))
        pre = env.model_copy(deep=True)
        native = FunctionsRuntime(suite.tools)
        oracle = json.loads((task / "solution/oracle.json").read_text())
        calls = [FunctionCall(function=c["function"], args=c["args"], id=f"call_{i}")
                 for i, c in enumerate(oracle["calls"])]
        # Invalid tool names must stay local to ToolsExecutor, exactly upstream.
        calls.append(FunctionCall(function="nonexistent_test_tool", args={}, id="invalid"))
        async with Client(server.mcp) as client:
            remote = RemoteRuntime(await client.list_tools(), list(native.functions), client,
                                   asyncio.get_running_loop(), {
                                       f.name: {"description": f.description, "parameters": f.parameters.model_json_schema()}
                                       for f in native.functions.values()})
            expected = [_function_to_openai(f) for f in native.functions.values()]
            actual = [_function_to_openai(f) for f in remote.functions.values()]
            if expected != actual:
                from deepdiff import DeepDiff
                raise ValueError(f"Tool schema mismatch: {DeepDiff(expected, actual)}")
            for call in calls:
                messages = [{"role": "assistant", "content": None, "tool_calls": [call]}]
                left = ToolsExecutor().query("", native, env, messages)[3][-1]
                right = (await asyncio.to_thread(ToolsExecutor().query, "", remote, env, messages))[3][-1]
                left_message, right_message = _message_to_openai(left, "test"), _message_to_openai(right, "test")
                if left_message != right_message:
                    from deepdiff import DeepDiff
                    raise ValueError(f"{call.function}: {DeepDiff(left_message, right_message)}")
            await client.call_tool("submit_answer", {"answer": oracle["answer"]})
        final = {"model_output": [text_content_block_from_string(oracle["answer"])],
                 "calls": [c.model_dump() for c in calls]}

        class Request:
            client = SimpleNamespace(host="127.0.0.1")

            async def json(self):
                return final

        outsider = Request()
        outsider.client = SimpleNamespace(host="172.20.0.9")
        assert (await server.parity_finalize(outsider)).status_code == 403
        assert (await server.evaluate(outsider)).status_code == 403
        assert (await server.parity_finalize(Request())).status_code == 200
        scored = json.loads((await server.evaluate(Request())).body)
        assert scored["utility"] == suite._check_task_result(user, final["model_output"], pre, env, calls)
        if config["injection_task_id"]:
            attack = suite.get_injection_task_by_id(config["injection_task_id"])
            assert scored["security"] == suite._check_task_result(attack, final["model_output"], pre, env, calls)


async def main(root):
    from agentdojo.default_suites.v1.tools import cloud_drive_client, email_client

    class FixedClock(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime(2026, 1, 1, 12, tzinfo=tz)

    # Freeze only wall-clock fields in this offline comparison. Real runs keep
    # upstream's live clock; independently executed tools naturally differ here.
    clock_module = SimpleNamespace(datetime=FixedClock)
    with patch.object(cloud_drive_client, "datetime", clock_module), patch.object(email_client, "datetime", clock_module):
        for task in sorted(root.iterdir()):
            await check(task)
            print("PASS", task.name, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path)
    asyncio.run(main(parser.parse_args().tasks))
