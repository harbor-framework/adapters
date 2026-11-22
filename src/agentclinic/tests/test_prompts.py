import json
from pathlib import Path

import pytest
from upstream import (
    Recorder,
    Transport,
    load_upstream,
    load_upstream_with_transport,
    upstream_source,
)

from agentclinic import prompts
from agentclinic.cases import load_cases

FIXTURE = Path(__file__).parent / "fixtures" / "medqa_ext_sample.jsonl"

pytestmark = pytest.mark.network


def _scenario(ns, index=0):
    row = json.loads(FIXTURE.read_text().splitlines()[index])
    return ns["ScenarioMedQAExtended"](row)


def test_patient_prompts_match_upstream():
    rec = Recorder(["I see double."])
    ns = load_upstream(rec)
    agent = ns["PatientAgent"](scenario=_scenario(ns), backend_str="gpt-4o-mini", bias_present="None")
    agent.add_hist("RESULTS: CK normal")
    agent.inference_patient("What brings you in?")
    case = load_cases(FIXTURE)[0]
    assert rec.calls[0]["system"] == prompts.patient_system_prompt(case.patient_information())
    assert rec.calls[0]["prompt"] == prompts.patient_user_prompt("RESULTS: CK normal\n\n", "What brings you in?")


def test_measurement_prompts_match_upstream():
    rec = Recorder(["RESULTS: positive"])
    ns = load_upstream(rec)
    agent = ns["MeasurementAgent"](scenario=_scenario(ns), backend_str="gpt-4o-mini")
    agent.add_hist("It started a month ago.")
    agent.inference_measurement("REQUEST TEST: Acetylcholine_Receptor_Antibodies")
    case = load_cases(FIXTURE)[0]
    assert rec.calls[0]["system"] == prompts.measurement_system_prompt(case.exam_information())
    assert rec.calls[0]["prompt"] == prompts.measurement_user_prompt(
        "It started a month ago.\n\n", "REQUEST TEST: Acetylcholine_Receptor_Antibodies"
    )


def test_doctor_prompts_match_upstream():
    rec = Recorder(["Hello, what brings you in?", "REQUEST TEST: CBC"])
    ns = load_upstream(rec)
    agent = ns["DoctorAgent"](scenario=_scenario(ns), backend_str="gpt-4o-mini", max_infs=20, bias_present="None")
    agent.inference_doctor("")
    agent.inference_doctor("I see double.")
    case = load_cases(FIXTURE)[0]
    assert rec.calls[0]["system"] == prompts.doctor_system_prompt(20, 0, case.examiner_information())
    assert rec.calls[0]["prompt"] == prompts.doctor_user_prompt("", "")
    assert rec.calls[1]["system"] == prompts.doctor_system_prompt(20, 1, case.examiner_information())
    assert rec.calls[1]["prompt"] == prompts.doctor_user_prompt("\n\nHello, what brings you in?\n\n", "I see double.")


def test_doctor_limit_message_matches_upstream():
    rec = Recorder([])
    ns = load_upstream(rec)
    agent = ns["DoctorAgent"](scenario=_scenario(ns), backend_str="gpt-4o-mini", max_infs=0, bias_present="None")
    assert agent.inference_doctor("x") == prompts.MAX_REACHED


def test_moderator_prompts_match_upstream():
    rec = Recorder(["Yes"])
    ns = load_upstream(rec)
    verdict = ns["compare_results"]("DIAGNOSIS READY: Myasthenia gravis", "Myasthenia gravis", "gpt-4o-mini", None)
    assert rec.calls[0]["system"] == prompts.moderator_system_prompt()
    assert rec.calls[0]["prompt"] == prompts.moderator_user_prompt(
        "Myasthenia gravis", "DIAGNOSIS READY: Myasthenia gravis"
    )
    assert (verdict == "yes") is prompts.moderator_is_correct("Yes")


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Yes", True),
        ("yes", True),
        ("YES", True),
        ("Yes.", False),
        ("yes, they match", False),
        ("No", False),
        ("Yes\n", False),
        ("\nYes", False),
    ],
)
def test_moderator_rule_matches_upstream(raw, expected):
    transport = Transport([], moderator_reply=raw)
    ns = load_upstream_with_transport(transport)
    upstream = ns["compare_results"]("d", "c", "gpt-4o-mini", None) == "yes"
    assert upstream is expected
    assert prompts.moderator_is_correct(raw) is expected


def test_constants_match_upstream_loop():
    source = upstream_source()
    assert f"pi_dialogue += {prompts.FINAL_NOTICE!r}".replace("'", '"') in source
    assert "default=20, required=False, help='Number of inferences between patient and doctor'" in source
    assert prompts.MAX_INFERENCES == 20
    gpt4o_mini = source.split('elif model_str == "gpt-4o-mini":')[2].split("elif")[0]
    assert f"temperature={prompts.TEMPERATURE}," in gpt4o_mini
    assert f"max_tokens={prompts.MAX_TOKENS}," in gpt4o_mini
    assert 're.sub("\\s+", " ", answer)' in gpt4o_mini


def test_normalize_response_collapses_whitespace():
    assert prompts.normalize_response("RESULTS:\n\n  CK   normal\n") == "RESULTS: CK normal "
