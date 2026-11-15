"""The Inspect bridge harness fails the run when Inspect reports an error.

Runs the embedded harness (`HARNESS_PY`) against a fake `inspect` executable
that writes a canned eval log, with the container paths redirected to a temp
directory. An errored sample must end in a non-zero exit and no answer file
(Harbor then records an agent error); a successful sample writes its
completion to the answer file.
"""

from __future__ import annotations

import ast
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

AGENT_PY = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "asta_bench"
    / "inspect_solver"
    / "agent.py"
)


def _module_string(name: str) -> str:
    # Read the constant from source: importing agent.py needs `harbor`, which
    # the offline test environment does not have.
    for node in ast.parse(AGENT_PY.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise KeyError(name)


HARNESS_PY = _module_string("HARNESS_PY")

ERROR_LOG = {
    "status": "error",
    "error": {"message": "TypeError('Cannot instantiate typing.Union')"},
    "samples": [
        {
            "id": "s1",
            "error": {"message": "TypeError('Cannot instantiate typing.Union')"},
            "output": {"completion": ""},
            "events": [],
        }
    ],
}

SUCCESS_LOG = {
    "status": "success",
    "samples": [
        {
            "id": "s1",
            "output": {"completion": '{"answer": 42}'},
            "events": [{"event": "model", "tools": [{"name": "python_session"}]}],
        }
    ],
}


def _run(tmp_path: Path, log: dict) -> tuple[subprocess.CompletedProcess, Path]:
    log_dir = tmp_path / "inspect-logs"
    app_dir = tmp_path / "app"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_inspect = bin_dir / "inspect"
    fake_inspect.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"d = pathlib.Path({str(log_dir)!r}); d.mkdir(parents=True, exist_ok=True)\n"
        f"(d / 'log.json').write_text({json.dumps(json.dumps(log))})\n"
    )
    fake_inspect.chmod(fake_inspect.stat().st_mode | stat.S_IEXEC)

    script = HARNESS_PY.replace("/logs/agent/inspect-logs", str(log_dir)).replace(
        '"/app', f'"{app_dir}'
    )
    harness = tmp_path / "harness.py"
    harness.write_text(script)

    config = tmp_path / "inspect_config.json"
    config.write_text(json.dumps({"task": "astabench/fake", "sample_id": "s1"}))
    payload = {
        "solver": "astabench/react",
        "model_name": "anthropic/claude-haiku-4-5",
        "cli_config_path": str(config),
        "config_path_primary": str(config),
        "config_path_alt": str(config),
    }
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "__INSPECT_BRIDGE_PAYLOAD": json.dumps(payload),
    }
    proc = subprocess.run(
        [sys.executable, str(harness)], env=env, capture_output=True, text=True
    )
    return proc, app_dir / "answer.txt"


def test_errored_sample_fails_the_run(tmp_path: Path) -> None:
    proc, answer = _run(tmp_path, ERROR_LOG)
    assert proc.returncode == 7, proc.stdout + proc.stderr
    assert "Cannot instantiate typing.Union" in proc.stderr
    assert not answer.exists()


def test_successful_sample_writes_answer(tmp_path: Path) -> None:
    proc, answer = _run(tmp_path, SUCCESS_LOG)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert answer.read_text() == '{"answer": 42}'


def test_bridge_installs_pin_anthropic() -> None:
    # inspect_ai 0.3.203 breaks on anthropic>=2; both install paths pin the
    # version from the fork's uv.lock.
    from asta_bench.benchmarks import base

    assert base._INSPECT_BRIDGE_DOCKERFILE_SNIPPET.count("'anthropic==0.97.0'") == 2
    assert _module_string("DEFAULT_ANTHROPIC_VERSION") == "0.97.0"
    assert "anthropic=={DEFAULT_ANTHROPIC_VERSION}" in AGENT_PY.read_text()
    assert "'pyarrow==24.0.0'" in base._INSPECT_BRIDGE_DOCKERFILE_SNIPPET
    assert "'pyarrow==24.0.0'" in AGENT_PY.read_text()


# Needs Harbor (not in the offline test environment); run with
# `uv run --with 'harbor==0.26.0' ... pytest tests/test_inspect_bridge_harness.py`.
FAILURE_OUTPUTS = {
    "[inspect-bridge] inspect eval status='error', sample error: "
    "TypeError('Cannot instantiate typing.Union') -- failing the run": "InspectHarnessError",
    "Error: No inspect tasks were found at the specified paths.": "InspectHarnessError",
    "sample error: InternalServerError('Error code: 500')": "ApiInternalServerError",
    "sample error: APIStatusError('Error code: 529 - overloaded_error')": "ApiOverloadedError",
    "sample error: APIConnectionError('Connection error.')": "UnknownApiError",
}


def test_bridge_failures_never_count_as_rewards(tmp_path: Path) -> None:
    import asyncio
    from types import SimpleNamespace

    import pytest
    import yaml

    pytest.importorskip("harbor")
    from harbor.models.job.config import JobConfig
    from harbor.models.trial.error_policy import policy_for

    from asta_bench.inspect_solver.agent import InspectSolver

    job_yaml = Path(__file__).resolve().parents[1] / "run_asta-bench_inspect-ai.yaml"
    overrides = JobConfig.model_validate(
        yaml.safe_load(job_yaml.read_text().replace("${", "$${"))
    ).override_error_policy

    class FailingEnv:
        def __init__(self, output: str) -> None:
            self.output = output

        async def exec(self, command, **kwargs):
            return SimpleNamespace(return_code=7, stdout=self.output, stderr="")

    for output, expected in FAILURE_OUTPUTS.items():
        agent = InspectSolver(logs_dir=tmp_path, model_name="anthropic/claude-haiku-4-5")
        with pytest.raises(Exception) as info:
            asyncio.run(agent.run("x", FailingEnv(output), SimpleNamespace()))
        name = type(info.value).__name__
        assert name == expected, output
        assert not policy_for(name, overrides.get(name)).has_valid_reward, name
