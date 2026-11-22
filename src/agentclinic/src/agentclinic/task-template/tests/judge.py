import argparse
import json
import os
import sys
from pathlib import Path

import prompts
from llm import ChatClient

DEFAULT_MODERATOR_MODEL = "gpt-4o-mini"


class VerifierError(RuntimeError):
    pass


def make_chat() -> ChatClient:
    return ChatClient.from_env()


def grade(state: dict | None, case: dict, chat, moderator_model: str) -> dict:
    if state is None:
        raise VerifierError("no consultation state was collected from the clinic")
    if state.get("task_id") != case["task_id"]:
        raise VerifierError(f"state belongs to {state.get('task_id')!r}, expected {case['task_id']!r}")
    if state.get("sealed") is not True:
        raise VerifierError("the clinic did not seal its final state after the consultation")
    if state.get("simulator_unrecovered"):
        raise VerifierError(f"the simulator was failing when the consultation ended: {state.get('errors', [])[-1:]}")
    if state.get("state_unrecovered"):
        raise VerifierError("the clinic could not record a turn and never recovered")
    diagnosis = state.get("diagnosis")
    result = {
        "task_id": case["task_id"],
        "turns": state.get("turns"),
        "submitted_at_turn": state.get("submitted_at_turn"),
        "diagnosis": diagnosis,
        "correct_diagnosis": case["correct_diagnosis"],
        "moderator_model": moderator_model,
        "moderator_served_model": None,
        "moderator_reply": None,
        "correct": False,
        "reward": 0,
        "simulator_errors": state.get("errors", []),
        "simulator_served_models": state.get("served_models"),
        "restarts": state.get("restarts", 0),
    }
    if diagnosis is None:
        if state.get("pending") is not None:
            raise VerifierError("the consultation ended while a simulator call was still in flight")
        return result
    reply = chat(
        moderator_model,
        prompts.moderator_system_prompt(),
        prompts.moderator_user_prompt(case["correct_diagnosis"], diagnosis),
    )
    finish_reason = getattr(chat, "last_finish_reason", None)
    if finish_reason == "content_filter":
        raise VerifierError("the moderator reply was withheld by the provider (content_filter)")
    if not reply.strip():
        raise VerifierError("the moderator returned an empty reply")
    correct = prompts.moderator_is_correct(reply)
    result.update(
        {
            "moderator_reply": reply,
            "moderator_served_model": getattr(chat, "last_model", None),
            "moderator_finish_reason": finish_reason,
            "correct": correct,
            "reward": 1 if correct else 0,
        }
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--reward", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(argv)
    args.reward.parent.mkdir(parents=True, exist_ok=True)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    case = json.loads(args.case.read_text(encoding="utf-8"))
    state = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else None
    moderator_model = os.environ.get("AGENTCLINIC_MODERATOR_MODEL") or DEFAULT_MODERATOR_MODEL
    try:
        needs_moderator = state is not None and state.get("diagnosis") is not None
        result = grade(state, case, make_chat() if needs_moderator else None, moderator_model)
    except Exception as exc:
        args.result.write_text(
            json.dumps({"task_id": case["task_id"], "error": f"{type(exc).__name__}: {exc}"}, indent=2)
        )
        print(f"verifier error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    args.result.write_text(json.dumps(result, indent=2))
    args.reward.write_text(str(result["reward"]))
    print(json.dumps({"reward": result["reward"], "moderator_reply": result["moderator_reply"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
