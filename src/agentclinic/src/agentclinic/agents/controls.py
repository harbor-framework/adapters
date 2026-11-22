import json
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from .errors import RuntimeRequestError
from .gateway import ClinicGateway

WRONG_DIAGNOSIS = "Common cold"


class WrongDiagnosisAgent(BaseAgent):
    capabilities = AgentCapabilities(mcp_servers=True)

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        clinic_url: str = "http://clinic:8000",
        python: str = "python3",
        diagnosis: str = WRONG_DIAGNOSIS,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self.clinic_url = clinic_url
        self.python = python
        self.diagnosis = diagnosis

    @staticmethod
    def name() -> str:
        return "agentclinic-wrong-diagnosis"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        return None

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        status, reply = await ClinicGateway(environment, self.clinic_url, self.python).post(
            "submit_diagnosis", self.diagnosis
        )
        if status != "submitted":
            raise RuntimeRequestError(
                f"the clinic did not accept the control diagnosis (status {status}): {reply[:200]}"
            )
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "control.json").write_text(json.dumps({"submitted": self.diagnosis, "reply": reply}, indent=2))
