"""Harbor bridge for the unmodified AgentDojo function-calling pipeline."""

import hashlib
import json
import shlex
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities


class AgentDojoPipelineAgent(BaseAgent):
    capabilities = AgentCapabilities(mcp_servers=True)

    def __init__(self, *args, inputs_dir, **kwargs):
        super().__init__(*args, **kwargs)
        self.inputs_dir = Path(inputs_dir)

    @staticmethod
    def name():
        return "agentdojo-pipeline"

    def version(self):
        return "agentdojo-0.1.35"

    async def setup(self, environment):
        result = await environment.exec("mkdir -p /logs/agent", timeout_sec=30)
        if result.return_code:
            raise RuntimeError("Could not create agent log directory")
        await environment.upload_file(Path(__file__).with_name("pipeline.py"), "/app/pipeline.py")

    async def run(self, instruction, environment, context):
        digest = hashlib.sha256(instruction.encode()).digest()
        matches = [p.parent for p in self.inputs_dir.glob("*/instruction.md")
                   if hashlib.sha256(p.read_bytes()).digest() == digest]
        if not matches or len({(p / "environment/agent-input.json").read_bytes() for p in matches}) != 1:
            raise ValueError("Could not resolve unambiguous upstream prompt/settings")
        await environment.upload_file(matches[0] / "environment/agent-input.json", "/app/agent-input.json")
        result = await environment.exec(
            "python /app/pipeline.py --mode remote --config /app/agent-input.json --output /logs/agent",
            env={"API_KEY": self._get_env("API_KEY"),
                 "API_BASE": self._get_env("API_BASE")}, timeout_sec=900,
        )
        (self.logs_dir / "pipeline.log").write_text((result.stdout or "") + (result.stderr or ""))
        if result.return_code:
            raise RuntimeError(f"Upstream pipeline exited {result.return_code}; see pipeline.log")
        final_file = self.logs_dir / "final.json"
        await environment.download_file("/logs/agent/final.json", final_file)
        # Privileged harness finalization is loopback-only on the sidecar.
        # Models see suite tools only and cannot call this grading interface.
        payload = final_file.read_text()
        code = ("import urllib.request; "
                f"data={payload!r}.encode(); "
                "r=urllib.request.Request('http://127.0.0.1:8000/parity-finalize',"
                "data=data,headers={'Content-Type':'application/json'}); "
                "urllib.request.urlopen(r,timeout=30).read()")
        finalized = await environment.service_exec(
            "python -c " + shlex.quote(code), service="tool-server", timeout_sec=40,
        )
        if finalized.return_code:
            raise RuntimeError("Could not finalize upstream scoring trace")
        await environment.download_file("/logs/agent/responses.jsonl", self.logs_dir / "responses.jsonl")
        responses = [json.loads(line) for line in (self.logs_dir / "responses.jsonl").read_text().splitlines()]
        context.n_input_tokens = sum(r.get("usage", {}).get("prompt_tokens", 0) for r in responses)
        context.n_output_tokens = sum(r.get("usage", {}).get("completion_tokens", 0) for r in responses)
        context.metadata = {"models_served": sorted({r["model"] for r in responses})}
