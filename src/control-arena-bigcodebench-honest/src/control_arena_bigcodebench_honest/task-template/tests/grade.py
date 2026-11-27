"""Score the harvested Python submission inside Harbor's separate verifier."""

import json
import sys
from pathlib import Path

from control_arena.settings.bigcodebench.task.scorers import main_task_success
from control_arena.settings.bigcodebench.task.submission_types import SubmitHonestArgs
from control_arena.tools.submit_tool import STORE_SUBMIT_ARGS_KEY
from inspect_ai import Task, eval
from inspect_ai.dataset import Sample
from inspect_ai.scorer import CORRECT, INCORRECT
from inspect_ai.solver import solver
from inspect_ai.util import sandboxenv
from inspect_ai.util._sandbox.local import LocalSandboxEnvironment


@sandboxenv(name="honest_bigcodebench")
class GraderSandbox(LocalSandboxEnvironment):
    @classmethod
    async def sample_init(cls, task_name, config, metadata):
        return {"default": cls()}

    async def exec(self, cmd, **kwargs):
        # The pinned scorer runs a single Python unittest script. Run the
        # submitted function without access to the grader's files or reward.
        if cmd[:2] != ["python3", "-c"] or len(cmd) != 3:
            raise ValueError("Unexpected invocation from the BigCodeBench honest scorer")
        identity = ["/usr/bin/setpriv", "--reuid=65534", "--regid=65534",
                    "--clear-groups", "--no-new-privs", "--"]
        kwargs["cwd"] = "/tmp"
        return await super().exec([*identity, *cmd], **kwargs)


@solver
def restore(code: str | None):
    async def solve(state, generate):
        if code is not None:
            submission = SubmitHonestArgs(code=code)
            state.store.set(STORE_SUBMIT_ARGS_KEY, submission.model_dump_json())
        return state
    return solve


def main(reward: Path) -> None:
    reward.unlink(missing_ok=True)
    sample = Sample.model_validate_json(Path("/tests/sample.json").read_bytes())
    try:
        code = Path("/logs/artifacts/solution.py").read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, IsADirectoryError):
        code = None
    task = Task(dataset=[sample], solver=restore(code), scorer=main_task_success(),
                sandbox="honest_bigcodebench", name="honest_bigcodebench_submission")
    (log,) = eval(task, model="mockllm/unused", display="none", ctl_server=False,
                 fail_on_error=True, log_dir="/logs/verifier/inspect")
    if log.status != "success" or not log.samples or not log.samples[0].scores:
        raise RuntimeError(f"Native BigCodeBench scoring failed. See {log.location}")
    score = log.samples[0].scores["main_task_success"]
    if score.value not in (CORRECT, INCORRECT):
        raise ValueError(f"Unexpected native verdict: {score.value}")
    temp = reward.with_suffix(".tmp")
    temp.write_text(json.dumps({"main_task_success": int(score.value == CORRECT)}) + "\n")
    temp.replace(reward)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
