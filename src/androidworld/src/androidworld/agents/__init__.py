"""Harbor custom agents for AndroidWorld."""

from __future__ import annotations

from typing import Any

from androidworld.agents.llm import ERROR_CALLING_LLM, LlmPrediction, T3ALlmClient
from androidworld.agents.t3a_core import (
    ACTION_SELECTION_PROMPT_TEMPLATE,
    DEFAULT_MAX_RETRY,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    GUIDANCE,
    PROMPT_PREFIX,
    SUMMARIZATION_PROMPT_TEMPLATE,
    TRIGGER_SAFETY_CLASSIFIER,
    BoundingBox,
    JSONAction,
    UIElement,
    action_selection_prompt,
    allocate_step_budget,
    extract_json,
    generate_ui_elements_description_list_full,
    parse_reason_action_output,
    summarize_prompt,
    validate_ui_element,
)
from androidworld.agents.trajectory import (
    T3A_RESULT_FILENAME,
    T3AActionObservation,
    T3ATrajectoryRecorder,
)

__all__ = [
    "ACTION_SELECTION_PROMPT_TEMPLATE",
    "BoundingBox",
    "DEFAULT_MAX_RETRY",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "ERROR_CALLING_LLM",
    "GUIDANCE",
    "JSONAction",
    "LlmPrediction",
    "PROMPT_PREFIX",
    "SUMMARIZATION_PROMPT_TEMPLATE",
    "T3A_RESULT_FILENAME",
    "T3AActionObservation",
    "T3AAgent",
    "T3AAgentOptions",
    "T3ALlmClient",
    "T3ATrajectoryRecorder",
    "TRIGGER_SAFETY_CLASSIFIER",
    "UIElement",
    "action_selection_prompt",
    "allocate_step_budget",
    "extract_json",
    "generate_ui_elements_description_list_full",
    "parse_reason_action_output",
    "summarize_prompt",
    "validate_ui_element",
]


def __getattr__(name: str) -> Any:
    if name in {"T3AAgent", "T3AAgentOptions"}:
        from androidworld.agents import t3a_agent

        return getattr(t3a_agent, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
