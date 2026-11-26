"""Check the generated honest packets with ControlArena's main scorer in native Inspect Docker."""

import argparse
import json
from importlib.metadata import distribution
from pathlib import Path

from control_arena import ControlTaskMetadata, EvalMode
from control_arena.settings.apps.task.metadata import AppsTaskMetadata
from control_arena.settings.apps.task.scorers import main_task_success
from control_arena.tools.submit_tool import STORE_SUBMIT_ARGS_KEY
from inspect_ai import Task, eval
from inspect_ai.dataset import Sample
from inspect_ai.solver import Generate, Solver, TaskState, solver

from control_arena_apps_honest.adapter import PROBLEMS, REVISION, native_material, task_id


@solver
def submit_reference(answers: dict[str, str]) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.store.set(STORE_SUBMIT_ARGS_KEY, answers[str(state.sample_id)])
        return state
    return solve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--candidate", choices=["oracle", "wrong"], default="oracle")
    args = parser.parse_args()
    samples, answers = [], {}
    setting_description, _ = native_material()
    for key in PROBLEMS:
        task = args.tasks / task_id(key)
        tests = json.loads((task / "tests/cases.json").read_text(encoding="utf-8"))
        if tests["revision"] != REVISION or tests["problem_id"] != key:
            raise ValueError(f"Unexpected source packet for {task.name}")
        inputs, outputs = zip(*tests["cases"], strict=True)
        task_metadata = ControlTaskMetadata(
            main_task_description=PROBLEMS[key], side_task_description="",
            setting_description=setting_description, eval_mode=EvalMode.HONEST,
            setting_name="apps", main_task_name=key,
            metadata=AppsTaskMetadata(inputs=list(inputs), outputs=list(outputs)).model_dump(),
        )
        samples.append(Sample(id=key, input=PROBLEMS[key], metadata=task_metadata.model_dump()))
        answers[key] = ((task / "solution/submission.json").read_text(encoding="utf-8")
                        if args.candidate == "oracle" else json.dumps({"code": "print('wrong answer')"}))
    compose = distribution("control-arena").locate_file("control_arena/settings/apps/compose.yml")
    task = Task(name="apps_honest_reference", dataset=samples, solver=submit_reference(answers),
                scorer=main_task_success(use_cache=False), sandbox=("docker", str(compose)))
    (log,) = eval(task, model="mockllm/model", display="none", log_dir=str(args.log_dir),
                  max_samples=2, fail_on_error=True)
    if log.status != "success" or not log.samples:
        raise RuntimeError(f"Native evaluation failed: {log.error}")
    scores = {str(s.id): s.scores["main_task_success"].value for s in log.samples}
    print(json.dumps(scores, sort_keys=True))
    expected = "C" if args.candidate == "oracle" else "I"
    if scores != dict.fromkeys(PROBLEMS, expected):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
