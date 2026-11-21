"""Scripted, explicitly labelled responses for offline integration tests only."""

def outputs(scenario):
    from inspect_ai.model import ChatCompletionChoice, ChatMessageAssistant, ModelOutput, ModelUsage
    from inspect_ai.tool import ToolCall

    if scenario == "timeout":
        async def slow(*args):
            import asyncio
            await asyncio.sleep(30)
            raise AssertionError("Inspect failed to cancel the slow response")
        return slow
    if scenario == "compact":
        turns = 0
        summaries = 0
        def compacting(messages, tools, tool_choice, config):
            nonlocal turns, summaries
            if not tools:
                summaries += 1
                result = ModelOutput.from_content(model="mockllm", content="Prior analysis is summarized.")
                result.usage = ModelUsage(input_tokens=8000, output_tokens=10, total_tokens=8010)
                return result
            turns += 1
            if turns == 1:
                result = ModelOutput.from_content(model="mockllm", content="lengthy analysis " * 3000)
                result.choices[0].stop_reason = "max_tokens"
                result.usage = ModelUsage(input_tokens=100, output_tokens=6000, total_tokens=6100)
                return result
            assert summaries >= 1, "The fixture did not actually trigger compaction"
            assert any((message.metadata or {}).get("summary") for message in messages)
            return ModelOutput(model="mockllm", choices=[ChatCompletionChoice(
                message=ChatMessageAssistant(content="", tool_calls=[ToolCall(
                    id="compacted-submission", function="submit_answer", arguments={"answer": "d4d3"}
                )]), stop_reason="stop"
            )])
        return compacting
    if scenario not in ("submit", "continue", "forced", "wrong"):
        raise ValueError("Unknown simulation scenario")
    calls = 0

    def generate(messages, tools, tool_choice, config):
        nonlocal calls
        calls += 1
        assert [tool.name for tool in tools] == ["submit_answer"]
        interrupted = calls == 1 and scenario in ("continue", "forced")
        tokens = 100 if scenario == "forced" and interrupted else 10
        # Fixed fixture for puzzle 1, not access to the dataset or a model prediction.
        answer = "a1a2" if scenario == "wrong" else "d4d3"
        message = ChatMessageAssistant(
            content="simulated truncated response" if interrupted else "",
            tool_calls=None if interrupted else [ToolCall(
                id=f"submission-{calls}", function="submit_answer", arguments={"answer": answer}
            )],
        )
        return ModelOutput(model="mockllm", choices=[ChatCompletionChoice(
            message=message, stop_reason="max_tokens" if interrupted else "stop"
        )], usage=ModelUsage(input_tokens=100, output_tokens=tokens, total_tokens=100+tokens))

    return generate
