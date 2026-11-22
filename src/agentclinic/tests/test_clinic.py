import json
from pathlib import Path

import pytest
from upstream import ScriptedWorld, run_upstream_consultation

from agentclinic import prompts
from agentclinic.cases import load_cases
from agentclinic.clinic import Clinic, ClinicLLMError

FIXTURE = Path(__file__).parent / "fixtures" / "medqa_ext_sample.jsonl"


def _clinic(world=None, on_change=None, llm=None):
    world = world or ScriptedWorld()
    case = load_cases(FIXTURE)[0]
    clinic = Clinic(
        case=case.runtime_view(),
        llm=llm or (lambda model, system, user: world.reply(system, user)),
        patient_model="gpt-4o-mini",
        measurement_model="gpt-4o-mini",
        on_change=on_change,
    )
    return clinic, world


def _drive(clinic, script):
    replies = []
    for utterance in script:
        replies.append(clinic.say(utterance))
        if clinic.snapshot()["diagnosis"] is not None:
            break
    return replies


SCRIPTS = {
    "mixed": [
        "Hello, what brings you in today?",
        "REQUEST TEST: Acetylcholine_Receptor_Antibodies",
        "When did the double\nvision start?",
        "REQUEST\nTEST: Chest_CT",
        "DIAGNOSIS READY: Myasthenia gravis",
    ],
    "never_diagnoses": [f"Question number {i}?" if i % 3 else f"REQUEST TEST: Test_{i}" for i in range(20)],
    "both_keywords": ["REQUEST TEST: CBC then DIAGNOSIS READY: Myasthenia gravis"],
    "diagnosis_on_last_turn": [f"Question {i}?" for i in range(19)] + ["DIAGNOSIS  READY:\tMyasthenia gravis"],
}


def reference_doctor_loop(clinic, objective, script):
    import anyio

    from agentclinic.agents.doctor import run_consultation

    calls = []
    queue = list(script)

    def doctor(model, system, user):
        calls.append({"system": system, "prompt": user})
        return prompts.normalize_response(queue.pop(0))

    async def say(text):
        return clinic.say_with_status(text)

    transcript = anyio.run(run_consultation, objective, doctor, say, "gpt-4o-mini")
    return calls, transcript[-1]["reply"]


@pytest.mark.network
@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_matches_upstream_loop(name, tmp_path):
    script = SCRIPTS[name]
    upstream = run_upstream_consultation(FIXTURE, script, tmp_path)
    clinic, world = _clinic()
    doctor_calls, last_reply = reference_doctor_loop(clinic, load_cases(FIXTURE)[0].examiner_information(), script)
    upstream_doctor = [{"system": c["system"], "prompt": c["prompt"]} for c in upstream.calls if c["role"] == "doctor"]
    upstream_sim = [
        {"role": c["role"], "system": c["system"], "prompt": c["prompt"]}
        for c in upstream.calls
        if c["role"] in ("patient", "measurement")
    ]
    assert doctor_calls == upstream_doctor
    assert [{"role": c["role"], "system": c["system"], "prompt": c["prompt"]} for c in world.calls] == upstream_sim
    assert {(c["temperature"], c["max_tokens"]) for c in upstream.calls} == {(prompts.TEMPERATURE, prompts.MAX_TOKENS)}
    moderator = [c for c in upstream.calls if c["role"] == "moderator"]
    diagnosis = clinic.snapshot()["diagnosis"]
    if moderator:
        assert moderator[0]["prompt"] == prompts.moderator_user_prompt("Myasthenia gravis", diagnosis)
    else:
        assert diagnosis is None
        last_upstream_sim = [c for c in upstream.calls if c["role"] in ("patient", "measurement")][-1]
        assert last_reply == prompts.normalize_response(last_upstream_sim["reply"])


def test_turn_budget():
    clinic, world = _clinic()
    for i in range(20):
        assert clinic.ask_patient(f"Question {i}?") != prompts.MAX_REACHED
    assert len(world.calls) == 20
    assert clinic.ask_patient("One more?") == prompts.MAX_REACHED
    assert clinic.submit_diagnosis("Myasthenia gravis") == prompts.MAX_REACHED
    assert len(world.calls) == 20
    state = clinic.snapshot()
    assert state["turns"] == 20 and state["diagnosis"] is None


def test_history_routing():
    clinic, world = _clinic()
    clinic.ask_patient("Q1")
    clinic.request_test("CBC")
    clinic.ask_patient("Q2")
    patient_calls = [c for c in world.calls if c["role"] == "patient"]
    measurement_calls = [c for c in world.calls if c["role"] == "measurement"]
    assert measurement_calls[0]["prompt"] == prompts.measurement_user_prompt(
        "Patient reply 1.\n\n", "REQUEST TEST: CBC"
    )
    assert patient_calls[1]["prompt"] == prompts.patient_user_prompt(
        "Q1\n\nPatient reply 1.\n\nRESULTS: finding 1\n\n", "Q2"
    )


def test_final_notice():
    clinic, _ = _clinic()
    replies = [clinic.ask_patient(f"Question {i}?") for i in range(20)]
    assert replies[18] == "Patient reply 19." + prompts.FINAL_NOTICE
    assert all(prompts.FINAL_NOTICE not in r for i, r in enumerate(replies) if i != 18)


def test_tool_wrappers_compose_upstream_utterances():
    clinic, world = _clinic()
    clinic.request_test("Chest_X-Ray")
    assert world.calls[-1]["prompt"].endswith("REQUEST TEST: Chest_X-Ray")
    clinic.request_test("Let me order one. REQUEST TEST: CBC")
    assert world.calls[-1]["prompt"].endswith("Let me order one. REQUEST TEST: CBC")
    clinic.submit_diagnosis("Myasthenia gravis")
    assert clinic.snapshot()["diagnosis"] == "DIAGNOSIS READY: Myasthenia gravis"


def test_ask_patient_with_keyword_routes_like_upstream():
    clinic, world = _clinic()
    clinic.ask_patient("REQUEST TEST: CBC")
    assert world.calls[-1]["role"] == "measurement"


def test_submit_once():
    clinic, world = _clinic()
    clinic.submit_diagnosis("Myasthenia gravis")
    reply = clinic.submit_diagnosis("Lambert-Eaton syndrome")
    assert "already" in reply.lower()
    assert clinic.ask_patient("Anything else?") == reply
    state = clinic.snapshot()
    assert state["diagnosis"] == "DIAGNOSIS READY: Myasthenia gravis"
    assert state["submitted_at_turn"] == 1 and state["turns"] == 1
    assert world.calls == []


def test_state_reported_after_each_call():
    seen = []
    clinic, _ = _clinic(on_change=lambda state: seen.append(json.loads(json.dumps(state))))
    clinic.ask_patient("Q1")
    clinic.request_test("CBC")
    clinic.submit_diagnosis("Myasthenia gravis")
    committed = [s for s in seen if s["pending"] is None]
    assert [s["turns"] for s in committed] == [1, 2, 3]
    assert [s["pending"]["role"] for s in seen if s["pending"]] == ["patient", "measurement"]
    assert [t["role"] for t in seen[-1]["transcript"]] == ["doctor", "patient", "doctor", "measurement", "doctor"]
    assert seen[-1]["task_id"] == "medqa-ext-000" and seen[-1]["max_turns"] == 20


def test_llm_error_raises_and_is_recorded():
    def broken(model, system, user):
        raise RuntimeError("upstream 503")

    seen = []
    clinic, _ = _clinic(llm=broken, on_change=seen.append)
    with pytest.raises(ClinicLLMError):
        clinic.ask_patient("Q1")
    state = clinic.snapshot()
    assert state["errors"] and "503" in state["errors"][0]
    assert state["turns"] == 0
    assert seen and seen[-1]["errors"]


def test_runtime_view_hides_diagnosis():
    view = load_cases(FIXTURE)[0].runtime_view()
    assert "Myasthenia" not in json.dumps(view)
    assert set(view) == {"task_id", "objective", "patient_actor", "physical_exam", "test_results"}


def test_doctor_text_is_normalized_like_upstream_before_routing():
    clinic, world = _clinic()
    clinic.ask_patient("REQUEST\nTEST: CBC")
    assert world.calls[-1]["role"] == "measurement"
    assert world.calls[-1]["prompt"].endswith("REQUEST TEST: CBC")
    clinic.ask_patient("I think\tthis is it.\n\nDIAGNOSIS\tREADY: Myasthenia   gravis")
    assert clinic.snapshot()["diagnosis"] == "I think this is it. DIAGNOSIS READY: Myasthenia gravis"


def test_wrapper_prefix_check_uses_normalized_text():
    clinic, _ = _clinic()
    clinic.submit_diagnosis("DIAGNOSIS\nREADY: Myasthenia gravis")
    assert clinic.snapshot()["diagnosis"] == "DIAGNOSIS READY: Myasthenia gravis"


def test_llm_error_message_to_doctor_hides_provider_text():
    secret = "SECRET-PROMPT-ECHO"

    def leaky(model, system, user):
        raise RuntimeError(f"HTTP 400: invalid request near '{secret}'")

    clinic, _ = _clinic(llm=leaky)
    with pytest.raises(ClinicLLMError) as exc:
        clinic.ask_patient("Q1")
    assert secret not in str(exc.value)
    assert "patient" in str(exc.value)
    assert secret in clinic.snapshot()["errors"][0]


def test_failed_persist_rolls_back_the_turn():
    from agentclinic.clinic import ClinicStateError

    fail = {"on": True}

    def persist(state):
        if fail["on"] and state["diagnosis"]:
            raise OSError(28, "No space left on device")

    clinic, _ = _clinic(on_change=persist)
    clinic.ask_patient("Q1")
    with pytest.raises(ClinicStateError):
        clinic.submit_diagnosis("Myasthenia gravis")
    assert clinic.snapshot()["diagnosis"] is None and clinic.snapshot()["turns"] == 1
    fail["on"] = False
    assert clinic.submit_diagnosis("Myasthenia gravis") == "Diagnosis recorded. The consultation is over."
    assert clinic.snapshot()["submitted_at_turn"] == 2


def test_pending_call_is_persisted_and_status_does_not_block():
    import threading

    release = threading.Event()
    entered = threading.Event()
    persisted = []

    def slow(model, system, user):
        entered.set()
        release.wait(5)
        return "Patient reply."

    clinic, _ = _clinic(llm=slow, on_change=persisted.append)
    worker = threading.Thread(target=clinic.ask_patient, args=("Q1",))
    worker.start()
    assert entered.wait(5)
    during = []
    probe = threading.Thread(target=lambda: during.append(clinic.snapshot()))
    probe.start()
    probe.join(1)
    assert during, "snapshot blocked while the simulator call was in flight"
    assert during[0]["pending"]["role"] == "patient" and during[0]["turns"] == 0
    assert persisted[-1]["pending"]["role"] == "patient"
    release.set()
    worker.join(5)
    assert clinic.snapshot()["pending"] is None and clinic.snapshot()["turns"] == 1


def test_resume_from_saved_state_keeps_budget_and_histories():
    first, world = _clinic()
    for i in range(3):
        first.ask_patient(f"Q{i}")
    saved = json.loads(json.dumps(first.snapshot()))
    case = load_cases(FIXTURE)[0]
    resumed = Clinic(
        case=case.runtime_view(),
        llm=lambda model, system, user: world.reply(system, user),
        patient_model="gpt-4o-mini",
        measurement_model="gpt-4o-mini",
        initial_state=saved,
    )
    reference, reference_world = _clinic()
    for i in range(4):
        reference.ask_patient(f"Q{i}")
    resumed.ask_patient("Q3")
    assert resumed.snapshot()["turns"] == 4
    assert world.calls[-1]["prompt"] == reference_world.calls[-1]["prompt"]
    assert resumed.snapshot()["restarts"] == 1


def test_resume_after_submission_stays_closed():
    first, _ = _clinic()
    first.submit_diagnosis("Myasthenia gravis")
    resumed = Clinic(
        case=load_cases(FIXTURE)[0].runtime_view(),
        llm=lambda *a: "x",
        patient_model="m",
        measurement_model="m",
        initial_state=first.snapshot(),
    )
    assert "already" in resumed.ask_patient("Hello again").lower()
    assert resumed.snapshot()["diagnosis"] == "DIAGNOSIS READY: Myasthenia gravis"


def test_overlong_utterance_is_rejected_without_using_a_turn():
    clinic, world = _clinic()
    reply = clinic.submit_diagnosis("; ".join(f"Disease {i}" for i in range(3000)))
    assert "too long" in reply.lower()
    assert clinic.ask_patient("x" * (prompts.MAX_UTTERANCE_CHARS + 1)).lower().startswith("rejected")
    state = clinic.snapshot()
    assert state["turns"] == 0 and state["diagnosis"] is None and world.calls == []
    assert clinic.ask_patient("y" * prompts.MAX_UTTERANCE_CHARS) == "Patient reply 1."


def test_concurrent_call_is_refused_as_busy_without_using_a_turn():
    import threading

    release = threading.Event()
    entered = threading.Event()

    def slow(model, system, user):
        entered.set()
        release.wait(5)
        return "Patient reply."

    clinic, _ = _clinic(llm=slow)
    worker = threading.Thread(target=clinic.ask_patient, args=("When did it start?",))
    worker.start()
    assert entered.wait(5)
    second = clinic.ask_patient("When did it start?")
    assert "busy" in second.lower() and "no turn" in second.lower()
    release.set()
    worker.join(5)
    state = clinic.snapshot()
    assert state["turns"] == 1
    assert [t["text"] for t in state["transcript"]] == ["When did it start?", "Patient reply."]
    assert state["last_reply"] == "Patient reply."


def test_state_records_models():
    clinic, _ = _clinic()
    assert clinic.snapshot()["models"] == {"patient": "gpt-4o-mini", "measurement": "gpt-4o-mini"}


def _chat_client_over(world, monkeypatch):
    import io

    from agentclinic import llm

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        messages = json.loads(request.data)["messages"]
        content = world.reply(messages[0]["content"], messages[1]["content"])
        return Response(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    return llm.ChatClient(base_url="http://simulator.test/v1", api_key="k", retry_sleep=0)


@pytest.mark.network
@pytest.mark.parametrize("name", ["mixed", "never_diagnoses"])
def test_matches_upstream_end_to_end_with_messy_replies(name, tmp_path, monkeypatch):
    script = SCRIPTS[name]
    upstream = run_upstream_consultation(FIXTURE, script, tmp_path, messy=True)
    world = ScriptedWorld(messy=True)
    clinic, _ = _clinic(world=world, llm=_chat_client_over(world, monkeypatch))
    doctor_calls, last_reply = reference_doctor_loop(clinic, load_cases(FIXTURE)[0].examiner_information(), script)
    upstream_doctor = [{"system": c["system"], "prompt": c["prompt"]} for c in upstream.calls if c["role"] == "doctor"]
    upstream_sim = [
        {"role": c["role"], "system": c["system"], "prompt": c["prompt"]}
        for c in upstream.calls
        if c["role"] in ("patient", "measurement")
    ]
    assert doctor_calls == upstream_doctor
    assert [{"role": c["role"], "system": c["system"], "prompt": c["prompt"]} for c in world.calls] == upstream_sim
    assert "  " not in clinic.snapshot()["patient_history"].replace("\n\n", "")


@pytest.mark.parametrize(
    "steps, status",
    [
        (["Hi"], "ok"),
        (["DIAGNOSIS READY: x"], "submitted"),
        (["DIAGNOSIS READY: x", "Hi"], "ended"),
        (["z" * (prompts.MAX_UTTERANCE_CHARS + 1)], "rejected"),
    ],
)
def test_say_with_status(steps, status):
    clinic, _ = _clinic()
    for text in steps:
        result = clinic.say_with_status(text)
    assert result[0] == status


def test_status_after_budget_is_max_reached():
    clinic, _ = _clinic()
    for i in range(20):
        clinic.ask_patient(f"Q{i}")
    assert clinic.say_with_status("Q21") == ("max_reached", prompts.MAX_REACHED)


def test_two_hundred_token_doctor_lines_are_never_rejected():
    assert prompts.MAX_UTTERANCE_CHARS >= 2000


def _flaky(fail_first):
    calls = {"n": 0}

    def llm(model, system, user):
        calls["n"] += 1
        if calls["n"] <= fail_first:
            raise RuntimeError("503 from provider")
        return "Patient reply."

    return llm


def test_simulator_error_is_unrecovered_until_a_simulator_reply_succeeds():
    clinic, _ = _clinic(llm=_flaky(1))
    with pytest.raises(ClinicLLMError):
        clinic.ask_patient("Q1")
    assert clinic.snapshot()["simulator_unrecovered"] is True
    clinic.ask_patient("Q1")
    assert clinic.snapshot()["simulator_unrecovered"] is False


def test_diagnosis_does_not_clear_a_simulator_outage():
    clinic, _ = _clinic(llm=_flaky(5))
    with pytest.raises(ClinicLLMError):
        clinic.ask_patient("Q1")
    clinic.submit_diagnosis("A guess")
    state = clinic.snapshot()
    assert state["diagnosis"] and state["simulator_unrecovered"] is True


def test_persist_failure_is_unrecovered_until_a_later_commit():
    from agentclinic.clinic import ClinicStateError

    fail = {"on": True}

    def persist(state):
        if fail["on"] and state["pending"] is None:
            raise OSError(28, "No space left on device")

    clinic, _ = _clinic(on_change=persist)
    with pytest.raises(ClinicStateError):
        clinic.ask_patient("Q1")
    assert clinic.snapshot()["state_unrecovered"] is True and clinic.snapshot()["persist_failures"] == 1
    fail["on"] = False
    clinic.ask_patient("Q1")
    assert clinic.snapshot()["state_unrecovered"] is False and clinic.snapshot()["persist_failures"] == 1


def test_seal_closes_the_consultation():
    clinic, world = _clinic()
    clinic.ask_patient("Q1")
    sealed = clinic.seal()
    assert sealed["sealed"] is True and sealed["turns"] == 1
    assert clinic.say_with_status("Q2")[0] == "closed"
    assert len(world.calls) == 1 and clinic.snapshot()["sealed"] is True


def test_resume_with_a_lost_in_flight_call_is_unrecovered():
    first, _ = _clinic()
    first.ask_patient("Q1")
    saved = first.snapshot()
    saved["pending"] = {"role": "patient", "started_at": 0}
    resumed = Clinic(
        case=load_cases(FIXTURE)[0].runtime_view(),
        llm=lambda *a: "Patient reply.",
        patient_model="m",
        measurement_model="m",
        initial_state=saved,
    )
    assert resumed.snapshot()["simulator_unrecovered"] is True and resumed.snapshot()["pending"] is None
    resumed.ask_patient("Q2")
    assert resumed.snapshot()["simulator_unrecovered"] is False
