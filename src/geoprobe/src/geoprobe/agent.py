"""Harbor entry point for the original sealed-completion / persistent-REPL agent."""
import json
import shlex

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from .sources import ARENA_COMMIT


class GeoProbeNativeAgent(BaseInstalledAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.model_name:
            raise ValueError("An exact native model identifier is required")

    @staticmethod
    def name() -> str:
        return "geoprobe-native"

    def version(self) -> str:
        return ARENA_COMMIT

    async def install(self, environment: BaseEnvironment) -> None:
        # Runtime and dependencies are pinned in the task image. No model call.
        await self.exec_as_agent(environment, "test -f /opt/arena/scripts/run_w1_native_case.py")

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        # Use the native model identifier verbatim, including any slash. Credentials
        # and endpoint use the upstream LLM_* / OPENAI_* environment contract and
        # Harbor's scoped --ae forwarding; never read unrelated host credentials.
        command = shlex.join(["python", "/opt/geoprobe/run_public.py", "--model", self.model_name])
        await self.exec_as_agent(environment, command, timeout_sec=950)
        local = self.logs_dir / "native-runtime-report.json"
        await environment.download_file("/logs/agent/native/runtime-report.json", local)
        report = json.loads(local.read_text())
        usage = report.get("llm_usage", {})
        context.n_input_tokens = usage.get("prompt_tokens")
        context.n_output_tokens = usage.get("completion_tokens")
        context.cost_usd = usage.get("accumulated_cost") if usage.get("cost_available") else None
        context.metadata = {"arena_commit": ARENA_COMMIT, "provider": "openai-compatible",
                            "native_report": "native/runtime-report.json", "private_grading": "separate_verifier"}
