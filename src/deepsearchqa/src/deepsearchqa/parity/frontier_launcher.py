"""Launch ``frontier_worker.py`` in FrontierAgent's Docker image (shared by both parity sides).

FrontierAgent refuses to execute tools on an unisolated host: it needs
bubblewrap (Linux only) or ``SANDBOX_BACKEND=container`` inside an isolated
container. On macOS the supported route is Docker, so every question runs in a
fresh container built from the pinned FrontierAgent checkout, with
``SANDBOX_BACKEND=container``. The container is the isolation boundary.

Both the Harbor-side agent (``frontier_agent.py``) and the original-side
runner (``run_original.py`` in the parity repo) call :func:`run_worker`, so the
agent's runtime, image, environment variables and failure handling are
identical on both sides.

Configuration (environment variables):

* ``FRONTIER_AGENT_IMAGE``: image tag built from the pinned checkout
  (``docker build -t frontier-agent:<commit> .``).
* ``FRONTIER_AGENT_ENV_FILE``: env file with the model / search settings
  (OPENAI_*, WEB_SEARCH_PROVIDER, ...).

Standard library only.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
PIPELINE_ERROR_PREFIX = "Pipeline error:"


def _docker() -> str:
    found = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    if not Path(found).exists():
        raise RuntimeError("docker CLI not found on PATH")
    return found


def config() -> tuple[str, Path]:
    image = os.environ.get("FRONTIER_AGENT_IMAGE", "").strip()
    env_file = os.environ.get("FRONTIER_AGENT_ENV_FILE", "").strip()
    if not image or not env_file:
        raise RuntimeError("Set FRONTIER_AGENT_IMAGE and FRONTIER_AGENT_ENV_FILE")
    env_path = Path(env_file).expanduser().resolve()
    if not env_path.is_file():
        raise RuntimeError(f"FRONTIER_AGENT_ENV_FILE not found: {env_path}")
    return image, env_path


def classify(result: dict) -> str | None:
    """Return an exception string for infrastructure failures, else None.

    A run counts as an exception (not a score) only when no agent trajectory
    was produced: the worker crashed, or FrontierAgent's pipeline raised before
    answering. A pipeline that ran but found no answer is graded as-is
    (``<ANSWER_NOT_FOUND>`` is sent to the judge on both sides).

    An agent timeout is the agent's own failure, not infrastructure: it is
    scored as an empty answer (F1 = 0) on both sides. On the Harbor side the
    trial is cancelled at the task's agent timeout, no ``answer.txt`` is
    written, and the verifier scores it ``empty_response``; the original-side
    runner does the same with an empty prediction.
    """
    error = str(result.get("error") or "")
    if error.startswith("worker crashed"):
        return error
    pipeline = str(result.get("pipeline_errors") or "")
    if pipeline.startswith(PIPELINE_ERROR_PREFIX):
        return pipeline.splitlines()[0]
    return None


async def run_worker(question: str, trial_dir: Path, timeout_sec: float) -> dict:
    """Run one question in a fresh FrontierAgent container; return the worker result."""
    image, env_file = config()
    trial_dir = trial_dir.resolve()
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "question.txt").write_text(question, encoding="utf-8")
    result_file = trial_dir / "frontier_result.json"
    result_file.unlink(missing_ok=True)

    name = f"dsqa-frontier-{uuid.uuid4().hex[:12]}"
    cmd = [
        _docker(), "run", "--rm", "--init", "--name", name,
        "--env-file", str(env_file),
        "-e", "SANDBOX_BACKEND=container",
        "-v", f"{PARITY_DIR}:/dsqa:ro",
        "-v", f"{trial_dir}:/trial",
        "-w", "/app", "--entrypoint", "python",
        image,
        "/dsqa/frontier_worker.py",
        "--question-file", "/trial/question.txt",
        "--trial-dir", "/trial/frontier",
        "--out", "/trial/frontier_result.json",
    ]
    (trial_dir / "frontier_cmd.json").write_text(
        json.dumps({"image": image, "cmd": cmd[1:]}, indent=2), encoding="utf-8"
    )

    async def _kill() -> None:
        killer = await asyncio.create_subprocess_exec(
            _docker(), "kill", name,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()

    with open(trial_dir / "frontier_worker.log", "wb") as log:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=log, stderr=asyncio.subprocess.STDOUT
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout_sec)
        except TimeoutError:
            await _kill()
            await proc.wait()
            return {"predicted": "", "error": f"agent timeout after {timeout_sec}s"}
        except asyncio.CancelledError:  # e.g. Harbor's own agent timeout
            await _kill()
            await proc.wait()
            raise

    if not result_file.exists():
        return {
            "predicted": "",
            "error": f"worker crashed: docker exit {proc.returncode}, no result "
                     f"(see {trial_dir / 'frontier_worker.log'})",
        }
    return json.loads(result_file.read_text(encoding="utf-8"))
