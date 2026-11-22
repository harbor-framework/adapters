from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest
from bizagentbench.runtime import Mailbox, sse_chunk, public_response
from bizagentbench.source import UPSTREAM_COMMIT
from conftest import SOURCE

GRADER_PATH = Path(__file__).resolve().parents[1] / "src/bizagentbench/task-template/tests/grade.py"
spec = importlib.util.spec_from_file_location("isolated_grader", GRADER_PATH)
grader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grader)


def test_mailbox_rejects_duplicate_stale_and_role_injection():
    mailbox = Mailbox()
    mailbox.offer({"messages": [{"role": "user", "content": "Public text"}]})
    view = mailbox.view()
    with pytest.raises(ValueError, match="Stale"):
        mailbox.respond({"turn_id": "fake", "body": {}})
    mailbox.respond({"turn_id": view["turn_id"], "body": {"choices": []}})
    with pytest.raises(ValueError, match="duplicate"):
        mailbox.respond({"turn_id": view["turn_id"], "body": {}})
    # Public payloads only fill the assistant provider response; there is no
    # world, contract, actor, seed or score field applied by the mailbox.
    assert not hasattr(mailbox, "world")


def test_untrusted_public_interface_cannot_forge_provider_failures():
    for payload in (
        {"turn_id": "t", "status": 401, "body": {"error": "fake"}},
        {"turn_id": "t", "message": {}, "status": 401},
        {"turn_id": "t", "message": {}, "world": {"success": True}},
        {"turn_id": "t", "message": {}, "body": {"sse": "bad"}},
    ):
        with pytest.raises(ValueError, match="only an assistant message"):
            public_response(payload)
    result = public_response({"turn_id": "t", "message": {"content": "A final reply"}})
    assert "status" not in result and "model" not in result["body"]
    # The trusted relay still preserves non-object JSON error bodies from a real
    # provider; only the public route is forbidden from reporting such statuses.
    mailbox = Mailbox()
    mailbox.offer({"model": "fixture"})
    mailbox.respond({"turn_id": mailbox.view()["turn_id"], "status": 401, "body": ["denied"]})
    assert mailbox.answer == (401, ["denied"])


def test_sse_reconstruction_preserves_native_message_and_usage():
    from payment.runtime.products.evidence.stream_transport import assemble
    message = {"role": "assistant", "content": "Please review.", "tool_calls": [{
        "id": "test", "type": "function", "function": {"name": "get_clock", "arguments": "{}"},
    }], "reasoning_content": "Check current time."}
    body = {"model": "fixture", "id": "completion", "choices": [{"message": message, "finish_reason": "tool_calls"}],
            "usage": {"total_tokens": 3}}
    rebuilt = assemble([sse_chunk(body)])
    assert rebuilt["choices"][0]["message"] == message
    assert rebuilt["usage"] == body["usage"]


def test_upstream_httpagent_uses_customer_stop_not_assistant_stop_text():
    from payment.runtime.interaction.tau.llm import HTTPAgent
    from tau2.data_model.message import AssistantMessage, UserMessage
    from tau2.user.user_simulator import UserSimulator
    assert HTTPAgent.is_stop(AssistantMessage(role="assistant", content="###STOP###")) is False
    assert UserSimulator.is_stop(UserMessage(role="user", content="###STOP###")) is True


@pytest.mark.parametrize("number", range(1, 51))
def test_all_native_contracts_load_and_initial_verdict_is_not_success(number):
    from payment.runtime.tasks.contracts import read_contract
    from payment.runtime.core.factory import make_engine
    from payment.runtime.evaluation.runner import verify
    contract = read_contract(f"case_{number:03}", SOURCE / "payment/data")
    world = deepcopy(contract["initial_world"])
    result = make_engine(world, contract["engine_profile"], SOURCE / "payment/data").call("assistant", "get_clock")
    assert result["ok"]
    assert verify(world, contract)["strict_success"] is False


def test_grader_recomputes_native_and_preserves_infra_errors():
    from payment.runtime.tasks.contracts import read_contract
    from payment.runtime.evaluation.runner import verify
    task = "case_031"
    contract = read_contract(task, SOURCE / "payment/data")
    world = deepcopy(contract["initial_world"])
    verdict = verify(world, contract)
    source = {"task_id": task, "commit": UPSTREAM_COMMIT, "archive_sha256": "fixture"}
    evidence = {"schema_version": 1, "task_id": task, "upstream_commit": UPSTREAM_COMMIT,
                "archive_sha256": "fixture", "world": world, "result": {
                    "task_id": task, "verification": verdict, "reward": 0,
                    "classification": "failure"}}
    assert grader.grade(evidence, source, SOURCE)[0] == 0
    forged = deepcopy(evidence)
    forged["result"]["reward"] = 1
    with pytest.raises(ValueError, match="Strict"):
        grader.grade(forged, source, SOURCE)
    forged = deepcopy(evidence)
    forged["task_id"] = "case_032"
    with pytest.raises(ValueError, match="identity"):
        grader.grade(forged, source, SOURCE)
    forged = deepcopy(evidence)
    forged["result"].update(reward=None, classification="infrastructure_invalid")
    with pytest.raises(ValueError, match="infrastructure_invalid"):
        grader.grade(forged, source, SOURCE)


def test_grader_compares_complete_json_verdict_without_tuple_false_mismatch(monkeypatch):
    import payment.runtime.evaluation.runner as native
    verdict = {"strict_success": True, "source_checks": [{
        "id": "settlement", "passed": True,
        "evidence": {"payments": [(3, -6500, 1)]},
    }]}
    monkeypatch.setattr(native, "verify", lambda world, contract: verdict)
    source = {"task_id": "case_021", "commit": UPSTREAM_COMMIT, "archive_sha256": "fixture"}
    evidence = {"schema_version": 1, "task_id": "case_021", "upstream_commit": UPSTREAM_COMMIT,
                "archive_sha256": "fixture", "world": {}, "result": {
                    "task_id": "case_021", "verification": json.loads(json.dumps(verdict)),
                    "reward": 1.0, "classification": "success"}}
    assert grader.grade(evidence, source, SOURCE)[0] == 1.0
    forged = deepcopy(evidence)
    forged["result"]["verification"]["source_checks"][0]["evidence"]["payments"][0][1] = -6501
    with pytest.raises(ValueError, match="scoring mismatch"):
        grader.grade(forged, source, SOURCE)
