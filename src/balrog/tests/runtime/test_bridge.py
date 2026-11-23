"""Host bridge tests with a fake Harbor environment; no Docker or API calls."""

import json
import os
from pathlib import Path
import shlex
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from harbor.models.agent.context import AgentContext
from runtime_support import harbor_agent

BalrogNativeAgent = harbor_agent().BalrogNativeAgent


class FakeEnvironment:
    def __init__(self, report, code=0):
        self.report = report
        self.code = code
        self.executions = []
        self.uploads = []

    async def exec(self, command, **kwargs):
        self.executions.append((command, kwargs))
        return SimpleNamespace(return_code=0 if command.startswith("mkdir") else self.code)

    async def upload_file(self, source, target):
        self.uploads.append((source, target))

    async def download_file(self, source, target):
        if source.endswith("episode_result.json"):
            Path(target).write_text(json.dumps(self.report), encoding="utf-8")
        else:
            raise FileNotFoundError(source)


class BridgeTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path = Path(self.work.name)
        self.settings = self.path / "settings.json"
        self.settings.write_text(json.dumps({"api_base_url": "http://127.0.0.1:1/v1",
                                             "client": {"model_id": "offline-fake-model"}}))
        self.report = {"status": "completed", "input_tokens": 17, "output_tokens": 4,
                       "task_id": "babyai-goto-seed-0", "steps": 1}

    def tearDown(self):
        self.work.cleanup()

    def agent(self):
        return BalrogNativeAgent(logs_dir=self.path / "babyai-goto-seed-0__abc/agent",
                                 settings_path=self.settings, model_name="openai/offline-fake-model",
                                 api_key_env="OFFLINE_TEST_API_KEY")

    async def test_no_task_instruction_or_key_written_to_command(self):
        environment = FakeEnvironment(self.report)
        agent = self.agent()
        await agent.setup(environment)
        context = AgentContext()
        with patch.dict(os.environ, {"OFFLINE_TEST_API_KEY": "fake-test-key-not-a-credential"}):
            await agent.run("DO NOT SEND THIS SHELL INSTRUCTION TO MODEL", environment, context)
        self.assertEqual(len(environment.uploads), 2)
        command, args = environment.executions[-1]
        self.assertNotIn("DO NOT SEND", command)
        self.assertNotIn("fake-test-key", command)
        self.assertEqual(args["env"]["OPENAI_API_KEY"], "fake-test-key-not-a-credential")
        self.assertNotIn("RESULT_TOKEN", args["env"])
        self.assertEqual(context.n_input_tokens, 17)
        self.assertEqual(context.n_output_tokens, 4)
        self.assertEqual(context.metadata["status"], "completed")

    async def test_runner_error_raises(self):
        environment = FakeEnvironment({**self.report, "status": "error"}, code=1)
        with patch.dict(os.environ, {"OFFLINE_TEST_API_KEY": "fake-test-key-not-a-credential"}):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                await self.agent().run("unused", environment, AgentContext())

    async def test_truncated_log_directory_never_becomes_task_identity(self):
        full_id = "babaisai-goto-win-distr-obj-irrelevant-rule-seed-1"
        truncated = "babaisai-goto-win-distr-obj-irre"
        environment = FakeEnvironment({**self.report, "task_id": full_id})
        agent = BalrogNativeAgent(logs_dir=self.path / (truncated + "__hxXjvna") / "agent",
                                 settings_path=self.settings, model_name="offline-fake-model",
                                 api_key_env="OFFLINE_TEST_API_KEY")
        # Exercise the bridge's UUID fallback rather than Harbor's session ID.
        agent.session_id = None
        context = AgentContext()
        with patch.dict(os.environ, {"OFFLINE_TEST_API_KEY": "fake-test-key-not-a-credential"}):
            await agent.run("unused", environment, context)
        arguments = shlex.split(environment.executions[-1][0])
        self.assertIsNone(agent.task_id)
        self.assertNotIn("--task-id", arguments)
        self.assertNotIn(truncated, arguments)
        session = arguments[arguments.index("--session-id") + 1]
        self.assertEqual(str(uuid.UUID(session)), session)
        self.assertEqual(context.metadata["task_id"], full_id)

    async def test_missing_key_raises_before_execution(self):
        environment = FakeEnvironment(self.report)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "credential"):
                await self.agent().run("unused", environment, AgentContext())
        self.assertEqual(environment.executions, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
