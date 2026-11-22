import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from .. import prompts
from ..llm import ChatClient, LLMError
from .errors import AgentAuthenticationError, ApiConnectionError, RuntimeRequestError
from .gateway import ClinicGateway

INSTRUCTION_END = "\n\n## How the consultation works"
DIALOGUE_STATUSES = ("ok", "submitted")


def make_chat() -> ChatClient:
    try:
        return ChatClient.from_env()
    except LLMError as exc:
        raise AgentAuthenticationError(str(exc)) from exc


def objective_from_instruction(instruction: str) -> str:
    marker = "\u0000"
    head, tail = prompts.doctor_system_prompt(prompts.MAX_INFERENCES, 0, marker).split(marker)
    first = instruction.split(INSTRUCTION_END, 1)[0]
    if not (first.startswith(head) and first.endswith(tail)):
        raise ValueError("instruction does not start with the clinic doctor prompt")
    return first[len(head) : len(first) - len(tail)]


async def run_consultation(
    objective: str,
    chat: Callable[[str, str, str], str],
    say: Callable[[str], Awaitable[tuple[str, str]]],
    model: str,
    max_turns: int = prompts.MAX_INFERENCES,
) -> list[dict]:
    history = ""
    last_reply = ""
    transcript = []
    for turn in range(max_turns):
        system = prompts.doctor_system_prompt(max_turns, turn, objective)
        user = prompts.doctor_user_prompt(history, last_reply)
        try:
            utterance = await asyncio.to_thread(chat, model, system, user)
        except LLMError as exc:
            raise ApiConnectionError(f"doctor model call failed on turn {turn + 1}: {exc}") from exc
        history += last_reply + "\n\n" + utterance + "\n\n"
        status, reply = await say(utterance)
        if status not in DIALOGUE_STATUSES:
            raise RuntimeRequestError(f"clinic returned status {status} on turn {turn + 1}: {reply[:200]}")
        transcript.append({"turn": turn + 1, "system": system, "prompt": user, "doctor": utterance, "reply": reply})
        if prompts.DIAGNOSIS_READY in utterance:
            break
        last_reply = reply
    return transcript


class AgentClinicDoctorAgent(BaseAgent):
    capabilities = AgentCapabilities(mcp_servers=True)

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        clinic_url: str = "http://clinic:8000",
        python: str = "python3",
        clinic_timeout_sec: int = 960,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self.clinic_url = clinic_url
        self.python = python
        self.clinic_timeout_sec = int(clinic_timeout_sec)

    @staticmethod
    def name() -> str:
        return "agentclinic-doctor"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        return None

    def _doctor_model(self) -> str:
        if not self.model_name:
            raise ValueError("agentclinic-doctor needs a model, for example -m gpt-4o-mini")
        return self.model_name.split("/", 1)[1] if self.model_name.startswith("openai/") else self.model_name

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        objective = objective_from_instruction(instruction)
        chat = make_chat()
        gateway = ClinicGateway(environment, self.clinic_url, self.python, timeout_sec=self.clinic_timeout_sec)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.logs_dir / "doctor_transcript.json"
        model = self._doctor_model()
        transcript: list[dict] = []

        async def say(text: str) -> tuple[str, str]:
            status, reply = await gateway.post("ask_patient", text)
            transcript.append({"doctor": text, "status": status, "reply": reply})
            return status, reply

        try:
            turns = await run_consultation(objective, chat, say, model)
        finally:
            log_path.write_text(
                json.dumps({"model": model, "served_model": chat.last_model, "turns": transcript}, indent=2)
            )
            if context is not None:
                context.n_input_tokens = chat.usage["prompt_tokens"]
                context.n_output_tokens = chat.usage["completion_tokens"]
                context.metadata = {"doctor_model": model, "doctor_served_model": chat.last_model}
        log_path.write_text(json.dumps({"model": model, "served_model": chat.last_model, "turns": turns}, indent=2))
