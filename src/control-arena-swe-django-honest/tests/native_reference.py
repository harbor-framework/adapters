"""Replay the reviewed Django issue directly in Inspect with ControlArena's native main scorer."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from control_arena.settings.swebench.dataset import DEFAULT_INPUT_PROMPT
from control_arena.settings.swebench.scorers import main_task_correctness
from inspect_ai import Task, eval
from inspect_ai.dataset import Sample
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import sandbox

from control_arena_swe_django_honest.adapter import IMAGE, SOURCE_ID, load_issue, prepare_swebench_imports


@solver
def apply_reference(patch: str | None) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        if patch is not None:
            await sandbox().write_file("/tmp/reference.patch", patch)
            result = await sandbox().exec(["git", "apply", "/tmp/reference.patch"], cwd="/testbed")
            if not result.success:
                raise RuntimeError(result.stderr)
        return state
    return solve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=["oracle", "unchanged"], default="oracle")
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()
    prepare_swebench_imports()
    issue = load_issue()
    prompt = DEFAULT_INPUT_PROMPT.format(issue_text=issue["problem_statement"])
    sample = Sample(id=SOURCE_ID, input=prompt, metadata=issue)
    with TemporaryDirectory() as temp:
        compose = Path(temp) / "compose.yaml"
        compose.write_text(
            f"services:\n  default:\n    image: {IMAGE}\n    working_dir: /testbed\n"
            "    network_mode: none\n    init: true\n    command: sleep infinity\n",
            encoding="utf-8",
        )
        task = Task(name="django_honest_reference", dataset=[sample],
                    solver=apply_reference(issue["patch"] if args.candidate == "oracle" else None),
                    scorer=main_task_correctness(), sandbox=("docker", str(compose)))
        (log,) = eval(task, model="mockllm/model", display="none", log_dir=str(args.log_dir),
                      fail_on_error=True)
    if log.status != "success" or not log.samples:
        raise RuntimeError(f"Native evaluation failed: {log.error}")
    score = log.samples[0].scores["main_task_correctness"].value
    print(json.dumps({SOURCE_ID: score}))
    if score != ("C" if args.candidate == "oracle" else "I"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
