import json
from pathlib import Path

import anyio
import pytest
from fastmcp import Client
from runtime_env import import_runtime, write_case
from starlette.testclient import TestClient
from upstream import ScriptedWorld

from agentclinic import prompts
from agentclinic.cases import load_cases

FIXTURE = Path(__file__).parent / "fixtures" / "medqa_ext_sample.jsonl"


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    server = import_runtime(tmp_path / "runtime")
    case_path = write_case(tmp_path / "case.json", load_cases(FIXTURE)[0])
    state_path = tmp_path / "logs" / "agentclinic_state.json"
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(case_path))
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(state_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    world = ScriptedWorld()
    mcp, clinic = server.build_from_env(llm=lambda model, system, user: world.reply(system, user))
    return server, mcp, clinic, state_path, world


def _call(mcp, tool, args=None):
    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool(tool, args or {})
            return result.content[0].text

    return anyio.run(run)


def test_lists_tools(runtime):
    _, mcp, _, _, _ = runtime

    async def run():
        async with Client(mcp) as client:
            return {tool.name for tool in await client.list_tools()}

    assert anyio.run(run) == {"ask_patient", "request_test", "submit_diagnosis", "get_status"}


def test_mcp_round_trip_writes_state(runtime):
    _, mcp, _, state_path, world = runtime
    assert _call(mcp, "ask_patient", {"question": "What brings you in?"}) == "Patient reply 1."
    assert _call(mcp, "request_test", {"test": "CBC"}) == "RESULTS: finding 1"
    assert (
        _call(mcp, "submit_diagnosis", {"diagnosis": "Myasthenia gravis"})
        == "Diagnosis recorded. The consultation is over."
    )
    state = json.loads(state_path.read_text())
    assert state["diagnosis"] == "DIAGNOSIS READY: Myasthenia gravis"
    assert state["turns"] == 3
    assert [c["role"] for c in world.calls] == ["patient", "measurement"]


def test_status_reports_counts_only(runtime):
    _, mcp, _, _, _ = runtime
    _call(mcp, "ask_patient", {"question": "Hi"})
    status = json.loads(_call(mcp, "get_status"))
    assert status == {
        "turns_used": 1,
        "max_turns": 20,
        "turns_remaining": 19,
        "consultation_over": False,
        "call_in_progress": False,
        "last_reply": "Patient reply 1.",
    }


def test_rest_api(runtime):
    _, mcp, _, state_path, _ = runtime
    with TestClient(mcp.http_app()) as http:
        assert http.get("/health").json() == {"ok": True}
        assert http.post("/api/ask_patient", json={"text": "Hi"}).json() == {
            "reply": "Patient reply 1.",
            "status": "ok",
        }
        assert http.post("/api/ask_patient", json={"text": "x" * 5000}).json()["status"] == "rejected"
        assert http.post("/api/submit_diagnosis", json={"text": "Myasthenia gravis"}).status_code == 200
        assert http.post("/api/drop_tables", json={"text": "x"}).status_code == 404
        assert http.post("/api/ask_patient", json={}).status_code == 400
    assert json.loads(state_path.read_text())["submitted_at_turn"] == 2


def test_rest_llm_failure_is_502_and_recorded(tmp_path, monkeypatch):
    server = import_runtime(tmp_path / "runtime")
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(write_case(tmp_path / "case.json", load_cases(FIXTURE)[0])))
    state_path = tmp_path / "logs" / "state.json"
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(state_path))

    def broken(model, system, user):
        raise RuntimeError("endpoint down")

    mcp, _ = server.build_from_env(llm=broken)
    with TestClient(mcp.http_app()) as http:
        response = http.post("/api/ask_patient", json={"text": "Hi"})
    assert response.status_code == 502
    assert "endpoint down" in json.loads(state_path.read_text())["errors"][0]


def test_builds_without_api_key_and_uses_env_models(tmp_path, monkeypatch):
    server = import_runtime(tmp_path / "runtime")
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(write_case(tmp_path / "case.json", load_cases(FIXTURE)[0])))
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(tmp_path / "logs" / "state.json"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AGENTCLINIC_PATIENT_MODEL", "model-p")
    monkeypatch.setenv("AGENTCLINIC_MEASUREMENT_MODEL", "model-m")
    seen = []
    mcp, clinic = server.build_from_env(llm=lambda model, system, user: seen.append(model) or "ok")
    clinic.ask_patient("Hi")
    clinic.request_test("CBC")
    assert seen == ["model-p", "model-m"]
    _, lazy_clinic = server.build_from_env()
    assert lazy_clinic.submit_diagnosis("x") == "Diagnosis recorded. The consultation is over."


def test_final_notice_reaches_mcp_reply(runtime):
    _, mcp, _, _, _ = runtime
    replies = [_call(mcp, "ask_patient", {"question": f"Q{i}"}) for i in range(19)]
    assert replies[-1].endswith(prompts.FINAL_NOTICE)


def test_errors_returned_to_agent_hide_provider_text(tmp_path, monkeypatch):
    server = import_runtime(tmp_path / "runtime")
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(write_case(tmp_path / "case.json", load_cases(FIXTURE)[0])))
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(tmp_path / "logs" / "state.json"))

    def leaky(model, system, user):
        raise RuntimeError("HTTP 400 echo: Diminished motor strength observed")

    mcp, _ = server.build_from_env(llm=leaky)
    with TestClient(mcp.http_app()) as http:
        body = http.post("/api/ask_patient", json={"text": "Hi"}).text
    assert "Diminished" not in body

    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool("ask_patient", {"question": "Hi"}, raise_on_error=False)
            return result.is_error, " ".join(getattr(c, "text", "") for c in result.content)

    is_error, text = anyio.run(run)
    assert is_error is True
    assert "Diminished" not in text and "unavailable" in text


def test_restart_resumes_existing_state(tmp_path, monkeypatch):
    case = load_cases(FIXTURE)[0]
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(write_case(tmp_path / "case.json", case)))
    state_path = tmp_path / "logs" / "state.json"
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(state_path))
    server = import_runtime(tmp_path / "runtime")
    _, clinic = server.build_from_env(llm=lambda *a: "reply")
    clinic.ask_patient("Q1")
    clinic.submit_diagnosis("Myasthenia gravis")
    _, restarted = server.build_from_env(llm=lambda *a: "reply")
    state = json.loads(state_path.read_text())
    assert state["diagnosis"] == "DIAGNOSIS READY: Myasthenia gravis" and state["turns"] == 2 and state["restarts"] == 1
    assert "already" in restarted.ask_patient("Q2").lower()


def test_rest_state_error_is_json_503(tmp_path, monkeypatch):
    server = import_runtime(tmp_path / "runtime")
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(write_case(tmp_path / "case.json", load_cases(FIXTURE)[0])))
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(tmp_path / "logs" / "state.json"))
    mcp, clinic = server.build_from_env(llm=lambda *a: "reply")

    def full_disk(state):
        raise OSError(28, "No space left on device")

    clinic._on_change = full_disk
    with TestClient(mcp.http_app()) as http:
        response = http.post("/api/submit_diagnosis", json={"text": "Myasthenia gravis"})
    assert response.status_code == 503
    assert "could not record" in response.json()["error"]


def test_state_file_is_world_readable(runtime):
    import stat

    _, mcp, _, state_path, _ = runtime
    _call(mcp, "ask_patient", {"question": "Hi"})
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o644


def test_sigusr1_seals_state_to_disk(runtime):
    import os
    import signal
    import time

    server, mcp, clinic, state_path, _ = runtime
    _call(mcp, "ask_patient", {"question": "Hi"})
    previous = signal.getsignal(signal.SIGUSR1)
    try:
        server.install_seal_handler(clinic, state_path)
        os.kill(os.getpid(), signal.SIGUSR1)
        for _ in range(100):
            state = json.loads(state_path.read_text())
            if state.get("sealed"):
                break
            time.sleep(0.02)
    finally:
        signal.signal(signal.SIGUSR1, previous)
    assert state["sealed"] is True and state["turns"] == 1


def test_seal_script_waits_for_sealed_state(tmp_path):
    import importlib.util

    script = Path(__file__).resolve().parents[1] / "src/agentclinic/task-template/environment/runtime/seal.py"
    spec = importlib.util.spec_from_file_location("seal_script", script)
    seal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seal)
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"sealed": False}))
    assert seal.wait_for_seal(path, timeout=0.2) is False
    path.write_text(json.dumps({"sealed": True}))
    assert seal.wait_for_seal(path, timeout=0.2) is True


def test_served_model_is_recorded_through_the_default_client(tmp_path, monkeypatch):
    server = import_runtime(tmp_path / "runtime")
    monkeypatch.setenv("AGENTCLINIC_CASE_PATH", str(write_case(tmp_path / "case.json", load_cases(FIXTURE)[0])))
    state_path = tmp_path / "logs" / "state.json"
    monkeypatch.setenv("AGENTCLINIC_STATE_PATH", str(state_path))

    class FakeClient:
        last_model = None

        def __call__(self, model, system, user):
            self.last_model = model + "-2024-07-18"
            return "Patient reply."

    monkeypatch.setattr(server.ChatClient, "from_env", classmethod(lambda cls: FakeClient()))
    _, clinic = server.build_from_env()
    clinic.ask_patient("Hi")
    clinic.request_test("CBC")
    served = json.loads(state_path.read_text())["served_models"]
    assert served == {"patient": "gpt-4o-mini-2024-07-18", "measurement": "gpt-4o-mini-2024-07-18"}
