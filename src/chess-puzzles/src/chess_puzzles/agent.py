import base64
import json
import shlex

from harbor.agents.base import BaseAgent

from .process import run_worker
from .source import prepare_source


class EpochChessAgent(BaseAgent):
    @staticmethod
    def name():
        return "epoch-chess-v2"

    def version(self):
        return "2.0.1-adapter-0.2.0"

    def __init__(
        self,
        *args,
        max_output_tokens=1_000_000,
        compaction_threshold_tokens=None,
        source_dir=None,
        reasoning_effort=None,
        response_max_tokens=None,
        token_count_mode="provider",
        attempt_timeout_sec=1800,
        inspect_base_url=None,
        api_key_env="ANTHROPIC_API_KEY",
        mock_scenario=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if compaction_threshold_tokens is None:
            raise ValueError(
                "Set compaction_threshold_tokens explicitly to match the model and original run"
            )
        if int(max_output_tokens) < 1 or int(compaction_threshold_tokens) < 1:
            raise ValueError("Token budgets must be positive")
        self.budget = int(max_output_tokens)
        self.threshold = int(compaction_threshold_tokens)
        self.source_dir = source_dir
        self.effort = reasoning_effort
        self.response_max_tokens = response_max_tokens
        from .token_counting import validate_count_mode
        validate_count_mode(token_count_mode)
        self.token_count_mode = token_count_mode
        self.attempt_timeout_sec = attempt_timeout_sec
        self.inspect_base_url = inspect_base_url
        self.inspect_key_name = api_key_env
        self.mock_scenario = mock_scenario

    async def setup(self, environment):
        # Download before the trial if desired; always verify the immutable snapshot.
        prepare_source(self.source_dir)

    async def run(self, instruction, environment, context):
        result = await environment.exec(command="cat /app/problem.json")
        if result.return_code != 0:
            raise RuntimeError("Unable to read puzzle from task environment")
        problem = json.loads(result.stdout)
        if problem.get("variant") != "original":
            raise ValueError(
                "EpochChessAgent only supports the original variant; use a CLI agent for cli tasks"
            )
        from .source import upstream

        expected = upstream(self.source_dir).QUESTION_TEMPLATE.format(
            prompt=problem["fen"]
        )
        if instruction.strip() != expected.strip():
            raise ValueError("Task instruction differs from pinned upstream prompt")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        key = self._get_env(self.inspect_key_name) if self.inspect_key_name else None
        result = await run_worker(
            {
                "fen": problem["fen"],
                "sample_id": problem.get("id", 1),
                "model": self.model_name,
                "log_dir": str((self.logs_dir / "inspect").resolve()),
                "max_output_tokens": self.budget,
                "compaction_threshold_tokens": self.threshold,
                "source_dir": str(prepare_source(self.source_dir)),
                "base_url": self.inspect_base_url,
                "reasoning_effort": self.effort,
                "response_max_tokens": self.response_max_tokens,
                "token_count_mode": self.token_count_mode,
                "attempt_timeout_sec": self.attempt_timeout_sec,
                "mock_scenario": self.mock_scenario,
            },
            self.logs_dir,
            key,
        )
        answer = result["answer"]
        encoded = base64.b64encode(answer.encode()).decode()
        cmd = "printf %s " + shlex.quote(encoded) + " | base64 -d > /app/answer.txt"
        written = await environment.exec(command=cmd)
        if written.return_code != 0:
            raise RuntimeError("Unable to write submitted move")
        context.metadata = {
            "upstream_version": "2.0.1",
            "inspect_log": result["inspect_log"],
            "sample_metadata": result["sample_metadata"],
            "usage": result.get("usage", {}),
            "token_count_mode": self.token_count_mode,
        }
        context.n_cache_tokens = result.get("usage", {}).get("cache_read_tokens", 0)
        context.n_input_tokens = result["input_tokens"]
        context.n_output_tokens = result["output_tokens"]
