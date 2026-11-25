"""Upstream-exact T3A prompts, UI element formatting, and JSON action parsing.

Kept free of Harbor and ``android_world`` imports so it can be shared identically
by the Harbor host agent, the container environment bridge, the upstream parity
runner, and offline unit tests.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import re
from typing import Any, Optional

DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 1000
DEFAULT_MAX_RETRY = 3
TRIGGER_SAFETY_CLASSIFIER = "Triggered LLM safety classifier."

PROMPT_PREFIX = (
    "You are an agent who can operate an Android phone on behalf of a user."
    " Based on user's goal/request, you may\n"
    '- Answer back if the request/goal is a question (or a chat message), like'
    ' user asks "What is my schedule for today?".\n'
    "- Complete some tasks described in the requests/goals by performing"
    " actions (step by step) on the phone.\n\n"
    "When given a user request, you will try to complete it step by step. At"
    " each step, a list of descriptions for most UI elements on the"
    " current screen will be given to you (each element can be specified by an"
    " index), together with a history of what you have done in previous steps."
    " Based on these pieces of information and the goal, you must choose to"
    " perform one of the action in the following list (action description"
    " followed by the JSON format) by outputing the action in the correct JSON"
    " format.\n"
    "- If you think the task has been completed, finish the task by using the"
    " status action with complete as goal_status:"
    ' `{{"action_type": "status", "goal_status": "complete"}}`\n'
    "- If you think the task is not"
    " feasible (including cases like you don't have enough information or can"
    " not perform some necessary actions), finish by using the `status` action"
    " with infeasible as goal_status:"
    ' `{{"action_type": "status", "goal_status": "infeasible"}}`\n'
    "- Answer user's question:"
    ' `{{"action_type": "answer", "text": "<answer_text>"}}`\n'
    "- Click/tap on a UI element (specified by its index) on the screen:"
    ' `{{"action_type": "click", "index": <target_index>}}`.\n'
    "- Long press on a UI element (specified by its index) on the screen:"
    ' `{{"action_type": "long_press", "index": <target_index>}}`.\n'
    "- Type text into an editable text field (specified by its index), this"
    " action contains clicking the text field, typing in the text and pressing"
    " the enter, so no need to click on the target field to start:"
    ' `{{"action_type": "input_text", "text": <text_input>, "index":'
    " <target_index>}}`\n"
    '- Press the Enter key: `{{"action_type": "keyboard_enter"}}`\n'
    '- Navigate to the home screen: `{{"action_type": "navigate_home"}}`\n'
    '- Navigate back: `{{"action_type": "navigate_back"}}`\n'
    "- Scroll the screen or a scrollable UI element in one of the four"
    " directions, use the same numeric index as above if you want to scroll a"
    " specific UI element, leave it empty when scroll the whole screen:"
    ' `{{"action_type": "scroll", "direction": <up, down, left, right>,'
    ' "index": <optional_target_index>}}`\n'
    "- Open an app (nothing will happen if the app is not installed):"
    ' `{{"action_type": "open_app", "app_name": <name>}}`\n'
    '- Wait for the screen to update: `{{"action_type": "wait"}}`\n'
)

GUIDANCE = (
    "Here are some useful guidelines you need to follow:\n"
    "General\n"
    "- Usually there will be multiple ways to complete a task, pick the"
    " easiest one. Also when something does not work as expected (due"
    " to various reasons), sometimes a simple retry can solve the problem,"
    " but if it doesn't (you can see that from the history), try to"
    " switch to other solutions.\n"
    "- Sometimes you may need to navigate the phone to gather information"
    " needed to complete the task, for example if user asks"
    ' "what is my schedule tomorrow", then you may want to open the calendar'
    " app (using the `open_app` action), look up information there, answer"
    " user's question (using the `answer` action) and finish (using"
    " the `status` action with complete as goal_status).\n"
    "- For requests that are questions (or chat messages), remember to use"
    " the `answer` action to reply to user explicitly before finish!"
    " Merely displaying the answer on the screen is NOT sufficient (unless"
    ' the goal is something like "show me ...").\n'
    "- If the desired state is already achieved (e.g., enabling Wi-Fi when"
    " it's already on), you can just complete the task.\n"
    "Action Related\n"
    "- Use the `open_app` action whenever you want to open an app"
    " (nothing will happen if the app is not installed), do not use the"
    " app drawer to open an app unless all other ways have failed.\n"
    "- Use the `input_text` action whenever you want to type"
    " something (including password) instead of clicking characters on the"
    " keyboard one by one. Sometimes there is some default text in the text"
    " field you want to type in, remember to delete them before typing.\n"
    "- For `click`, `long_press` and `input_text`, the index parameter you"
    " pick must be VISIBLE in the screenshot and also in the UI element"
    " list given to you (some elements in the list may NOT be visible on"
    " the screen so you can not interact with them).\n"
    "- Consider exploring the screen by using the `scroll`"
    " action with different directions to reveal additional content.\n"
    "- The direction parameter for the `scroll` action can be confusing"
    " sometimes as it's opposite to swipe, for example, to view content at the"
    ' bottom, the `scroll` direction should be set to "down". It has been'
    " observed that you have difficulties in choosing the correct direction, so"
    " if one does not work, try the opposite as well.\n"
    "Text Related Operations\n"
    "- Normally to select some text on the screen: <i> Enter text selection"
    " mode by long pressing the area where the text is, then some of the words"
    " near the long press point will be selected (highlighted with two pointers"
    " indicating the range) and usually a text selection bar will also appear"
    " with options like `copy`, `paste`, `select all`, etc."
    " <ii> Select the exact text you need. Usually the text selected from the"
    " previous step is NOT the one you want, you need to adjust the"
    " range by dragging the two pointers. If you want to select all text in"
    " the text field, simply click the `select all` button in the bar.\n"
    "- At this point, you don't have the ability to drag something around the"
    " screen, so in general you can not select arbitrary text.\n"
    "- To delete some text: the most traditional way is to place the cursor"
    " at the right place and use the backspace button in the keyboard to"
    " delete the characters one by one (can long press the backspace to"
    " accelerate if there are many to delete). Another approach is to first"
    " select the text you want to delete, then click the backspace button"
    " in the keyboard.\n"
    "- To copy some text: first select the exact text you want to copy, which"
    " usually also brings up the text selection bar, then click the `copy`"
    " button in bar.\n"
    "- To paste text into a text box, first long press the"
    " text box, then usually the text selection bar will appear with a"
    " `paste` button in it.\n"
    "- When typing into a text field, sometimes an auto-complete dropdown"
    " list will appear. This usually indicating this is a enum field and you"
    " should try to select the best match by clicking the corresponding one"
    " in the list.\n"
)

ACTION_SELECTION_PROMPT_TEMPLATE = (
    PROMPT_PREFIX
    + "\nThe current user goal/request is: {goal}"
    + "\n\nHere is a history of what you have done so far:\n{history}"
    + "\n\nHere is a list of descriptions for some UI elements on the current"
    " screen:\n{ui_elements_description}\n"
    + GUIDANCE
    + "{additional_guidelines}"
    + "\n\nNow output an action from the above list in the correct JSON format,"
    " following the reason why you do that. Your answer should look like:\n"
    'Reason: ...\nAction: {{"action_type":...}}\n\n'
    "Your Answer:\n"
)

SUMMARIZATION_PROMPT_TEMPLATE = (
    PROMPT_PREFIX
    + "\nThe (overall) user goal/request is:{goal}\n"
    "Now I want you to summerize the latest step based on the action you"
    " pick with the reason and descriptions for the before and after (the"
    " action) screenshots.\n"
    "Here is the description for the before"
    " screenshot:\n{before_elements}\n"
    "Here is the description for the after screenshot:\n{after_elements}\n"
    "This is the action you picked: {action}\n"
    "Based on the reason: {reason}\n\n"
    "\nBy comparing the descriptions for the two screenshots and the action"
    " performed, give a brief summary of this step."
    " This summary will be added to action history and used in future action"
    " selection, so try to include essential information you think that will"
    " be most useful for future action selection like"
    " what you intended to do, why, if it worked as expected, if not"
    " what might be the reason (be critical, the action/reason might not be"
    " correct), what should/should not be done next and so on. Some more"
    " rules/tips you should follow:\n"
    "- Keep it short and in one line.\n"
    "- Some actions (like `answer`, `wait`) don't involve screen change,"
    " you can just assume they work as expected.\n"
    "- Given this summary will be added into action history, it can be used as"
    " memory to include information that needs to be remembered, or shared"
    " between different apps.\n\n"
    "Summary of this step: "
)

ACTION_TYPES = (
    "click",
    "double_tap",
    "scroll",
    "swipe",
    "input_text",
    "navigate_home",
    "navigate_back",
    "keyboard_enter",
    "open_app",
    "status",
    "wait",
    "long_press",
    "answer",
    "unknown",
)
SCROLL_DIRECTIONS = ("left", "right", "down", "up")


@dataclasses.dataclass
class BoundingBox:
    """Mirror of ``android_world.env.representation_utils.BoundingBox``."""

    x_min: float | int
    x_max: float | int
    y_min: float | int
    y_max: float | int

    @property
    def center(self) -> tuple[float, float]:
        return (self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0

    @property
    def width(self) -> float | int:
        return self.x_max - self.x_min

    @property
    def height(self) -> float | int:
        return self.y_max - self.y_min

    @property
    def area(self) -> float | int:
        return self.width * self.height


@dataclasses.dataclass
class UIElement:
    """Mirror of ``android_world.env.representation_utils.UIElement``."""

    text: Optional[str] = None
    content_description: Optional[str] = None
    class_name: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    bbox_pixels: Optional[BoundingBox] = None
    hint_text: Optional[str] = None
    is_checked: Optional[bool] = None
    is_checkable: Optional[bool] = None
    is_clickable: Optional[bool] = None
    is_editable: Optional[bool] = None
    is_enabled: Optional[bool] = None
    is_focused: Optional[bool] = None
    is_focusable: Optional[bool] = None
    is_long_clickable: Optional[bool] = None
    is_scrollable: Optional[bool] = None
    is_selected: Optional[bool] = None
    is_visible: Optional[bool] = None
    package_name: Optional[str] = None
    resource_name: Optional[str] = None
    tooltip: Optional[str] = None
    resource_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@dataclasses.dataclass()
class JSONAction:
    """Mirror of ``android_world.env.json_action.JSONAction``."""

    action_type: Optional[str] = None
    index: Optional[str | int] = None
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    direction: Optional[str] = None
    goal_status: Optional[str] = None
    app_name: Optional[str] = None
    keycode: Optional[str] = None
    clear_text: Optional[bool] = None

    def __post_init__(self) -> None:
        if self.action_type not in ACTION_TYPES:
            raise ValueError(f"Invalid action type: {self.action_type}")
        if self.index is not None:
            self.index = int(self.index)
            if self.x is not None or self.y is not None:
                raise ValueError("Either an index or a <x, y> should be provided.")
        if self.direction and self.direction not in SCROLL_DIRECTIONS:
            raise ValueError(f"Invalid scroll direction: {self.direction}")
        if self.text is not None and not isinstance(self.text, str):
            self.text = str(self.text)
        if self.keycode is not None and not self.keycode.startswith("KEYCODE_"):
            raise ValueError(f"Invalid keycode: {self.keycode}")

    def as_dict(self, skip_none: bool = True) -> dict[str, Any]:
        non_null = {}
        for key, value in self.__dict__.items():
            if skip_none and value is None:
                continue
            non_null[key] = value
        return non_null

    def json_str(self) -> str:
        return json.dumps(self.as_dict(skip_none=True), separators=(",", ":"))


def validate_ui_element(
    ui_element: Any,
    screen_width_height_px: tuple[int, int],
) -> bool:
    """Filter out invisible or off-screen UI elements (matches ``m3a_utils.validate_ui_element``)."""
    screen_width, screen_height = screen_width_height_px

    if not ui_element.is_visible:
        return False

    if ui_element.bbox_pixels:
        x_min = ui_element.bbox_pixels.x_min
        x_max = ui_element.bbox_pixels.x_max
        y_min = ui_element.bbox_pixels.y_min
        y_max = ui_element.bbox_pixels.y_max

        if (
            x_min >= x_max
            or x_min >= screen_width
            or x_max <= 0
            or y_min >= y_max
            or y_min >= screen_height
            or y_max <= 0
        ):
            return False

    return True


def generate_ui_elements_description_list_full(
    ui_elements: list[Any],
    screen_width_height_px: tuple[int, int],
) -> str:
    """Format UI elements list identically to ``t3a._generate_ui_elements_description_list_full``."""
    tree_info = ""
    for index, ui_element in enumerate(ui_elements):
        if validate_ui_element(ui_element, screen_width_height_px):
            tree_info += f"UI element {index}: {str(ui_element)}\n"
    return tree_info


def action_selection_prompt(
    goal: str,
    history: list[str],
    ui_elements_description: str,
    additional_guidelines: list[str] | None = None,
) -> str:
    """Build the T3A action selection prompt identically to ``t3a._action_selection_prompt``."""
    if history:
        history_text = "\n".join(history)
    else:
        history_text = "You just started, no action has been performed yet."

    extra_guidelines = ""
    if additional_guidelines:
        extra_guidelines = "For The Current Task:\n"
        for guideline in additional_guidelines:
            extra_guidelines += f"- {guideline}\n"

    return ACTION_SELECTION_PROMPT_TEMPLATE.format(
        history=history_text,
        goal=goal,
        ui_elements_description=(
            ui_elements_description if ui_elements_description else "Not available"
        ),
        additional_guidelines=extra_guidelines,
    )


def summarize_prompt(
    goal: str,
    action: str,
    reason: str,
    before_elements: str,
    after_elements: str,
) -> str:
    """Build the T3A summarization prompt identically to ``t3a._summarize_prompt``."""
    return SUMMARIZATION_PROMPT_TEMPLATE.format(
        goal=goal,
        action=action,
        reason=reason,
        before_elements=before_elements if before_elements else "Not available",
        after_elements=after_elements if after_elements else "Not available",
    )


def m3a_extract_json(s: str) -> Optional[dict[str, Any]]:
    """Mirror of ``m3a_utils.extract_json`` used inside ``parse_reason_action_output``."""
    match = re.search(r"\{.*?\}", s, re.DOTALL)
    if not match:
        return None
    try:
        parsed = ast.literal_eval(match.group())
        return parsed if isinstance(parsed, dict) else None
    except (SyntaxError, ValueError):
        return None


def extract_json(s: str) -> dict[str, Any] | None:
    """Mirror of ``agent_utils.extract_json`` used when building ``JSONAction``."""
    match = re.search(r"\{.*?\}", s)
    if not match:
        return None
    try:
        parsed = ast.literal_eval(match.group())
        return parsed if isinstance(parsed, dict) else None
    except (SyntaxError, ValueError):
        try:
            parsed = json.loads(match.group())
            return parsed if isinstance(parsed, dict) else None
        except (SyntaxError, ValueError):
            return None


def parse_reason_action_output(
    raw_reason_action_output: str,
) -> tuple[Optional[str], Optional[str]]:
    """Mirror of ``m3a_utils.parse_reason_action_output``."""
    reason_result = re.search(
        r"Reason:(.*)Action:", raw_reason_action_output, flags=re.DOTALL
    )
    reason = reason_result.group(1).strip() if reason_result else None
    action_result = re.search(
        r"Action:(.*)", raw_reason_action_output, flags=re.DOTALL
    )
    action = action_result.group(1).strip() if action_result else None
    if action:
        extracted = m3a_extract_json(action)
        if extracted is not None:
            action = json.dumps(extracted)
    return reason, action


def allocate_step_budget(task_complexity: float) -> int:
    """Mirror of upstream ``suite_utils._allocate_step_budget``."""
    return int(10 * float(task_complexity))
