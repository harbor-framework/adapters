"""Run one DeepSearchQA question through FrontierAgent's ReAct pipeline.

This script is shared by BOTH sides of the parity experiment, so the agent
code path is identical:

* Harbor side: ``DeepSearchQAFrontierAgent`` (frontier_agent.py) spawns it once
  per trial.
* Original side: ``run_original.py`` in the parity repo spawns it once per
  question.

Both sides launch it through ``frontier_launcher.run_worker``, inside a fresh
container of FrontierAgent's own Docker image (working directory ``/app``,
``SANDBOX_BACKEND=container``): FrontierAgent discovers its workflows via
relative paths and refuses to run tools on an unisolated host. One process per
question mirrors FrontierAgent's own runner
(``benchmarks/public/runner/run_one_task.py``), because ``BenchmarkSession``
mutates a process-global service registry.

The agent input is built with FrontierAgent's own ``_render_instruction``
(``# Task\\n\\n{question}\\n``), the same text its standalone DeepSearchQA runner
sends. No task metadata is passed on either side: for DeepSearchQA,
FrontierAgent's metadata does not select any sandbox profile, so it would have
no effect anyway, and ``answer_type`` must never reach the agent.

Output: a JSON file with ``predicted`` (the agent's final answer, verbatim),
``error`` and ``duration_seconds``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--question-file", required=True, type=Path,
                   help="Plain-text file containing only the DeepSearchQA prompt")
    p.add_argument("--trial-dir", required=True, type=Path,
                   help="Directory for FrontierAgent logs and artifacts")
    p.add_argument("--out", required=True, type=Path, help="Result JSON path")
    p.add_argument("--timeout-sec", type=float, default=None,
                   help="Optional pipeline timeout")
    return p.parse_args()


async def _run(args: argparse.Namespace) -> dict:
    root = Path.cwd()
    sys.path.insert(0, str(root))

    from dotenv import load_dotenv

    load_dotenv(root / ".env")

    from harbor.models.agent.context import AgentContext

    from benchmarks.public.core.harbor_task_generator import _render_instruction
    from benchmarks.public.harbor_agent.agent import FrontierAgentAgent

    question = args.question_file.read_text(encoding="utf-8").strip()
    instruction = _render_instruction(question, None)

    trial_dir = args.trial_dir.resolve()
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "instruction.md").write_text(instruction, encoding="utf-8")

    agent = FrontierAgentAgent(logs_dir=trial_dir, model_name=None)
    await agent.setup(MagicMock(spec=[]), db_path=str(trial_dir / "kernel.db"))

    context = AgentContext()
    t0 = time.monotonic()
    error = None
    try:
        await asyncio.wait_for(
            agent.run(instruction, MagicMock(), context), timeout=args.timeout_sec
        )
    except TimeoutError:
        error = f"timeout after {args.timeout_sec}s"
    except Exception as exc:  # recorded, not swallowed: see "error" in the output
        error = f"{type(exc).__name__}: {exc}"

    answer_file = trial_dir / "agent" / "final_answer.txt"
    predicted = answer_file.read_text(encoding="utf-8") if answer_file.exists() else ""
    pipeline_error_log = trial_dir / "agent" / "error.log"
    return {
        "predicted": predicted,
        "error": error,
        "pipeline_errors": (
            pipeline_error_log.read_text(encoding="utf-8")
            if pipeline_error_log.exists()
            else None
        ),
        "duration_seconds": round(time.monotonic() - t0, 2),
        "openai_model": os.environ.get("OPENAI_MODEL", ""),
    }


def main() -> None:
    args = _parse_args()
    try:
        result = asyncio.run(_run(args))
        code = 0
    except Exception as exc:
        result = {"predicted": "", "error": f"worker crashed: {type(exc).__name__}: {exc}"}
        code = 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.stdout.flush()
    sys.stderr.flush()
    # FrontierAgent's kernel keeps a non-daemon aiosqlite thread alive, which
    # blocks interpreter shutdown (same workaround as run_one_task.py).
    os._exit(code)


if __name__ == "__main__":
    main()
