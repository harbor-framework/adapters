import json
from pathlib import Path

import anyio
import pytest
from clinic_server import LocalEnvironment, RunningClinic
from runtime_env import import_runtime, write_case
from upstream import ScriptedWorld

from agentclinic.agents.errors import RuntimeRequestError
from agentclinic.agents.gateway import ClinicGateway
from agentclinic.cases import load_cases

FIXTURE = Path(__file__).parent / "fixtures" / "medqa_ext_sample.jsonl"


@pytest.fixture
def clinic(tmp_path, monkeypatch):
    server = import_runtime(tmp_path / "runtime")
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(write_case(tmp_path / "case.json", load_cases(FIXTURE)[0])))
    state_path = tmp_path / "logs" / "consultation_state.json"
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(state_path))
    world = ScriptedWorld()
    mcp, _ = server.build_from_env(llm=lambda model, system, user: world.reply(system, user))
    with RunningClinic(mcp) as running:
        yield running, state_path, world


def test_gateway_round_trip_through_container_python(clinic):
    running, state_path, _ = clinic
    env = LocalEnvironment()
    gateway = ClinicGateway(env, base_url=running.url, python="python3")
    assert anyio.run(gateway.post, "ask_patient", 'What brings you in? It\'s "bad".') == ("ok", "Patient reply 1.")
    assert anyio.run(gateway.post, "submit_diagnosis", "Myasthenia gravis") == (
        "submitted",
        "Diagnosis recorded. The consultation is over.",
    )
    assert anyio.run(gateway.post, "ask_patient", "Still there?")[0] == "ended"
    assert json.loads(state_path.read_text())["transcript"][0]["text"] == 'What brings you in? It\'s "bad".'
    assert all("python3" in c for c in env.commands)


def test_gateway_raises_on_infrastructure_errors(tmp_path, monkeypatch):
    server = import_runtime(tmp_path / "runtime")
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(write_case(tmp_path / "case.json", load_cases(FIXTURE)[0])))
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(tmp_path / "logs" / "s.json"))

    def broken(model, system, user):
        raise RuntimeError("down")

    mcp, _ = server.build_from_env(llm=broken)
    with RunningClinic(mcp) as running:
        gateway = ClinicGateway(LocalEnvironment(), base_url=running.url, python="python3")
        with pytest.raises(RuntimeRequestError, match="502"):
            anyio.run(gateway.post, "ask_patient", "Hi")


def test_gateway_raises_when_clinic_unreachable():
    gateway = ClinicGateway(LocalEnvironment(), base_url="http://127.0.0.1:9", python="python3", wait_sec=1)
    with pytest.raises(RuntimeRequestError):
        anyio.run(gateway.post, "ask_patient", "Hi")


def test_wrong_diagnosis_control_agent(clinic, tmp_path):
    from agentclinic.agents.controls import WRONG_DIAGNOSIS, WrongDiagnosisAgent

    running, state_path, world = clinic
    agent = WrongDiagnosisAgent(logs_dir=tmp_path / "agent-logs", clinic_url=running.url, python="python3")
    assert WrongDiagnosisAgent.name() == "agentclinic-wrong-diagnosis" and agent.version() == "1.0.0"
    anyio.run(agent.run, "instruction", LocalEnvironment(), None)
    state = json.loads(state_path.read_text())
    assert state["diagnosis"] == f"DIAGNOSIS READY: {WRONG_DIAGNOSIS}"
    assert state["turns"] == 1 and world.calls == []


@pytest.mark.parametrize(
    "path",
    ["agentclinic.agents.controls:WrongDiagnosisAgent", "agentclinic.agents.doctor:AgentClinicDoctorAgent"],
)
def test_agents_accept_tasks_with_mcp_servers(path):
    import importlib

    module, name = path.split(":")
    agent_class = getattr(importlib.import_module(module), name)
    assert agent_class.capabilities.mcp_servers is True
    assert agent_class.import_path() == path


def test_wrong_control_fails_unless_the_clinic_acknowledges_the_submission(tmp_path, monkeypatch):
    from agentclinic.agents import controls

    async def busy(self, action, text):
        return "busy", "Busy: your previous turn is still being answered."

    monkeypatch.setattr(controls.ClinicGateway, "post", busy)
    agent = controls.WrongDiagnosisAgent(logs_dir=tmp_path / "agent-logs")
    with pytest.raises(RuntimeRequestError, match="busy"):
        anyio.run(agent.run, "instruction", LocalEnvironment(), None)


def test_gateway_timeout_covers_upstream_like_retry_deadlines():
    from agentclinic.agents.doctor import AgentClinicDoctorAgent

    assert ClinicGateway(None).timeout_sec >= 960
    agent = AgentClinicDoctorAgent(logs_dir=Path("/tmp/x"), model_name="gpt-4o-mini", clinic_timeout_sec=1200)
    assert agent.clinic_timeout_sec == 1200
