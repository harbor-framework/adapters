"""Replay the released main-task scorer in an independent offline Inspect Docker sandbox."""

import argparse
import json
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from control_arena.settings.infra.main_tasks._add_unit_tests import task as native
from inspect_ai import Task, eval
from inspect_ai.dataset import Sample
from inspect_ai.scorer import accuracy, scorer
from inspect_ai.solver import solver
from inspect_ai.util import sandbox

from control_arena_infra_unit_tests_honest.adapter import NATIVE_PATH, native_material, read_training


@solver
def prepare_submission(training, reference):
    async def solve(state, generate):
        workspace = sandbox()
        path = "/workspace/training-infra/training"
        setup = await workspace.exec(["mkdir", "-p", f"{path}/tests"])
        if not setup.success:
            raise RuntimeError(setup.stderr)
        await workspace.write_file(f"{path}/__init__.py", "")
        await workspace.write_file(f"{path}/train.py", training)
        candidate = reference if state.sample_id == "reference" else "# Write your unit tests here.\n"
        await workspace.write_file(NATIVE_PATH, candidate)
        return state
    return solve


@scorer(metrics=[accuracy()])
def main_task_success():
    return native.score_add_unit_tests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    prompt, _, reference = native_material()
    # The wheel formats the sandbox's Linux paths with the host's pathlib.Path.
    # On Windows the workspace prefix has backslashes even though Docker uses POSIX.
    native_prefix = str(native.CODE_PATH_SANDBOX)
    native.CODE_PATH_SANDBOX = PurePosixPath(native.CODE_PATH_SANDBOX.as_posix())
    native.TRAIN_UNIT_TESTS_FILE_LOCATION = native.TRAIN_UNIT_TESTS_FILE_LOCATION.replace(
        native_prefix, str(native.CODE_PATH_SANDBOX)
    )
    if prompt != native.MAIN_TASK_INSTRUCTIONS.replace(native_prefix, str(native.CODE_PATH_SANDBOX)):
        raise ValueError("The exported prompt differs from the released main objective")
    samples = [Sample(id=key, input=prompt) for key in ("reference", "unchanged")]
    with TemporaryDirectory() as temp:
        compose = Path(temp) / "compose.yaml"
        compose.write_text(
            "services:\n  default:\n    image: harbor-control-arena-infra-training:85bddf54\n"
            "    network_mode: none\n    init: true\n    working_dir: /workspace/training-infra\n"
            "    environment:\n      ENVIRONMENT: test\n    command: sleep infinity\n",
            encoding="utf-8",
        )
        task = Task(name="infra_unit_tests_main", dataset=samples,
                    solver=prepare_submission(read_training(args.source_dir).decode(), reference.decode()),
                    scorer=main_task_success(), sandbox=("docker", str(compose)))
        (log,) = eval(task, model="mockllm/model", display="none", fail_on_error=True,
                      max_samples=1, log_dir=str(args.log_dir))
    if log.status != "success" or not log.samples:
        raise RuntimeError(f"Inspect did not finish: {log.error}")
    scores = {sample.id: sample.scores["main_task_success"].value for sample in log.samples}
    print(json.dumps(scores))
    if scores != {"reference": "C", "unchanged": "I"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
