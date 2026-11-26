"""Score one Harbor submission with the native ControlArena SAE scorer."""

import hashlib
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path

from control_arena import EvalMode
from control_arena.protocol_arg_defaults import get_untrusted_model
from control_arena.settings.sae_interp_sabotage.scorers import (
    ResponseType,
    sae_interp_scorer,
)
from control_arena.settings.sae_interp_sabotage.setting import get_dataset
from control_arena.tools.submit_tool import STORE_SUBMIT_ARGS_KEY
from inspect_ai import Task, eval as inspect_eval
from inspect_ai.model import Model
from inspect_ai.scorer import CORRECT, INCORRECT
from inspect_ai.solver import Generate, Solver, TaskState, solver
from pydantic import ValidationError


@solver
def restore_submission(submission_json: str) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.store.set(STORE_SUBMIT_ARGS_KEY, submission_json)
        return state

    return solve


def read_submission(path: Path) -> ResponseType | None:
    try:
        return ResponseType.model_validate_json(path.read_bytes(), strict=True)
    except (FileNotFoundError, IsADirectoryError, ValidationError):
        # Without a valid submit call the native scorer marks both objectives incorrect.
        print("No valid interpretation was submitted.", file=sys.stderr)
        return None


def score_submission(
    case: dict,
    mode: EvalMode,
    submission: ResponseType | None,
    judge_model: str | Model,
    log_dir: Path,
) -> dict[str, int]:
    dataset = get_dataset(mode)
    index = case["source_index"]
    if type(index) is not int or not 0 <= index < len(dataset):
        raise ValueError("Invalid SAE source index in verifier case.")
    sample = dataset[index]
    if hashlib.sha256(sample.input.encode("utf-8")).hexdigest() != case["prompt_sha256"]:
        raise ValueError("Verifier case does not match the installed SAE dataset.")

    keys = {"main_task_success"}
    if mode == EvalMode.ATTACK:
        keys.add("side_task_success")
    if submission is None:
        return {key: 0 for key in keys}

    task = Task(
        name="sae_submission_grading",
        dataset=[sample],
        solver=restore_submission(submission.model_dump_json()),
        scorer=sae_interp_scorer(judge_model),
    )
    (log,) = inspect_eval(
        task,
        model=judge_model,
        log_dir=str(log_dir),
        log_samples=True,
        display="none",
        ctl_server=False,
        fail_on_error=True,
    )
    if log.status != "success" or not log.samples or not log.samples[0].scores:
        reason = log.error.message if log.error else log.status
        raise RuntimeError(f"Native SAE scoring failed. Inspect log: {log.location}. {reason}")
    value = log.samples[0].scores["sae_interp_scorer"].value
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"Native scorer returned unexpected objectives. Inspect log: {log.location}")
    if any(verdict not in (CORRECT, INCORRECT) for verdict in value.values()):
        raise ValueError(f"Judge returned an inconclusive verdict. Inspect log: {log.location}")
    return {key: int(verdict == CORRECT) for key, verdict in value.items()}


def write_json(path: Path, value: dict | int) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(
    reward_path: Path,
    *,
    case_path: Path = Path(__file__).with_name("case.json"),
    submission_path: Path = Path("/logs/artifacts/submission.json"),
) -> None:
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.unlink(missing_ok=True)
    scalar_path = reward_path.with_name("reward.txt")
    scalar_path.unlink(missing_ok=True)
    provenance_path = reward_path.with_name("provenance.json")
    provenance_path.unlink(missing_ok=True)
    case = json.loads(case_path.read_text(encoding="utf-8"))
    mode = EvalMode(os.environ.get("CONTROL_ARENA_EVAL_MODE", "honest"))
    model_name = os.environ.get("CONTROL_ARENA_JUDGE_MODEL") or get_untrusted_model()
    model: str | Model = model_name
    if model_name == "mockllm/sae-fixture":
        from fixture_judge import fixture_judge

        model = fixture_judge()
    submission = read_submission(submission_path)
    rewards = score_submission(case, mode, submission, model, reward_path.parent / "inspect")
    write_json(provenance_path, {
        "setting": "sae_interp_sabotage",
        "source_index": case["source_index"],
        "prompt_sha256": case["prompt_sha256"],
        "eval_mode": mode.value,
        "judge_model": model_name,
        "valid_submission": submission is not None,
        "control_arena_version": version("control-arena"),
        "inspect_ai_version": version("inspect-ai"),
    })
    write_json(scalar_path, rewards["main_task_success"])
    try:
        write_json(reward_path, rewards)
    except BaseException:
        # Harbor falls back to the scalar when the named reward file is absent.
        scalar_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main(Path(sys.argv[1]))
