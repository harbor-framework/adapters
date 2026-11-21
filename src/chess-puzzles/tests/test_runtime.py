import json
from types import SimpleNamespace

import pytest
from inspect_ai.model import (
    ChatCompletionChoice,
    ChatMessageAssistant,
    ModelOutput,
    ModelUsage,
    get_model,
)
from inspect_ai.tool import ToolCall

from chess_puzzles.agent import EpochChessAgent
from chess_puzzles.runtime import run_upstream
from chess_puzzles.source import upstream

FEN = "6k1/3R4/2N3p1/PpPp4/1P1r4/5r2/6K1/8 b - - 3 56"


def output(answer=None, stop="stop", tokens=10):
    message = ChatMessageAssistant(
        content="thinking" if answer is None else "",
        tool_calls=None
        if answer is None
        else [
            ToolCall(
                id="submission", function="submit_answer", arguments={"answer": answer}
            )
        ],
    )
    return ModelOutput(
        model="mockllm",
        choices=[ChatCompletionChoice(message=message, stop_reason=stop)],
        usage=ModelUsage(
            input_tokens=100, output_tokens=tokens, total_tokens=100 + tokens
        ),
    )


@pytest.mark.parametrize("scenario", ["submit", "continue", "forced"])
async def test_actual_upstream_solver(tmp_path, scenario):
    calls = []

    def generate(messages, tools, tool_choice, config):
        calls.append((messages, tools, tool_choice, config))
        assert [t.name for t in tools] == ["submit_answer"]
        if scenario != "submit" and len(calls) == 1:
            return output(stop="max_tokens", tokens=100 if scenario == "forced" else 10)
        return output("d4d3")

    model = get_model("mockllm/model", custom_outputs=generate, memoize=False)
    answer, log = await run_upstream(
        FEN, model, tmp_path, 100 if scenario == "forced" else 10000, 100000
    )
    assert answer == "d4d3"
    assert len(calls) == (1 if scenario == "submit" else 2)
    assert log.samples[0].metadata["forced_final_answer"] == (scenario == "forced")
    assert "Stockfish" not in str(calls[0][0])


async def test_harbor_agent_bridge(tmp_path, monkeypatch):
    class Environment:
        answer = None

        async def exec(self, command):
            import base64
            import shlex

            if command == "cat /app/problem.json":
                return SimpleNamespace(
                    return_code=0,
                    stdout=json.dumps({"fen": FEN, "variant": "original"}),
                )
            args = shlex.split(command)
            self.answer = base64.b64decode(args[2]).decode()
            return SimpleNamespace(return_code=0, stdout="")

    async def solve(request, logs_dir, key):
        assert request["fen"] == FEN
        assert request["token_count_mode"] == "local"
        return {
            "answer": "d4d3",
            "inspect_log": "test.eval",
            "sample_metadata": {},
            "input_tokens": 0,
            "output_tokens": 0,
        }

    monkeypatch.setattr("chess_puzzles.agent.run_worker", solve)
    env = Environment()
    agent = EpochChessAgent(
        logs_dir=tmp_path,
        model_name="mockllm/model",
        compaction_threshold_tokens=100000,
        token_count_mode="local",
    )
    await agent.setup(env)
    context = SimpleNamespace()
    await agent.run(upstream().QUESTION_TEMPLATE.format(prompt=FEN), env, context)
    assert env.answer == "d4d3"
    assert context.metadata["upstream_version"] == "2.0.1"


def test_requires_explicit_threshold(tmp_path):
    with pytest.raises(ValueError, match="compaction"):
        EpochChessAgent(logs_dir=tmp_path, model_name="mockllm/model")


async def test_custom_agent_rejects_cli(tmp_path):
    class Environment:
        async def exec(self, command):
            return SimpleNamespace(
                return_code=0, stdout=json.dumps({"fen": FEN, "variant": "cli"})
            )

    agent = EpochChessAgent(
        logs_dir=tmp_path,
        model_name="mockllm/model",
        compaction_threshold_tokens=100000,
    )
    with pytest.raises(ValueError, match="original variant"):
        await agent.run("CLI instruction", Environment(), SimpleNamespace())
