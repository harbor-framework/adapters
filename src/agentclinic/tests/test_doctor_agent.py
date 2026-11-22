import json
from pathlib import Path

import anyio
import pytest
from clinic_server import LocalEnvironment, RunningClinic
from runtime_env import import_runtime, write_case
from upstream import ScriptedWorld

from agentclinic import prompts
from agentclinic.adapter import AgentClinicAdapter
from agentclinic.agents.doctor import objective_from_instruction, run_consultation
from agentclinic.cases import load_cases

FIXTURE = Path(__file__).parent / "fixtures" / "medqa_ext_sample.jsonl"


class ScriptedDoctor:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, model, system, user):
        self.calls.append({"model": model, "system": system, "prompt": user})
        return prompts.normalize_response(self.script.pop(0))


def test_objective_from_instruction(tmp_path):
    paths = AgentClinicAdapter(tmp_path / "out", source=FIXTURE).run()
    for task, case in zip(paths, load_cases(FIXTURE)):
        assert objective_from_instruction((task / "instruction.md").read_text()) == case.objective


def test_objective_from_instruction_rejects_other_text():
    with pytest.raises(ValueError):
        objective_from_instruction("Solve this puzzle.")


def test_run_consultation_stops_after_diagnosis():
    said = []

    async def say(text):
        said.append(text)
        return "ok", "reply"

    doctor = ScriptedDoctor(["Hello?", "REQUEST TEST: CBC", "DIAGNOSIS READY: Flu", "never used"])
    transcript = anyio.run(run_consultation, "objective", doctor, say, "gpt-4o-mini")
    assert said == ["Hello?", "REQUEST TEST: CBC", "DIAGNOSIS READY: Flu"]
    assert len(transcript) == 3 and transcript[-1]["doctor"] == "DIAGNOSIS READY: Flu"
    assert {c["model"] for c in doctor.calls} == {"gpt-4o-mini"}


def test_run_consultation_uses_at_most_twenty_turns():
    async def say(text):
        return "ok", "reply"

    doctor = ScriptedDoctor([f"Q{i}" for i in range(30)])
    transcript = anyio.run(run_consultation, "objective", doctor, say, "m")
    assert len(transcript) == 20 and len(doctor.calls) == 20


def test_run_consultation_refuses_protocol_statuses_not_dialogue():
    from agentclinic.agents.errors import RuntimeRequestError

    async def busy(text):
        return "busy", "Busy: your previous turn is still being answered. No turn was used."

    with pytest.raises(RuntimeRequestError, match="busy"):
        anyio.run(run_consultation, "objective", ScriptedDoctor(["Hi"]), busy, "m")


def test_patient_dialogue_that_looks_like_a_status_is_accepted():
    async def say(text):
        return "ok", "Busy: I have been busy at work and tired."

    transcript = anyio.run(run_consultation, "objective", ScriptedDoctor(["Hi", "DIAGNOSIS READY: x"]), say, "m")
    assert transcript[0]["reply"].startswith("Busy:")


def test_doctor_model_failure_is_an_api_connection_error():
    from agentclinic.agents.errors import ApiConnectionError
    from agentclinic.llm import LLMError

    def broken(model, system, user):
        raise LLMError("chat completion failed after 30 attempts: HTTP 429")

    async def say(text):
        return "ok", "reply"

    with pytest.raises(ApiConnectionError):
        anyio.run(run_consultation, "objective", broken, say, "m")


def test_missing_doctor_key_is_an_authentication_error(monkeypatch):
    from agentclinic.agents import doctor as doctor_module
    from agentclinic.agents.errors import AgentAuthenticationError

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AgentAuthenticationError):
        doctor_module.make_chat()


def test_doctor_agent_end_to_end(tmp_path, monkeypatch):
    from agentclinic.agents import doctor as doctor_module
    from agentclinic.agents.doctor import AgentClinicDoctorAgent

    server = import_runtime(tmp_path / "runtime")
    case = load_cases(FIXTURE)[0]
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(write_case(tmp_path / "case.json", case)))
    state_path = tmp_path / "logs" / "consultation_state.json"
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(state_path))
    world = ScriptedWorld()
    mcp, _ = server.build_from_env(llm=lambda model, system, user: world.reply(system, user))
    scripted = ScriptedDoctor(["What brings you in?", "REQUEST TEST: CBC", "DIAGNOSIS READY: Myasthenia gravis"])
    scripted.usage = {"prompt_tokens": 120, "completion_tokens": 30}
    scripted.last_model = "gpt-4o-mini-2024-07-18"
    monkeypatch.setattr(doctor_module, "make_chat", lambda: scripted)
    instruction = (
        AgentClinicAdapter(tmp_path / "out", source=FIXTURE, limit=1).run()[0] / "instruction.md"
    ).read_text()
    context = type("Context", (), {"n_input_tokens": None, "n_output_tokens": None, "metadata": None})()
    with RunningClinic(mcp) as running:
        agent = AgentClinicDoctorAgent(
            logs_dir=tmp_path / "agent", model_name="openai/gpt-4o-mini", clinic_url=running.url
        )
        assert AgentClinicDoctorAgent.name() == "agentclinic-doctor" and agent.version() == "1.0.0"
        anyio.run(agent.run, instruction, LocalEnvironment(), context)
    state = json.loads(state_path.read_text())
    assert state["diagnosis"] == "DIAGNOSIS READY: Myasthenia gravis" and state["turns"] == 3
    assert scripted.calls[0]["system"] == prompts.doctor_system_prompt(20, 0, case.objective)
    assert {c["model"] for c in scripted.calls} == {"gpt-4o-mini"}
    saved = json.loads((tmp_path / "agent" / "doctor_transcript.json").read_text())
    assert [t["doctor"] for t in saved["turns"]] == [
        "What brings you in?",
        "REQUEST TEST: CBC",
        "DIAGNOSIS READY: Myasthenia gravis",
    ]
    assert (context.n_input_tokens, context.n_output_tokens) == (120, 30)
    assert context.metadata["doctor_served_model"] == "gpt-4o-mini-2024-07-18"
