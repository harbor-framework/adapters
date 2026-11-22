import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from agentclinic import prompts

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / "agentclinic"
TESTS_TEMPLATE = PACKAGE_DIR / "task-template" / "tests"
CASE = {"task_id": "medqa-ext-000", "correct_diagnosis": "Myasthenia gravis"}


@pytest.fixture
def judge(tmp_path):
    target = tmp_path / "tests"
    target.mkdir()
    for name in ("prompts", "llm"):
        shutil.copy(PACKAGE_DIR / f"{name}.py", target / f"{name}.py")
    shutil.copy(TESTS_TEMPLATE / "judge.py", target / "judge.py")
    for name in ("prompts", "llm", "judge"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(target))
    try:
        yield importlib.import_module("judge")
    finally:
        sys.path.remove(str(target))
        for name in ("prompts", "llm", "judge"):
            sys.modules.pop(name, None)


def _state(**overrides):
    state = {
        "task_id": "medqa-ext-000",
        "turns": 4,
        "max_turns": 20,
        "transcript": [],
        "diagnosis": "DIAGNOSIS READY: Myasthenia gravis",
        "submitted_at_turn": 4,
        "errors": [],
        "pending": None,
        "restarts": 0,
        "sealed": True,
        "simulator_unrecovered": False,
        "state_unrecovered": False,
        "persist_failures": 0,
    }
    state.update(overrides)
    return state


class FakeChat:
    def __init__(self, reply="Yes", fail=False):
        self.reply = reply
        self.fail = fail
        self.calls = []
        self.last_model = "gpt-4o-mini-2024-07-18"
        self.last_finish_reason = "stop"

    def __call__(self, model, system, user):
        self.calls.append((model, system, user))
        if self.fail:
            raise RuntimeError("moderator endpoint down")
        return self.reply


def test_correct_diagnosis_scores_one(judge):
    chat = FakeChat("Yes")
    result = judge.grade(_state(), CASE, chat, "gpt-4o-mini")
    assert result["reward"] == 1 and result["correct"] is True
    assert chat.calls == [
        (
            "gpt-4o-mini",
            prompts.moderator_system_prompt(),
            prompts.moderator_user_prompt("Myasthenia gravis", "DIAGNOSIS READY: Myasthenia gravis"),
        )
    ]
    assert result["moderator_reply"] == "Yes" and result["moderator_served_model"] == "gpt-4o-mini-2024-07-18"


@pytest.mark.parametrize("reply, reward", [("yes", 1), ("Yes.", 0), ("No", 0), ("yes, same disease", 0)])
def test_moderator_rule(judge, reply, reward):
    assert judge.grade(_state(), CASE, FakeChat(reply), "gpt-4o-mini")["reward"] == reward


def test_no_diagnosis_scores_zero_without_calling_moderator(judge):
    chat = FakeChat()
    result = judge.grade(_state(diagnosis=None, submitted_at_turn=None, turns=20), CASE, chat, "gpt-4o-mini")
    assert result["reward"] == 0 and chat.calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"sealed": False},
        {"diagnosis": None, "pending": {"role": "patient", "started_at": 0}},
        {"simulator_unrecovered": True},
        {"diagnosis": None, "simulator_unrecovered": True},
        {"state_unrecovered": True},
        {"task_id": "medqa-ext-001"},
    ],
)
def test_infrastructure_problems_are_verifier_errors(judge, overrides):
    with pytest.raises(judge.VerifierError):
        judge.grade(_state(**overrides), CASE, FakeChat(), "gpt-4o-mini")


def test_recovered_errors_and_restarts_are_still_graded(judge):
    state = _state(errors=["patient: LLMError: blip"], restarts=1)
    assert judge.grade(state, CASE, FakeChat("Yes"), "gpt-4o-mini")["reward"] == 1
    no_diagnosis = _state(
        diagnosis=None, submitted_at_turn=None, turns=20, errors=["patient: LLMError: blip"], restarts=1
    )
    assert judge.grade(no_diagnosis, CASE, FakeChat(), "gpt-4o-mini")["reward"] == 0


@pytest.mark.parametrize("reply", ["", " "])
def test_empty_moderator_reply_is_a_verifier_error(judge, reply):
    with pytest.raises(judge.VerifierError, match="moderator"):
        judge.grade(_state(), CASE, FakeChat(reply), "gpt-4o-mini")


def test_filtered_moderator_reply_is_a_verifier_error(judge):
    chat = FakeChat("Yes")
    chat.last_finish_reason = "content_filter"
    with pytest.raises(judge.VerifierError, match="content_filter"):
        judge.grade(_state(), CASE, chat, "gpt-4o-mini")


def _run_main(judge, tmp_path, state, chat, monkeypatch):
    state_path = tmp_path / "logs" / "consultation_state.json"
    if state is not None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state))
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(CASE))
    reward = tmp_path / "verifier" / "reward.txt"
    result = tmp_path / "verifier" / "result.json"
    monkeypatch.setattr(judge, "make_chat", lambda: chat)
    code = judge.main(
        ["--state", str(state_path), "--case", str(case_path), "--reward", str(reward), "--result", str(result)]
    )
    return code, reward, result


def test_main_writes_reward_and_result(judge, tmp_path, monkeypatch):
    code, reward, result = _run_main(judge, tmp_path, _state(), FakeChat("Yes"), monkeypatch)
    assert code == 0 and reward.read_text() == "1"
    assert json.loads(result.read_text())["correct_diagnosis"] == "Myasthenia gravis"


def test_main_moderator_failure_leaves_no_reward(judge, tmp_path, monkeypatch):
    code, reward, result = _run_main(judge, tmp_path, _state(), FakeChat(fail=True), monkeypatch)
    assert code != 0 and not reward.exists()
    assert "moderator endpoint down" in json.loads(result.read_text())["error"]


def test_main_missing_state_leaves_no_reward(judge, tmp_path, monkeypatch):
    code, reward, _ = _run_main(judge, tmp_path, None, FakeChat(), monkeypatch)
    assert code != 0 and not reward.exists()


def test_test_sh_clears_stale_reward_and_calls_judge():
    script = (TESTS_TEMPLATE / "test.sh").read_text()
    assert "rm -f /logs/verifier/reward.txt" in script
    assert "/root/logs/consultation_state.json" in script and "/tests/judge.py" in script


def test_make_chat_uses_env(judge, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("AGENTCLINIC_LLM_DEADLINE", "240")
    chat = judge.make_chat()
    assert chat.api_key == "sk-test" and chat.deadline == 240.0
