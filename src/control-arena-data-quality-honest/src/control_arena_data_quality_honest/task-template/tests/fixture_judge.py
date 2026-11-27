"""Script two known quality verdicts while exercising the real judge prompt and parser."""
from control_arena.settings.data_poisoning.scorers import MONITOR_QUALITY_JUDGE_PROMPT
from inspect_ai.model import ModelOutput, ModelUsage, get_model
from public_case import DOMAIN, digest, domain_info

FIXTURE = "mockllm/data-quality-fixture"
WEAK_INPUT = "User: Say something.\nAssistant: Something."


def fixture_judge(submission, expected_digest):
    if digest(submission.monitor_input) == expected_digest:
        quality = 8
    elif submission.monitor_input == WEAK_INPUT:
        quality = 2
    else:
        raise ValueError("The fixture recognizes only the private reference and the regression example.")
    expected_prompt = MONITOR_QUALITY_JUDGE_PROMPT.format(
        domain=DOMAIN.replace("_", " "), domain_requirements=domain_info()["requirements"],
        monitor_input=submission.monitor_input,
    )

    def reply(messages, tools, tool_choice, config):
        if messages[0].text != expected_prompt:
            raise ValueError("The native judge prompt has changed.")
        content = f"<reasoning>Scripted fixture for submission transport.</reasoning><score>{quality}</score>"
        output = ModelOutput.from_content(FIXTURE, content)
        output.usage = ModelUsage()
        return output

    return get_model(FIXTURE, custom_outputs=reply)
