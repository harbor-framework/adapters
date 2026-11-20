"""Harbor agent that replays one retained ContextBench parity trial.

The agent calls no model. For the task Harbor gives it, it finds the retained
trial of the same task, uploads that trial's ATIF trajectory and raw OpenHands
log to the agent log directory, and applies the trial's collected model patch
to the workspace. Everything after the agent phase is Harbor's own: the task's
collect hook regenerates the patch, the artifact handler transfers the logs,
and the separate verifier scores the trajectory. `parity/rescore.py` runs it::

    harbor run --path <prepared tasks> \\
        --agent parity.replay_agent:ContextBenchReplayAgent \\
        --agent-kwarg source_job_dir=<retained Harbor job directory>
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any, override

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trial.paths import EnvironmentPaths

from contextbench.adapter import sha256_file

# A Harbor job keeps the collected patch with the trial's artifacts; the
# published bundle keeps it beside the trial's `agent/` directory.
PATCH_PATHS = (
    "artifacts/logs/artifacts/contextbench-model.patch",
    "contextbench-model.patch",
)
_REMOTE_PATCH = "/tmp/contextbench-replay.patch"
_TASK_KEY = re.compile(r"([0-9a-f]{16,})$")


def task_key(name: str) -> str:
    """Return the instance digest that a task, trial or task directory name ends in.

    A task name ends in hex digits of the SHA-256 of the ContextBench instance
    ID, at least 16 of them (`contextbench.adapter`), and a trial name appends
    `__<suffix>`. The digest is the first 16 digits.
    """
    match = _TASK_KEY.search(name.split("__", 1)[0])
    if match is None:
        raise ValueError(f"no instance digest in {name!r}")
    return str(match.group(1))[:16]


def retained_trials(job_dir: Path) -> dict[str, Path]:
    """Index the trial directories of a retained Harbor job by task key."""
    trials: dict[str, Path] = {}
    for trial in sorted(path for path in job_dir.iterdir() if path.is_dir()):
        key = task_key(trial.name)
        if key in trials:
            raise ValueError(f"{job_dir} holds two trials of one task: {key}")
        trials[key] = trial
    return trials


def retained_patch(trial: Path) -> Path:
    for relative in PATCH_PATHS:
        if (path := trial / relative).is_file():
            return path
    raise FileNotFoundError(f"retained trial has no model patch: {trial}")


class ContextBenchReplayAgent(BaseAgent):
    """Restore a retained trial's trajectory and patch without calling a model."""

    def __init__(self, *args: Any, source_job_dir: str, **kwargs: Any) -> None:
        self.source_job_dir = Path(source_job_dir).expanduser().resolve()
        if not self.source_job_dir.is_dir():
            raise FileNotFoundError(f"retained job not found: {self.source_job_dir}")
        super().__init__(*args, **kwargs)

    @staticmethod
    @override
    def name() -> str:
        return "contextbench-replay"

    @override
    def version(self) -> str:
        return "1.0.0"

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        return None

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        # Harbor's agent log directory is `<trial>/agent`.
        key = task_key(self.logs_dir.parent.name)
        source = retained_trials(self.source_job_dir).get(key)
        if source is None:
            raise FileNotFoundError(
                f"no retained trial of {key} in {self.source_job_dir}"
            )
        trajectory = source / "agent/trajectory.json"
        patch = retained_patch(source)
        agent_dir = EnvironmentPaths.for_os(environment.os).agent_dir

        await environment.upload_file(trajectory, str(agent_dir / "trajectory.json"))
        native = source / "agent/openhands.trajectory.json"
        if native.is_file():
            await environment.upload_file(
                native, str(agent_dir / "openhands.trajectory.json")
            )
        if patch.stat().st_size:
            await environment.upload_file(patch, _REMOTE_PATCH)
            remote = shlex.quote(_REMOTE_PATCH)
            result = await environment.exec(
                f"git apply --binary --whitespace=nowarn {remote} && rm -f {remote}",
                timeout_sec=120,
            )
            if result.return_code != 0:
                raise RuntimeError(
                    f"retained patch did not apply: {result.stdout} {result.stderr}"
                )
        context.metadata = {
            "replay_source_trial": str(source),
            "replay_trajectory_sha256": sha256_file(trajectory),
            "replay_patch_sha256": sha256_file(patch),
        }
