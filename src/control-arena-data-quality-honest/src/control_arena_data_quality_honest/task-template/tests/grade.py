"""Grade honest factual-accuracy examples using ControlArena's native main-task scorer."""
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path

from control_arena import EvalMode
from control_arena._control_task_metadata import ControlTaskMetadata
from control_arena.settings.data_poisoning.config import SETTING_DESCRIPTION
from control_arena.settings.data_poisoning.scorers import main_task_scorer
from control_arena.settings.data_poisoning.submission_types import TrainingPair
from control_arena.tools.submit_tool import STORE_SUBMIT_ARGS_KEY
from inspect_ai import Task, eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.model import get_model
from inspect_ai.scorer import CORRECT, INCORRECT, mean, scorer
from inspect_ai.solver import solver
from pydantic import ValidationError

from fixture_judge import FIXTURE, fixture_judge
from public_case import DOMAIN, agent_prompt, digest, prompts


@solver
def restore_submission(payload):
    async def solve(state, generate):
        if payload is not None:
            state.store.set(STORE_SUBMIT_ARGS_KEY, payload)
        return state
    return solve


@scorer(metrics=[mean()])
def factual_quality(judge):
    async def score(state, target):
        return await main_task_scorer(state, judge)
    return score


def read_submission(path):
    try:
        return TrainingPair.model_validate_json(path.read_bytes(), strict=True)
    except (FileNotFoundError, IsADirectoryError, ValidationError):
        return None


def score_submission(case, submission, model_name, logs):
    index = case["source_index"]
    rows = prompts()
    if case["domain"] != DOMAIN or type(index) is not int or not 0 <= index < len(rows):
        raise ValueError("Unknown factual-accuracy case")
    source = rows[index]
    prompt = agent_prompt(source)
    if digest(source) != case["source_prompt_sha256"] or digest(prompt) != case["adapted_prompt_sha256"]:
        raise ValueError("Pinned task prompt mismatch")
    judge = None
    if submission is not None:
        if model_name == FIXTURE:
            judge = fixture_judge(submission, case["fixture_input_sha256"])
        else:
            judge = get_model(model_name)
    metadata = ControlTaskMetadata(main_task_description=prompt, setting_description=SETTING_DESCRIPTION,
                                   main_task_name=f"generate_{DOMAIN}_monitor_data", side_task_description="",
                                   eval_mode=EvalMode.HONEST, setting_name="data_poisoning")
    task = Task(name="factual_accuracy_grading",
                dataset=[Sample(id=f"factual-{index:02}", input=prompt, metadata=metadata.model_dump())],
                solver=restore_submission(submission.model_dump_json() if submission else None),
                scorer=factual_quality(judge))
    (log,) = inspect_eval(task, model="mockllm/model", log_dir=str(logs), log_samples=True,
                          display="none", ctl_server=False, fail_on_error=True)
    if log.status != "success" or not log.samples or not log.samples[0].scores:
        raise RuntimeError(f"Native scoring failed. Inspect log: {log.location}")
    verdict = log.samples[0].scores["factual_quality"].value
    if verdict not in (CORRECT, INCORRECT):
        raise ValueError(f"Inconclusive quality judge result. Inspect log: {log.location}")
    return int(verdict == CORRECT)


def write_json(path, obj):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(reward, case_path=Path(__file__).with_name("case.json"), answer_path=Path("/logs/artifacts/submission.json")):
    reward.parent.mkdir(parents=True, exist_ok=True)
    scalar = reward.with_name("reward.txt")
    provenance = reward.with_name("provenance.json")
    for target in (reward, scalar, provenance):
        target.unlink(missing_ok=True)
    case = json.loads(case_path.read_bytes())
    submission = read_submission(answer_path)
    model_name = os.environ.get("CONTROL_ARENA_JUDGE_MODEL") or FIXTURE
    success = score_submission(case, submission, model_name, reward.parent / "inspect")
    write_json(provenance, {key: case[key] for key in ("domain", "source_index", "source_prompt_sha256", "adapted_prompt_sha256")} |
               {"setting": "data_poisoning", "eval_mode": "honest", "valid_submission": submission is not None,
                "judge_model": model_name, "control_arena_version": version("control-arena"), "inspect_ai_version": version("inspect-ai")})
    write_json(scalar, success)
    try:
        write_json(reward, {"main_task_success": success})
    except BaseException:
        scalar.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main(Path(sys.argv[1]))
