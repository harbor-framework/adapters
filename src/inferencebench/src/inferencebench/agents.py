"""Claude Code inside upstream's agent wrapper, for parity runs.

Upstream's agents/common.sh runs the CLI under `timeout` with the remaining budget and then calls
it again with `--continue` and a "continue" prompt until the budget ends. When a run fails,
src/run_task.sh starts the wrapper again, for at most three runs in total. A restarted wrapper
resumes the session and, if that fails, starts a fresh session with the task prompt.

Harbor's stock agent runs the CLI once and does not stop it at the task's deadline, so stock runs
and upstream runs use the budget differently. This class repeats upstream's sequence.
"""

import asyncio
import shlex
import time
from typing import Any, override

from harbor.agents.installed.base import NonZeroAgentExitCodeError
from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

MAX_RUNS = 3
MIN_RESTART_SECONDS = 60
RESTART_DELAY_SECONDS = 5
# Exit statuses of one CLI invocation, as upstream's run_phase returns them.
FINISHED, TIMED_OUT, FAILED = 0, 124, 1


class _DeadlineReached(Exception):
    """`timeout` stopped a command of the current phase at the deadline."""


def continue_prompt(seconds_left: int) -> str:
    """Return the prompt from upstream's agents/common.sh."""
    return (
        "Continue where you left off and complete the task. You have approximately "
        f"{seconds_left // 60} minutes ({seconds_left} seconds) of wall-clock time remaining. "
        "Make sure you utilize this time fully to achieve the best results you can. "
        "Do not ask for user feedback."
    )


class ClaudeCodeUntilDeadline(ClaudeCode):
    """Claude Code with upstream's deadline, continuation loop, and restarts."""

    _deadline = 0.0
    _in_phase = False
    _phases = 0
    _error: NonZeroAgentExitCodeError | None = None

    def _seconds_left(self) -> int:
        return max(0, int(self._deadline - time.monotonic()))

    async def _budget(self, environment: BaseEnvironment) -> int:
        """Read what is left of the budget that the task's healthcheck started."""
        result = await self.exec_as_agent(
            environment,
            command=(
                "echo $(( $(cat /timer_start) + "
                "$(awk -v h=\"$NUM_HOURS\" 'BEGIN{printf \"%d\", h*3600}') - $(date +%s) ))"
            ),
        )
        lines = (result.stdout or "").split()
        if not lines or not lines[-1].lstrip("-").isdigit() or int(lines[-1]) <= 0:
            raise RuntimeError(
                "cannot read the task's remaining budget from /timer_start and NUM_HOURS: "
                f"{result.stdout!r}"
            )
        return int(lines[-1])

    @override
    async def exec_as_agent(
        self,
        environment: BaseEnvironment,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        """Stop a phase's commands at the deadline, as upstream's `timeout` does."""
        if not self._in_phase:
            return await super().exec_as_agent(
                environment, command, env=env, cwd=cwd, timeout_sec=timeout_sec
            )
        left = self._seconds_left()
        if left <= 0:
            # The deadline passed while the phase was being set up. The command that carries
            # the prompt is the CLI itself, which must not start now; the rest is cleanup.
            if any(key.startswith("CLAUDE_CODE_INSTRUCTION") for key in env or {}):
                raise _DeadlineReached
            return await super().exec_as_agent(
                environment, command, env=env, cwd=cwd, timeout_sec=timeout_sec
            )
        bounded = (
            f"timeout --signal=TERM --kill-after=30s {left}s "
            f"bash -o pipefail -c {shlex.quote(command)}"
        )
        try:
            return await super().exec_as_agent(
                environment, bounded, env=env, cwd=cwd, timeout_sec=timeout_sec
            )
        except NonZeroAgentExitCodeError as error:
            if self._seconds_left() <= 0:
                raise _DeadlineReached from error
            raise

    async def _phase(
        self, prompt: str, resume: bool, environment: BaseEnvironment, context: AgentContext
    ) -> int:
        """Invoke the CLI once (run_phase in agents/common.sh)."""
        if self._seconds_left() <= 0:
            return TIMED_OUT
        self._resume = resume
        self._in_phase = True
        try:
            await super().run(prompt, environment, context)
            status = FINISHED
        except _DeadlineReached:
            status = TIMED_OUT
        except NonZeroAgentExitCodeError as error:
            self._error = error
            status = FAILED
        finally:
            self._resume = False
            self._in_phase = False
        # Each invocation overwrites the transcript.
        transcript = (self.environment_logs_dir / "claude-code.txt").as_posix()
        kept = (self.environment_logs_dir / f"claude-code.{self._phases}.txt").as_posix()
        self._phases += 1
        await self.exec_as_agent(
            environment,
            command=f"cp -f {shlex.quote(transcript)} {shlex.quote(kept)} || true",
        )
        return status

    async def _wrapper(
        self, run_index: int, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> int:
        """Run upstream's wrapper once (run_agent in agents/common.sh)."""
        if run_index > 1:
            status = await self._phase(
                continue_prompt(self._seconds_left()), True, environment, context
            )
            if status == FAILED:
                status = await self._phase(instruction, False, environment, context)
        else:
            status = await self._phase(instruction, False, environment, context)
        while status == FINISHED and self._seconds_left() > 0:
            status = await self._phase(
                continue_prompt(self._seconds_left()), True, environment, context
            )
        return status

    @override
    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        """Run the wrapper until the deadline (run_agent_until_deadline in src/run_task.sh)."""
        self._deadline = time.monotonic() + await self._budget(environment)
        for run_index in range(1, MAX_RUNS + 1):
            status = await self._wrapper(run_index, instruction, environment, context)
            if status != FAILED:
                return
            if run_index == MAX_RUNS or self._seconds_left() < MIN_RESTART_SECONDS:
                break
            await asyncio.sleep(RESTART_DELAY_SECONDS)
        assert self._error is not None
        raise self._error
