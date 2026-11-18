"""Harbor bridge for the original BALROG agent, with no extra model prompt."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import uuid

from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.models.agent.context import AgentContext


class BalrogNativeAgent(BaseAgent):
    capabilities = AgentCapabilities(atif=True)

    @staticmethod
    def name():
        return "balrog-native"

    def version(self):
        return "b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5"

    def _parse_model_name(self, model_name):
        # This adapter uses a pinned upstream OpenAI-compatible client, not
        # LiteLLM inference. Avoid alias/provider rewrites of the exact model ID.
        if model_name.startswith("openai/"):
            return "openai", model_name.removeprefix("openai/")
        return None, model_name

    def __init__(self, logs_dir, model_name=None, *, settings_path, runner_path=None,
                 task_id=None, api_key_env="OPENAI_API_KEY", execution_timeout_sec=7200,
                 extra_env=None, **kwargs):
        super().__init__(logs_dir=logs_dir, model_name=model_name, extra_env=extra_env, **kwargs)
        self.settings_path = Path(settings_path).resolve()
        self.runner_path = Path(runner_path).resolve() if runner_path else Path(__file__).with_name("parity_runner.py")
        self.settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
        configured_model = self.settings["client"]["model_id"]
        if model_name is not None and model_name not in {configured_model, "openai/" + configured_model}:
            raise ValueError("Harbor model_name must match the exact parity settings model_id")
        # Harbor truncates long trial directory names. The game service owns
        # the full task identity; never infer it from logs_dir.
        self.task_id = task_id
        self.api_key_env = api_key_env
        self.execution_timeout_sec = int(execution_timeout_sec)
        if self.execution_timeout_sec < 1:
            raise ValueError("execution_timeout_sec must be positive")
        self._remote_root = "/app/balrog-parity"

    async def setup(self, environment):
        # This is deterministic setup; neither filenames nor shell output reach
        # the model. Upstream code/SDKs are already installed in the agent image.
        result = await environment.exec("mkdir -p " + shlex.quote(self._remote_root), timeout_sec=30)
        if result.return_code != 0:
            raise RuntimeError("Unable to create the BALROG runner directory")
        await environment.upload_file(self.runner_path, self._remote_root + "/parity_runner.py")
        await environment.upload_file(self.settings_path, self._remote_root + "/settings.json")

    async def run(self, instruction, environment, context: AgentContext):
        # Intentionally do not forward Harbor instruction.md: game /observation
        # supplies the exact native instruction to the upstream prompt builder.
        key = self._extra_env.get(self.api_key_env) or os.environ.get(self.api_key_env)
        if not key and self.settings["client"].get("client_name", "openai") != "vllm":
            raise RuntimeError("Required model credential is missing")
        arguments = [
            "python", self._remote_root + "/parity_runner.py", "--mode", "http",
            "--settings", self._remote_root + "/settings.json",
            "--output-dir", str(self.environment_logs_dir),
            "--session-id", self.session_id or str(uuid.uuid4()),
        ]
        if self.task_id is not None:
            arguments.extend(["--task-id", self.task_id])
        command = shlex.join(arguments)
        child_env = {"PYTHONPATH": "/opt/balrog", "PYTHONUNBUFFERED": "1"}
        if key:
            child_env["OPENAI_API_KEY"] = key
        result = None
        try:
            result = await environment.exec(command, env=child_env, timeout_sec=self.execution_timeout_sec)
        finally:
            # Remote runs may not mount logs onto the host. Retrieve the report
            # even on timeout so token totals/error evidence survive.
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            for filename in ("episode_result.json", "model_calls.json", "trajectory.json", "error.json"):
                try:
                    await environment.download_file(str(self.environment_logs_dir / filename), self.logs_dir / filename)
                except Exception:
                    pass
            self.populate_context_post_run(context)
        if result is None or result.return_code != 0:
            raise RuntimeError("BALROG native agent failed; inspect agent/error.json")
        report_path = self.logs_dir / "episode_result.json"
        if not report_path.exists() or json.loads(report_path.read_text(encoding="utf-8"))["status"] != "completed":
            raise RuntimeError("BALROG runner did not certify a completed episode")

    def populate_context_post_run(self, context):
        path = self.logs_dir / "episode_result.json"
        if not path.exists():
            return
        report = json.loads(path.read_text(encoding="utf-8"))
        context.n_input_tokens = report["input_tokens"]
        context.n_output_tokens = report["output_tokens"]
        # Upstream clients don't report cache tokens or authoritative cost.
        context.metadata = {key: report.get(key) for key in (
            "status", "task_id", "steps", "model_calls", "elapsed_seconds",
            "settings_sha256", "runner_sha256", "source_commits", "runtime_versions")}
