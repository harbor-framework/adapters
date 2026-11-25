"""Harbor parity agent for tau-Rec: tau-Rec's own ``LiteLLMAgent``.

``install`` puts the pinned tau-Rec checkout (tag v2.1.0, commit checked) and
its locked environment into the ``main`` container, which ships without it;
``run`` then runs ``run_tau_rec_parity_agent.py`` with that environment's
Python. The runner builds the agent from the runtime sidecar's
``get_agent_setup`` and drives the trial through ``submit_agent_response``, so
the model sees exactly the requests a native ``tau-rec run`` sends. The task
instruction is not used: the native system prompt replaces it.

Import path: ``tau_rec_parity_agent:TauRecParityAgent``, with ``src/tau-rec``
on ``PYTHONPATH``.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harbor.agents.capabilities import AgentCapabilities
from harbor.agents.installed.base import BaseInstalledAgent

if TYPE_CHECKING:
    from harbor.environments.base import BaseEnvironment
    from harbor.models.agent.context import AgentContext
    from harbor.models.task.config import MCPServerConfig

RUNNER_FILENAME = "run_tau_rec_parity_agent.py"
RUNNER_TARGET_PATH = f"/installed-agent/{RUNNER_FILENAME}"
# The task images' package pins, shared with the runtime sidecar's build.
CONSTRAINTS_PATH = (
    Path(__file__).parent
    / "src"
    / "tau_rec_adapter"
    / "task-template"
    / "environment"
    / "constraints.txt"
)
CONSTRAINTS_TARGET_PATH = "/installed-agent/constraints.txt"
TAU_REC_ROOT = "/opt/tau-rec"
# The tau-Rec venv install() builds (litellm and mcp at the pinned versions).
PYTHON = f"{TAU_REC_ROOT}/.venv/bin/python"
SUMMARY_FILENAME = "tau-rec-parity-agent-summary.json"
LOG_FILENAME = "tau-rec-parity-agent.txt"
DEFAULT_VERSION = "1.0"

TAU_REC_REPO_URL = "https://github.com/nbharaths/tau-rec"
TAU_REC_TAG = "v2.1.0"
TAU_REC_COMMIT = "8b4c3e6823add74f6c209fff864e2eae6849880c"
UV_VERSION = "0.13.8"
MCP_VERSION = "2.3.0"

# The same steps as the runtime sidecar's Dockerfile. Afterwards only what the
# runner imports stays: tau-Rec's source and its locked environment, not the
# benchmark data.
INSTALL_SCRIPT = f"""set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends git ca-certificates
pip install --no-cache-dir uv=={UV_VERSION}
rm -rf {TAU_REC_ROOT}
git clone --depth 1 --branch {TAU_REC_TAG} {TAU_REC_REPO_URL} {TAU_REC_ROOT}
head="$(git -C {TAU_REC_ROOT} rev-parse HEAD)"
if [ "$head" != {TAU_REC_COMMIT} ]; then
    echo "tau-Rec {TAU_REC_TAG} is at $head, expected {TAU_REC_COMMIT}" >&2
    exit 1
fi
uv sync --frozen --project {TAU_REC_ROOT}
uv pip install --python {PYTHON} -c {CONSTRAINTS_TARGET_PATH} mcp=={MCP_VERSION}
find {TAU_REC_ROOT} -mindepth 1 -maxdepth 1 ! -name src ! -name .venv \\
    ! -name pyproject.toml ! -name uv.lock -exec rm -rf {{}} +
rm -rf /var/lib/apt/lists/*
"""

# Provider keys per LiteLLM provider prefix. Only the model's own provider's
# keys reach the runner.
PROVIDER_KEYS = {
    "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE"),
    "gemini": ("GEMINI_API_KEY",),
    "azure": (
        "AZURE_API_KEY",
        "AZURE_API_BASE",
        "AZURE_API_VERSION",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_API_BASE",
        "AZURE_OPENAI_API_VERSION",
    ),
    "openrouter": ("OPENROUTER_API_KEY",),
}
# LiteLLM settings a native run may set (e.g. pricing from the bundled map).
LITELLM_KEYS = ("LITELLM_LOCAL_MODEL_COST_MAP",)


def model_provider(model: str) -> str:
    """The LiteLLM provider of ``model``: its prefix, else inferred from a bare
    name as LiteLLM does for the providers above (OpenAI by default)."""
    if "/" in model:
        provider = model.split("/", 1)[0]
        if provider not in PROVIDER_KEYS:
            raise ValueError(
                f"TauRecParityAgent does not know which keys provider {provider!r} "
                f"needs; supported prefixes: {', '.join(sorted(PROVIDER_KEYS))}"
            )
        return provider
    for prefix, provider in (("claude", "anthropic"), ("gemini", "gemini")):
        if model.startswith(prefix):
            return provider
    return "openai"


class TauRecParityAgent(BaseInstalledAgent):
    capabilities = AgentCapabilities(mcp_servers=True, reasoning_effort=True)
    # install() clones tau-Rec and syncs its locked environment (~110 packages).
    DEFAULT_SETUP_TIMEOUT_SEC = 900.0

    def __init__(self, *args: Any, reasoning_effort: str | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._reasoning_effort = reasoning_effort

    @staticmethod
    def name() -> str:
        return "tau-rec-parity-agent"

    def version(self) -> str | None:
        return self._version or DEFAULT_VERSION

    async def install(self, environment: BaseEnvironment) -> None:
        # The main image has no tau-Rec: install the pinned checkout here.
        constraints = self.logs_dir / CONSTRAINTS_PATH.name
        constraints.write_text(CONSTRAINTS_PATH.read_text(encoding="utf-8"))
        await environment.upload_file(constraints, CONSTRAINTS_TARGET_PATH)
        await self.exec_as_root(environment, command=INSTALL_SCRIPT)
        runner = self.logs_dir / RUNNER_FILENAME
        runner.write_text(
            Path(__file__).with_name(RUNNER_FILENAME).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        await environment.upload_file(runner, RUNNER_TARGET_PATH)

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        if not self.model_name:
            raise ValueError("model_name is required for TauRecParityAgent")
        server = self._runtime_server()
        parts = [
            PYTHON,
            RUNNER_TARGET_PATH,
            "--model",
            shlex.quote(self.model_name),
            "--mcp-url",
            shlex.quote(server.url),
            "--summary-path",
            shlex.quote(f"/logs/agent/{SUMMARY_FILENAME}"),
        ]
        if self._reasoning_effort:
            parts += ["--reasoning-effort", shlex.quote(self._reasoning_effort)]
        command = f"{' '.join(parts)} 2>&1 | tee /logs/agent/{LOG_FILENAME}"
        await self.exec_as_agent(environment, command=command, env=self._runner_env())

    def populate_context_post_run(self, context: AgentContext) -> None:
        path = self.logs_dir / SUMMARY_FILENAME
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        context.n_input_tokens = _as(int, summary.get("n_input_tokens"))
        context.n_output_tokens = _as(int, summary.get("n_output_tokens"))
        context.n_cache_tokens = _as(int, summary.get("n_cache_tokens"))
        context.cost_usd = _as(float, summary.get("cost_usd"))
        if isinstance(summary.get("metadata"), dict):
            context.metadata = summary["metadata"]

    def _runtime_server(self) -> MCPServerConfig:
        if len(self.mcp_servers) != 1:
            raise ValueError(
                "TauRecParityAgent expects exactly one MCP server (the runtime "
                f"sidecar), got {len(self.mcp_servers)}"
            )
        server = self.mcp_servers[0]
        if server.transport != "streamable-http":
            raise ValueError(
                "TauRecParityAgent needs a streamable-http MCP server, got "
                f"{server.transport!r}"
            )
        if not server.url:
            raise ValueError("TauRecParityAgent's MCP server has no URL")
        return server

    def _runner_env(self) -> dict[str, str]:
        """The model's provider keys and the allow-listed LiteLLM settings,
        resolved through Harbor's agent env (``_get_env``), nothing else."""
        keys = (*PROVIDER_KEYS[model_provider(self.model_name)], *LITELLM_KEYS)
        return {key: value for key in keys if (value := self._get_env(key))}


def _as(kind: type, value: Any) -> Any:
    if value is None:
        return None
    try:
        return kind(value)
    except (TypeError, ValueError):
        return None
