"""CyberGym process ASLR hooks for Harbor's installed agents."""

from __future__ import annotations

import shlex
from typing import Any, override

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.codex import Codex
from harbor.agents.installed.gemini_cli import GeminiCli
from harbor.agents.installed.openhands import OpenHands
from harbor.environments.base import BaseEnvironment


class CyberGymInstalledAgent(BaseInstalledAgent):
    """Disable process ASLR while retaining Harbor's agent lifecycle."""

    @override
    async def exec_as_agent(
        self,
        environment: BaseEnvironment,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        command = 'exec setarch "$(uname -m)" -R bash -c ' + shlex.quote(
            f"set -o pipefail; {command}"
        )
        return await super().exec_as_agent(
            environment, command, env=env, cwd=cwd, timeout_sec=timeout_sec
        )


class CyberGymOpenHands(CyberGymInstalledAgent, OpenHands):
    """Harbor OpenHands with process ASLR disabled."""


class CyberGymCodex(CyberGymInstalledAgent, Codex):
    """Harbor Codex with process ASLR disabled."""


class CyberGymClaudeCode(CyberGymInstalledAgent, ClaudeCode):
    """Harbor Claude Code with process ASLR disabled."""


class CyberGymGeminiCli(CyberGymInstalledAgent, GeminiCli):
    """Harbor Gemini CLI with process ASLR disabled."""
