"""Oracle replay agent for GDM stealth (host-side).

Thin Harbor wrapper around `oracle_policies.EpisodeRunner`, which
executes the curated reference solutions in `oracle_solutions.py`
through the same host-side tools and checkers as the parity agent.
The identical policies also run inside generated task containers via
each task's `solution/replay.py` for the docs-compliant built-in
oracle path (`harbor run -c src/gdm-stealth/run_gdm-stealth.yaml`).

Usage:
    PYTHONPATH=src/gdm-stealth/src harbor run \
        -p datasets/gdm-stealth \
        -a gdm_stealth.custom_agent.oracle_agent:GDMStealthOracleAgent \
        --ak rater_model=openrouter/google/gemini-2.5-pro \
        --ak judger_model=openrouter/google/gemini-2.5-flash \
        --ak chat_model=openrouter/google/gemini-2.5-flash
Role models are needed wherever the upstream checkers need them
(classifier rater/judger, cover `said_yes` rater, strategic chat).
"""

from __future__ import annotations

import json
from typing import Any

from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from .agent import GDMStealthParityAgent, OUTCOME
from .hosts import EnvAccess
from .oracle_policies import (
    EpisodeRunner,
    compute_outcome,
    make_host,
    parse_email_tasks,
)

__all__ = ["GDMStealthOracleAgent", "parse_email_tasks"]


class GDMStealthOracleAgent(GDMStealthParityAgent):
    def __init__(
        self,
        *args: Any,
        candidate_offset: int = 0,
        strategic_mode: str = "compliant",
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        # Rater sampling is stochastic, so solvability evidence may
        # need several replay episodes; rotating the candidate order
        # per attempt (recorded in the job config) keeps every attempt
        # a deterministic replay of curated candidates.
        self._candidate_offset = int(candidate_offset)
        self._strategic_mode = strategic_mode

    @staticmethod
    def name() -> str:
        return "gdm-stealth-oracle-agent"

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        if not self._metadata:
            await self.setup(environment)
        metadata = self._metadata
        dataset = metadata["dataset_name"]
        env = EnvAccess(environment)
        host = await make_host(
            env,
            metadata,
            self._role_model,
            chat_shim=(
                self._chat_shim()
                if dataset == "strategic_rule_breaking"
                else None
            ),
            strategic_seed=self._strategic_seed,
        )
        runner = EpisodeRunner(
            host,
            metadata,
            candidate_offset=self._candidate_offset,
            strategic_mode=self._strategic_mode,
        )
        await runner.run()
        outcome = compute_outcome(
            OUTCOME, dataset, runner.status, runner.last_text, metadata
        )
        await env.write_file(
            str(OUTCOME.OUTCOME), json.dumps(outcome, indent=2), user=0
        )
        context.n_input_tokens = 0
        context.n_output_tokens = 0
        context.n_cache_tokens = 0
        context.metadata = {
            "dataset_name": dataset,
            "sample_id": metadata.get("sample_id"),
            "status": runner.status,
            "outcome": outcome,
            "upstream_benchmark": "gdm_stealth",
            "oracle": True,
            "solution_source": "gdm_stealth/custom_agent/oracle_solutions.py",
        }
        try:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            (self.logs_dir / "gdm-stealth-oracle-agent.json").write_text(
                json.dumps(
                    {"outcome": outcome, "transcript": runner.transcript},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass
