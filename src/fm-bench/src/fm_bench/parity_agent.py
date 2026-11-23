"""Harbor agent for FM-Bench parity runs (adapter Scenario 3).

It runs the ORIGINAL FM-Bench harness, runner.llm_agent.LLMAgent, unmodified,
against the task's game sidecar. The only substitution is the game object:
RemoteGame forwards each tool call to `fm rpc` inside the agent container.

Defaults are the harness settings of the paper's Solo runs (stamped in every
run manifest): max_tokens 8000, soft/hard turn limits 40/60, flat memory,
temperature 0 (fixed inside LLMAgent).

Usage:
  export FMBENCH_ROOT=/path/to/FM-Bench        # runner/ and engine/ are imported from here
  export ANTHROPIC_API_KEY=...                 # or OPENAI_API_KEY / GEMINI_API_KEY / ...
  PYTHONPATH=src/fm-bench/src uvx --from harbor \\
      --with-requirements $FMBENCH_ROOT/requirements.txt \\
      harbor run -p datasets/fm-bench \\
      --agent-import-path fm_bench.parity_agent:FMBenchParityAgent -m <model>

The original runner runs inside Harbor's Python process, so that process needs
the runner's packages (requirements.txt); Harbor alone does not ship `anthropic`.

The matching original-side command is in the adapter README.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shlex
import sys
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from fm_bench.remote_game import RemoteGame


class _Recorder:
    """Writes the trajectory to the trial's agent log dir (LLMAgent hooks)."""

    def __init__(self, logs_dir: Path):
        self.dir = logs_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _append(self, name: str, rec: dict) -> None:
        with open(self.dir / name, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")

    def action(self, stop_id, tool, args) -> None:
        self._append("actions.jsonl", {"args": args, "stop_id": stop_id,
                                       "tool": tool, "type": "action"})

    def turn(self, stop_id, turn, text, tool_calls, served_model=None) -> None:
        self._append("transcript.jsonl", {
            "served_model": served_model, "stop_id": stop_id, "text": text,
            "tool_calls": tool_calls, "turn": turn})

    def stop_end(self, stop_id, cost_summary, diagnostics, error_codes=None) -> None:
        self._append("actions.jsonl", {"stop_id": stop_id, "type": "stop_end"})
        self._append("stops.jsonl", {"cost": cost_summary, "diagnostics": diagnostics,
                                     "error_codes": error_codes or {},
                                     "stop_id": stop_id})

    def suspend(self, cost_summary) -> None:
        self._append("stops.jsonl", {"cost": cost_summary, "type": "suspended"})

    def finish(self, result) -> None:
        (self.dir / "result.json").write_text(
            json.dumps(result, indent=1, sort_keys=True, default=str), encoding="utf-8")


class FMBenchParityAgent(BaseAgent):
    """Runs the original LLMAgent on the host; only its tool calls enter the task.

    The model loop, prompts, retries and cost accounting are the original
    runner's. Each tool call is one `fm rpc` command executed in the agent
    container, which forwards it to the game sidecar.
    """

    def __init__(self, *args, fmbench_root: str | None = None,
                 max_tokens: int = 8000, soft_turn_limit: int = 40,
                 hard_turn_limit: int = 60, memory_mode: str = "flat",
                 spend_cap_usd: float | None = 400.0,
                 rpc_timeout_sec: int = 900, **kwargs):
        super().__init__(*args, **kwargs)
        self._root = Path(fmbench_root or os.environ.get("FMBENCH_ROOT", "")).resolve()
        self._max_tokens = max_tokens
        self._soft = soft_turn_limit
        self._hard = hard_turn_limit
        self._memory_mode = memory_mode
        self._spend_cap = spend_cap_usd
        self._rpc_timeout = rpc_timeout_sec

    @staticmethod
    def name() -> str:
        return "fm-bench-parity-agent"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    async def run(self, instruction: str, environment: BaseEnvironment,
                  context: AgentContext) -> None:
        if not (self._root / "runner" / "llm_agent.py").exists():
            raise RuntimeError("set FMBENCH_ROOT (or fmbench_root=) to an FM-Bench "
                               "checkout: the original runner is imported from it")
        if not self.model_name:
            raise RuntimeError("model_name is required")
        # the original harness is imported from the checkout, not vendored
        sys.path.insert(0, str(self._root))
        from engine.actions.validate import ValidationError
        from runner.keys import find_api_key, provider_for_model
        from runner.llm_agent import LLMAgent

        # the original runner takes bare provider model ids
        model = self.model_name.split("/", 1)[1] if (
            self.model_name.split("/", 1)[0] in ("anthropic", "openai", "google", "gemini")
        ) else self.model_name
        provider = provider_for_model(model)
        key = find_api_key(provider)
        if key is None:
            raise RuntimeError(f"no {provider} API key found in the environment")

        loop = asyncio.get_running_loop()

        def rpc(name: str, args: dict) -> dict:
            # called from the worker thread that runs the synchronous runner
            payload = base64.b64encode(
                json.dumps({"name": name, "args": args}).encode("utf-8")).decode("ascii")
            fut = asyncio.run_coroutine_threadsafe(
                environment.exec(f"fm rpc {shlex.quote(payload)}",
                                 timeout_sec=self._rpc_timeout), loop)
            res = fut.result()
            if res.return_code != 0:
                raise RuntimeError(f"fm rpc {name} failed ({res.return_code}): "
                                   f"{(res.stderr or res.stdout or '')[-400:]}")
            return json.loads((res.stdout or "").strip().splitlines()[-1])

        # cap_mode "settle": a run that hits the spend cap stops and is scored
        # as it stands, as in the paper's runs
        llm = LLMAgent(model=model, api_key=key, spend_cap_usd=self._spend_cap,
                       verbose=False, recorder=_Recorder(Path(self.logs_dir)),
                       max_tokens=self._max_tokens, soft_turn_limit=self._soft,
                       hard_turn_limit=self._hard, memory_mode=self._memory_mode,
                       cap_mode="settle")
        game = RemoteGame(rpc, ValidationError)
        # LLMAgent.play is synchronous: run it in a worker thread so the event
        # loop stays free to execute its rpc calls
        result = await asyncio.to_thread(llm.play, game)

        # report tokens and cost to Harbor; the reward comes from the verifier
        cost = result.get("cost") or llm.cost.summary()
        context.n_input_tokens = (cost.get("input_tokens", 0)
                                  + cost.get("cache_read_tokens", 0)
                                  + cost.get("cache_write_tokens", 0))
        context.n_cache_tokens = cost.get("cache_read_tokens", 0)
        context.n_output_tokens = cost.get("output_tokens", 0)
        context.cost_usd = cost.get("cost_usd")
        context.metadata = {"diagnostics": result.get("diagnostics"),
                            "s_final_seen_by_agent": result.get("s_final"),
                            "settle_reason": result.get("settle_reason")}
