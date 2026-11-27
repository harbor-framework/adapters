"""Harbor agent for ControlArena's submit-only SAE trusted-monitoring protocol."""

import json
import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

import anyio
from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext, ModelUsage


class SAEControlAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "control-arena-sae-interp"

    def version(self) -> str:
        return version("control-arena")

    async def setup(self, environment: BaseEnvironment) -> None:
        # The trusted controller runs on the host. No agent tools need installing.
        pass

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        process_env = os.environ | self.extra_env
        mode = process_env.get("CONTROL_ARENA_EVAL_MODE", "honest")
        trusted = process_env.get("CONTROL_ARENA_TRUSTED_MODEL")
        if not self.model_name or not trusted:
            raise ValueError("Set a Harbor model and CONTROL_ARENA_TRUSTED_MODEL")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        run_log = self.logs_dir / "native-run.log"
        with TemporaryDirectory() as tmp:
            work = Path(tmp)
            prompt = work / "instruction.md"
            result_path = work / "result.json"
            prompt.write_text(instruction, encoding="utf-8")
            # Inspect has process-global evaluation state; isolate concurrent trials.
            with run_log.open("wb") as log:
                run = await anyio.run_process(
                    [
                        sys.executable, "-X", "utf8", "-m", "control_arena_sae_interp.native",
                        "--instruction-file", str(prompt), "--mode", mode,
                        "--model", self.model_name, "--trusted-model", trusted,
                        "--verifier-grades", "--log-dir", str(self.logs_dir / "inspect"),
                        "--result-file", str(result_path),
                    ],
                    env=process_env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            if run.returncode:
                raise RuntimeError(f"SAE protocol exited with {run.returncode}. See {run_log}")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            context.metadata = {
                "source_index": result["source_index"],
                "eval_mode": result["mode"],
                "protocol": "trusted_monitoring",
                "policy_model": self.model_name,
                "trusted_model": trusted,
                "scores": result["scores"],
            }
            context.model_usage = {}
            for model_name, usage in result["model_usage"].items():
                cached = (usage["input_tokens_cache_read"] or 0) + (
                    usage["input_tokens_cache_write"] or 0
                )
                context.model_usage[model_name] = ModelUsage(
                    n_input_tokens=usage["input_tokens"] + cached,
                    n_cache_tokens=cached,
                    n_output_tokens=usage["output_tokens"],
                    cost_usd=usage["total_cost"],
                )
            context.n_input_tokens = sum(m.n_input_tokens for m in context.model_usage.values())
            context.n_cache_tokens = sum(m.n_cache_tokens for m in context.model_usage.values())
            context.n_output_tokens = sum(m.n_output_tokens for m in context.model_usage.values())
            if result["submission"] is not None:
                submission_file = work / "submission.json"
                submission_file.write_text(json.dumps(result["submission"]), encoding="utf-8")
                await environment.upload_file(submission_file, "/logs/artifacts/submission.json")
