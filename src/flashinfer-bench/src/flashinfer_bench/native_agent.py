"""Harbor transport for upstream's KernelGenerator; no model prompts are rewritten."""

import os
import shlex

from harbor.agents.base import BaseAgent


class FlashInferNativeAgent(BaseAgent):
    def __init__(
        self,
        *args,
        language="triton",
        rounds=10,
        attempts=2,
        reasoning_effort="high",
        seed=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.settings = {
            "language": language,
            "rounds": rounds,
            "attempts": attempts,
            "reasoning-effort": reasoning_effort,
            "seed": seed,
        }

    @staticmethod
    def name():
        return "flashinfer-native"

    def version(self):
        return "15618a67e8d7b7f49ca61b5ba3b9f26a876d0bee"

    async def setup(self, environment):
        pass  # Dependencies are installed by the task image.

    async def run(self, instruction, environment, context):
        if not self.model_name:
            raise ValueError("An explicit upstream model ID is required")
        args = [
            "python",
            "/opt/adapter-runtime/generate.py",
            "--model",
            self.model_name,
        ]
        for name, value in self.settings.items():
            if value is not None:
                args.extend(["--" + name, str(value)])
        env = {"LLM_API_KEY": os.environ["LLM_API_KEY"]}
        if os.environ.get("BASE_URL"):
            env["BASE_URL"] = os.environ["BASE_URL"]
        result = await environment.exec(
            shlex.join(args) + " > /logs/agent/native.log 2>&1",
            env=env,
            timeout_sec=14400,
        )
        context.metadata = {"upstream_revision": self.version(), **self.settings}
        if result.return_code != 0:
            raise RuntimeError(
                f"Native generator failed (exit {result.return_code}); "
                "see /logs/agent/native.log"
            )
