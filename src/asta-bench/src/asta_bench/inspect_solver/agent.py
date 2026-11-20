"""Inspect-AI solver bridge agent.

Runs `inspect eval --solver <solver> --no-score` in the task container for the
configured upstream Inspect task and sample, and writes the final completion
to `/app/answer.txt`. Scoring happens only in the Harbor verifier.

The per-task wiring is read from a JSON config file, first found of:

  1. the `inspect_config_path` agent kwarg
  2. `/app/inspect_config.json` (baked into the image)
  3. `/tests/inspect_config.json`

Required fields in `inspect_config.json`:
  - `task`       (str)            upstream Inspect task identifier, e.g.
                                  "astabench/sqa_test"
  - `sample_id`  (str | int)      sample id within that task

Optional fields:
  - `pip_install` (list[str])     extra pip requirements for ad hoc runs
                                  (generated datasets preinstall everything).
  - `apt_install` (list[str])     extra apt packages for ad hoc runs.
  - `task_args`   (dict[str,str]) forwarded as `inspect eval -T k=v`.
  - `solver_args` (dict[str,str]) forwarded as `inspect eval -S k=v`.
  - `eval_args`   (list[str])     extra flags for `inspect eval`.
  - `site_package_replacements`
                  (list[dict])    narrowly scoped text replacements applied
                                  to installed Python packages after
                                  `pip_install` and before `inspect eval`.
  - `export_files`
                  (list[dict])    `[{"src": "report.json", "dest": "/app/report.json"}]`.
                                  Sandbox files the scorer reads (CORE-Bench
                                  `report.json`). A wrapper solver copies each
                                  `src` to `dest` after the inner solver
                                  returns (or hits a sample limit), before the
                                  sandbox is torn down. Stale `dest` files are
                                  deleted before the run.
  - `keep_sandbox_dir` (bool)     keep Inspect's temporary `local` sandbox
                                  directory after the run, at the same path,
                                  so the verifier can re-run the submitted
                                  command (SUPER-Auto).
  - `require_tools` (bool)        fail the run (exit 6) if the first model
                                  call was offered no tool other than `submit`
                                  (task tools were dropped by the solver).

Agent kwargs (`--ak k=v`):
  - `solver`     (default "astabench/react"; bare "react" is Inspect's
                  built-in agent, which ignores the task's `use_tools` tools)
  - `inspect_config_path`, `task`, `sample_id` override the config file.

Env vars (from the agent kwargs or the host env, see ENV_VARS): the model
provider keys, HF_TOKEN, and ASTA_TOOL_KEY for the literature families.
"""

from __future__ import annotations

import json
import shlex

from harbor.agents.capabilities import AgentCapabilities
from harbor.agents.installed.base import (
    ApiError,
    ApiInternalServerError,
    ApiOverloadedError,
    BaseInstalledAgent,
    CliFlag,
    EnvVar,
    ErrorPattern,
    NonZeroAgentExitCodeError,
    UnknownApiError,
    with_prompt_template,
)
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

DEFAULT_INSPECT_AI_VERSION = "0.3.203"
# The fork's uv.lock version; inspect_ai 0.3.203 breaks on anthropic>=2.
DEFAULT_ANTHROPIC_VERSION = "0.97.0"

CONFIG_PATH_PRIMARY = "/app/inspect_config.json"
CONFIG_PATH_ALT = "/tests/inspect_config.json"
BRIDGE_READY_MARKER = "/opt/asta-inspect-bridge-ready"


class InspectHarnessError(NonZeroAgentExitCodeError):
    """The bridge failed before producing an answer (Inspect crashed, the task
    did not load, the sample errored, or the model was offered no tools).

    The harness exits non-zero only for such failures; a wrong answer exits 0
    and is scored. Harbor's default policy treats an unknown agent exception as
    a valid 0 reward, so job configs map this type to "not graded, no valid
    reward" via `override_error_policy` (see run_asta-bench_inspect-ai.yaml).
    """


class InspectSolver(BaseInstalledAgent):
    """Run any Inspect-AI solver against the configured Inspect Task + Sample,
    then write the final completion to `/app/answer.txt`.
    """

    # Harbor >= 0.26 refuses tasks with MCP servers unless this is declared.
    # The bridge does not use the task's Harbor-level Asta MCP server: the
    # Inspect task gives the model the same tools itself.
    capabilities = AgentCapabilities(mcp_servers=True)

    # Provider errors as Inspect's Anthropic/OpenAI clients report them, mapped
    # to Harbor's API error types (retryable, no valid reward). Checked in
    # addition to Harbor's own patterns; the match nearest the end wins.
    ERROR_PATTERNS = [
        *BaseInstalledAgent.ERROR_PATTERNS,
        ErrorPattern(r"InternalServerError|Error code: 5(?!29)\d\d", ApiInternalServerError),
        ErrorPattern(r"overloaded_error|OverloadedError|Error code: 529", ApiOverloadedError),
        ErrorPattern(r"APIConnectionError|APITimeoutError", UnknownApiError),
    ]

    CLI_FLAGS = [
        CliFlag("solver", cli="--solver", type="str", default="astabench/react"),
        CliFlag("inspect_config_path", cli="--inspect-config-path", type="str"),
        # Per-field overrides; empty by default so the config file wins.
        CliFlag("task", cli="--task", type="str"),
        CliFlag("sample_id", cli="--sample-id", type="str"),
    ]

    ENV_VARS = [
        EnvVar("hf_token", env="HF_TOKEN", env_fallback="HF_TOKEN"),
        EnvVar("openai_api_key", env="OPENAI_API_KEY", env_fallback="OPENAI_API_KEY"),
        EnvVar(
            "openai_base_url", env="OPENAI_BASE_URL", env_fallback="OPENAI_BASE_URL"
        ),
        EnvVar(
            "anthropic_api_key",
            env="ANTHROPIC_API_KEY",
            env_fallback="ANTHROPIC_API_KEY",
        ),
        EnvVar(
            "anthropic_base_url",
            env="ANTHROPIC_BASE_URL",
            env_fallback="ANTHROPIC_BASE_URL",
        ),
        EnvVar("google_api_key", env="GOOGLE_API_KEY", env_fallback="GOOGLE_API_KEY"),
        EnvVar("asta_tool_key", env="ASTA_TOOL_KEY", env_fallback="ASTA_TOOL_KEY"),
        EnvVar(
            "allow_runtime_install",
            env="ASTA_BRIDGE_ALLOW_RUNTIME_INSTALL",
            type="bool",
            default=False,
            env_fallback="ASTA_BRIDGE_ALLOW_RUNTIME_INSTALL",
            bool_true="1",
            bool_false="0",
        ),
    ]

    @staticmethod
    def name() -> str:
        # Not a Harbor-core agent; select it with
        # `import_path: asta_bench.inspect_solver:InspectSolver`.
        return "inspect-solver"

    def get_version_command(self) -> str | None:
        return ". $HOME/.local/bin/env 2>/dev/null || true; uv pip list --system 2>/dev/null | grep -i '^inspect[-_]ai' || pip show inspect_ai | grep -i ^version"

    def parse_version(self, stdout: str) -> str:
        for line in stdout.splitlines():
            line = line.strip()
            if line.lower().startswith("version"):
                return line.split(":", 1)[-1].strip()
            parts = line.split()
            if len(parts) >= 2 and parts[0].lower().replace("_", "-") == "inspect-ai":
                return parts[1]
        return stdout.strip() or DEFAULT_INSPECT_AI_VERSION

    async def install(self, environment: BaseEnvironment) -> None:
        # Generated bridge datasets bake this runtime into the image. The
        # install below is a debug-only fallback for ad hoc tasks
        # (ASTA_BRIDGE_ALLOW_RUNTIME_INSTALL=1).
        await self.exec_as_root(
            environment,
            command=(
                f"if [ -f {BRIDGE_READY_MARKER} ]; then "
                "echo '[bridge-setup] preinstalled runtime found'; exit 0; "
                "fi; "
                'if [ "${ASTA_BRIDGE_ALLOW_RUNTIME_INSTALL:-0}" != "1" ]; then '
                "echo '[bridge-setup] missing preinstalled Inspect-AI bridge runtime. "
                "Regenerate this dataset with the default asta-bench generator "
                "or set ASTA_BRIDGE_ALLOW_RUNTIME_INSTALL=1 for debug-only fallback installs.' >&2; "
                "exit 42; "
                "fi; "
                "apt-get update && "
                "apt-get install -y --no-install-recommends git curl ca-certificates gnupg && "
                "rm -rf /var/lib/apt/lists/*"
            ),
            env=self.resolve_env_vars() | {"DEBIAN_FRONTEND": "noninteractive"},
        )
        await self.exec_as_agent(
            environment,
            command=(
                f"if [ -f {BRIDGE_READY_MARKER} ]; then "
                "echo '[bridge-setup] preinstalled runtime found'; exit 0; "
                "fi; "
                "mkdir -p /logs/agent && "
                "exec > >(tee -a /logs/agent/inspect-bridge-setup.log) 2>&1; "
                "set -ex; "
                "curl -LsSf https://astral.sh/uv/install.sh | sh; "
                'if [ -f "$HOME/.local/bin/env" ]; then source "$HOME/.local/bin/env"; fi; '
                f"uv pip install --system 'inspect_ai=={DEFAULT_INSPECT_AI_VERSION}' "
                f"'anthropic=={DEFAULT_ANTHROPIC_VERSION}' 'pyarrow==24.0.0'; "
                # astabench's sandbox_jupyter.py hardcodes
                # /opt/inspect_tool_support/bin/python; a system-wide install
                # is not found and python_session cannot run code.
                "python3 -m venv /opt/inspect_tool_support && "
                "/opt/inspect_tool_support/bin/pip install inspect-tool-support && "
                "/opt/inspect_tool_support/bin/inspect-tool-support post-install; "
                # Package set of upstream's util/sandbox/Dockerfile; without it
                # the kernel gateway behind python_session does not start.
                "/opt/inspect_tool_support/bin/pip install requests "
                "  jupyter_client==8.6.3 jupyter_kernel_gateway==3.0.1 "
                "  'mcp~=1.10'; "
                "pip install jupyterlab==4.4.3 "
                "  jupyter_kernel_gateway==3.0.1 numpy pandas "
                "  matplotlib==3.10.0 'mcp~=1.10'; "
                "ls -la /opt/inspect_tool_support/bin/python; "
                "ls -la $HOME/.cache/ms-playwright/ 2>&1 | head -5; "
                "echo '[bridge-setup] complete'"
            ),
            env=self.resolve_env_vars(),
        )

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        if not self.model_name:
            raise ValueError("InspectSolver: --model is required for the solver.")

        flags = self._resolved_flags
        solver = flags.get("solver") or "astabench/react"
        cli_task = flags.get("task")
        cli_sample_id = flags.get("sample_id")
        cli_config_path = flags.get("inspect_config_path")

        harness_payload = {
            "solver": solver,
            "model_name": self.model_name,
            "cli_task": cli_task,
            "cli_sample_id": cli_sample_id,
            "cli_config_path": cli_config_path,
            "config_path_primary": CONFIG_PATH_PRIMARY,
            "config_path_alt": CONFIG_PATH_ALT,
        }
        harness_q = shlex.quote(json.dumps(harness_payload))

        try:
            await self.exec_as_agent(
                environment,
                command=(
                    "set -o pipefail; "
                    ". $HOME/.local/bin/env 2>/dev/null || true; "
                    "mkdir -p /app /logs/agent/inspect-logs /logs/agent/bridge && "
                    f"export __INSPECT_BRIDGE_PAYLOAD={harness_q} && "
                    f"PYTHONUNBUFFERED=1 python3 -u - <<'PYEOF' 2>&1 "
                    "| tee /logs/agent/bridge/harness.log\n"
                    f"{HARNESS_PY}\nPYEOF"
                ),
                env=self.resolve_env_vars(),
            )
        except ApiError:
            raise  # provider failure: Harbor already records no valid reward
        except NonZeroAgentExitCodeError as exc:
            raise InspectHarnessError(str(exc)) from exc

    def populate_context_post_run(self, context: AgentContext) -> None:
        pass


# Harness run in the container via a heredoc: reads $__INSPECT_BRIDGE_PAYLOAD
# and the config file, runs `inspect eval` for the configured sample, and
# writes the completion to /app/answer.txt.
HARNESS_PY = r"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

LOG_DIR = "/logs/agent/inspect-logs"
EXPORT_DIR = "/tmp/asta-inspect-bridge"

# Solver module written to EXPORT_DIR when the config has `export_files`.
# It wraps the configured solver (resolved by name, exactly as `inspect eval
# --solver <name> -S ...` would) and copies sandbox files out after it
# returns, i.e. while the sandbox still exists.  A sample limit (token /
# message / time) still leads to upstream scoring, so files are exported in
# that case too; on any other solver error upstream does not score, so
# nothing is exported.
EXPORT_SOLVER_SRC = '''
import json
import os
from pathlib import Path

from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import LimitExceededError, sandbox


def _keep_sandbox_dir():
    # Inspect's `local` sandbox works in a tempfile.TemporaryDirectory that is
    # removed at sample cleanup (and by its finalizer at interpreter exit).
    # Disarm both so the directory, and every absolute path the solver used
    # inside it, is still there when the Harbor verifier runs.
    if os.environ.get("ASTA_BRIDGE_KEEP_SANDBOX_DIR") != "1":
        return
    env = sandbox()
    try:
        # sandbox() returns an event-recording proxy; unwrap it.
        from inspect_ai.util._sandbox.local import LocalSandboxEnvironment

        env = env.as_type(LocalSandboxEnvironment)
    except Exception:
        env = getattr(env, "_sandbox", env)
    directory = getattr(env, "directory", None)
    if directory is None or not hasattr(directory, "cleanup"):
        print("[inspect-bridge] keep_sandbox_dir: sandbox has no temp directory", flush=True)
        return
    finalizer = getattr(directory, "_finalizer", None)
    if finalizer is not None:
        finalizer.detach()
    directory.cleanup = lambda: None
    print(f"[inspect-bridge] keeping sandbox directory {directory.name}", flush=True)


async def _export_files():
    specs = json.loads(os.environ.get("ASTA_BRIDGE_EXPORT_FILES") or "[]")
    for spec in specs:
        src, dest = spec["src"], Path(spec["dest"])
        try:
            data = await sandbox().read_file(src, text=False)
        except FileNotFoundError:
            print(f"[inspect-bridge] export: {src} not found in sandbox", flush=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(
            f"[inspect-bridge] export: {src} -> {dest} ({len(data)} bytes)",
            flush=True,
        )


@solver
def asta_bridge_export(**kwargs) -> Solver:
    from inspect_ai._eval.loader import solver_from_spec
    from inspect_ai.solver._solver import SolverSpec

    inner = solver_from_spec(
        SolverSpec(
            solver=os.environ["ASTA_BRIDGE_INNER_SOLVER"],
            args=dict(kwargs),
            args_passed=dict(kwargs),
        )
    )

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        _keep_sandbox_dir()
        try:
            state = await inner(state, generate)
        except LimitExceededError:
            await _export_files()
            raise
        await _export_files()
        return state

    return solve
'''


def _load_config_file(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[inspect-bridge] WARN: {path} not valid JSON: {e}", file=sys.stderr)
        return None


def _apt_install(packages):
    if not packages:
        return
    cmd = ["sudo", "-n", "apt-get", "install", "-y", "--no-install-recommends", *packages]
    print(f"[inspect-bridge] apt install: {packages}", flush=True)
    subprocess.run(cmd, check=False)


def _pip_install(packages):
    if not packages:
        return
    print(f"[inspect-bridge] pip install: {packages}", flush=True)
    cmd = ["uv", "pip", "install", "--system", *packages]
    rc = subprocess.run(cmd, check=False).returncode
    if rc != 0:
        print(f"[inspect-bridge] uv pip exit={rc}; trying pip", flush=True)
        subprocess.run(
            ["python3", "-m", "pip", "install", "--no-cache-dir", *packages],
            check=True,
        )


def _apply_site_package_replacements(replacements):
    if not replacements:
        return

    import importlib.util

    for item in replacements:
        package = item["package"]
        rel_path = item["path"]
        old = item["old"]
        new = item["new"]
        count = int(item.get("count", 1))

        spec = importlib.util.find_spec(package)
        if spec is None:
            raise RuntimeError(f"package not found for replacement: {package}")
        if spec.submodule_search_locations:
            package_root = Path(next(iter(spec.submodule_search_locations)))
        elif spec.origin:
            package_root = Path(spec.origin).parent
        else:
            raise RuntimeError(f"cannot locate package for replacement: {package}")

        target = (package_root / rel_path).resolve()
        text = target.read_text(encoding="utf-8")
        found = text.count(old)
        if found < count:
            if new in text:
                print(
                    f"[inspect-bridge] patch already present in {package}/{rel_path}",
                    flush=True,
                )
                continue
            raise RuntimeError(
                f"replacement target {target} has {found} occurrences; "
                f"expected at least {count}"
            )
        target.write_text(text.replace(old, new, count), encoding="utf-8")
        print(
            f"[inspect-bridge] patched {package}/{rel_path}: "
            f"{count} replacement(s)",
            flush=True,
        )


def _resolve_config(payload):
    cfg = {}
    cli_path = payload.get("cli_config_path")
    candidates = [cli_path, payload["config_path_primary"], payload["config_path_alt"]]
    for path in candidates:
        if not path:
            continue
        loaded = _load_config_file(path)
        if loaded:
            print(f"[inspect-bridge] using config from {path}", flush=True)
            cfg = loaded
            break
    # Agent kwargs override the config file.
    if payload.get("cli_task"):
        cfg["task"] = payload["cli_task"]
    if payload.get("cli_sample_id") is not None:
        cfg["sample_id"] = str(payload["cli_sample_id"])
    return cfg


def _format_kv_args(args_dict, flag):
    out = []
    for k, v in (args_dict or {}).items():
        out.extend([flag, f"{k}={v}"])
    return out


def _prepare_exports(export_files, solver, env, keep_sandbox_dir=False):
    # Returns the --solver value to use; mutates env for the wrapper.
    if not export_files and not keep_sandbox_dir:
        return solver
    if keep_sandbox_dir:
        env["ASTA_BRIDGE_KEEP_SANDBOX_DIR"] = "1"
    for spec in export_files:
        if not isinstance(spec, dict) or not spec.get("src") or not spec.get("dest"):
            raise ValueError(f"export_files entry must have src and dest: {spec!r}")
        if not str(spec["dest"]).startswith("/"):
            raise ValueError(f"export_files dest must be absolute: {spec!r}")
        # Never let a stale file (e.g. from a previous attempt) be scored.
        Path(spec["dest"]).unlink(missing_ok=True)
    mod = Path(EXPORT_DIR) / "asta_bridge_export.py"
    mod.parent.mkdir(parents=True, exist_ok=True)
    mod.write_text(EXPORT_SOLVER_SRC, encoding="utf-8")
    env["ASTA_BRIDGE_INNER_SOLVER"] = solver
    env["ASTA_BRIDGE_EXPORT_FILES"] = json.dumps(export_files)
    print(f"[inspect-bridge] wrapping solver {solver!r} to export {export_files}", flush=True)
    return f"{mod}@asta_bridge_export"


def _first_model_tool_names(sample):
    # Tool names offered to the model on its first call, or None if the
    # log has no model event.
    for ev in sample.get("events") or []:
        if ev.get("event") == "model":
            return [str(t.get("name")) for t in (ev.get("tools") or [])]
    return None


def main():
    raw = os.environ.get("__INSPECT_BRIDGE_PAYLOAD")
    if not raw:
        print("[inspect-bridge] missing __INSPECT_BRIDGE_PAYLOAD env", file=sys.stderr)
        sys.exit(2)
    payload = json.loads(raw)

    cfg = _resolve_config(payload)

    task = cfg.get("task")
    sample_id = cfg.get("sample_id")
    if not task or sample_id is None:
        print(
            "[inspect-bridge] config file or CLI must define 'task' and 'sample_id'.",
            file=sys.stderr,
        )
        sys.exit(3)

    _apt_install(cfg.get("apt_install") or [])
    _pip_install(cfg.get("pip_install") or [])
    _apply_site_package_replacements(cfg.get("site_package_replacements") or [])

    sub_env = dict(os.environ)
    export_files = cfg.get("export_files") or []
    solver_arg = _prepare_exports(
        export_files,
        payload["solver"],
        sub_env,
        keep_sandbox_dir=bool(cfg.get("keep_sandbox_dir")),
    )

    cmd = [
        "inspect",
        "eval",
        "--solver",
        solver_arg,
        "--model",
        payload["model_name"],
        "--sample-id",
        str(sample_id),
        "--log-format",
        "json",
        "--log-dir",
        LOG_DIR,
        # Scoring runs only in the verifier, outside the agent's reach.
        "--no-score",
        *_format_kv_args(cfg.get("task_args"), "-T"),
        *_format_kv_args(cfg.get("solver_args"), "-S"),
        *(cfg.get("eval_args") or []),
        task,
    ]
    # Log which keys are present (never their values).
    diag_keys = (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "GOOGLE_API_KEY",
        "ASTA_TOOL_KEY",
        "HF_TOKEN",
    )
    for k in diag_keys:
        v = os.environ.get(k)
        present = "set" if v else "MISSING"
        print(f"[inspect-bridge] env {k}: {present}", flush=True)
    print(
        f"[inspect-bridge] running: {' '.join(shlex.quote(c) for c in cmd)}",
        flush=True,
    )
    # Capture output so a failure's traceback is not lost to Harbor's
    # stream truncation.
    proc = subprocess.run(
        cmd, check=False, capture_output=True, text=True, env=sub_env
    )
    if proc.stdout:
        print("[inspect-bridge] === inspect eval stdout ===", flush=True)
        sys.stdout.write(proc.stdout)
        sys.stdout.flush()
    if proc.stderr:
        print("[inspect-bridge] === inspect eval stderr ===", flush=True)
        sys.stdout.write(proc.stderr)
        sys.stdout.flush()
    if proc.returncode != 0:
        print(
            f"[inspect-bridge] inspect eval exit={proc.returncode}",
            flush=True,
        )
        sys.exit(proc.returncode)

    logs = sorted(Path(LOG_DIR).glob("*.json"))
    if not logs:
        print("[inspect-bridge] no inspect log produced", file=sys.stderr)
        sys.exit(4)
    obj = json.loads(logs[-1].read_text(encoding="utf-8"))
    samples = obj.get("samples") or []
    if not samples:
        print("[inspect-bridge] inspect log has no samples", file=sys.stderr)
        sys.exit(5)
    # An errored sample or unfinished eval is a harness failure, not an answer
    # (upstream does not score errored samples either): fail instead of letting
    # the verifier score an empty completion as 0.
    sample_error = samples[0].get("error")
    if obj.get("status") != "success" or sample_error:
        message = (sample_error or obj.get("error") or {}).get("message", "")
        for spec in export_files:
            Path(spec["dest"]).unlink(missing_ok=True)
        print(
            f"[inspect-bridge] inspect eval status={obj.get('status')!r}, "
            f"sample error: {message or 'none'} -- failing the run",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(7)
    # Only `submit` offered means the task's tools were dropped (e.g. bare
    # `--solver react`).
    tool_names = _first_model_tool_names(samples[0])
    if tool_names is not None and set(tool_names) <= {"submit"}:
        msg = (
            "[inspect-bridge] first model call was offered only "
            f"{tool_names}; task tools were not passed to the solver"
        )
        if cfg.get("require_tools"):
            for spec in export_files:
                Path(spec["dest"]).unlink(missing_ok=True)
            print(msg + " -- failing the run (require_tools)", file=sys.stderr, flush=True)
            sys.exit(6)
        print(msg + " (WARNING)", flush=True)
    for spec in export_files:
        state = "present" if Path(spec["dest"]).is_file() else "MISSING"
        print(f"[inspect-bridge] export dest {spec['dest']}: {state}", flush=True)

    completion = (samples[0].get("output") or {}).get("completion") or ""
    Path("/app").mkdir(parents=True, exist_ok=True)
    Path("/app/answer.txt").write_text(completion, encoding="utf-8")
    print(f"[inspect-bridge] wrote {len(completion)} chars to /app/answer.txt", flush=True)

    # No score sidecar: an agent-writable score file would let agents forge
    # rewards. The verifier scores /app/answer.txt itself.


if __name__ == "__main__":
    main()
"""
