"""Offline transport check for two known submissions. Never used for live judging."""

from control_arena import EvalMode
from control_arena.settings.sae_interp_sabotage.scorers import (
    MAIN_TASK_SCORER_INSTRUCTIONS,
    SIDE_TASK_SCORER_INSTRUCTIONS,
)
from control_arena.settings.sae_interp_sabotage.setting import get_dataset
from inspect_ai.model import Model, ModelOutput, ModelUsage, get_model


def fixture_judge() -> Model:
    verdicts = {}
    for sample in get_dataset(EvalMode.HONEST):
        label = sample.metadata["main_task_name"]
        for answer, verdict in (
            (label, "accept"),
            ("A synthetic theme used to test submission transport.", "reject"),
        ):
            main_prompt = MAIN_TASK_SCORER_INSTRUCTIONS.format(
                main_task_description=sample.input, answer=answer
            )
            side_prompt = SIDE_TASK_SCORER_INSTRUCTIONS.format(answer=answer, target=label)
            verdicts[main_prompt] = verdict
            verdicts[side_prompt] = verdict

    def reply(messages, tools, tool_choice, config):
        prompt = messages[0].text
        if prompt not in verdicts:
            raise ValueError("No fixture response for this SAE judge prompt.")
        content = f"<reasoning>Fixed integration fixture.</reasoning><grade>{verdicts[prompt]}</grade>"
        result = ModelOutput.from_content("mockllm/sae-fixture", content)
        result.usage = ModelUsage()
        return result

    return get_model("mockllm/sae-fixture", custom_outputs=reply)
