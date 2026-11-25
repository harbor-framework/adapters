"""Unit tests for Harbor T3AAgent, LLM client, and symmetric parity runner."""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import hashlib
import importlib.abc
import importlib.util
import io
import json
import pickle
import shlex
import subprocess
import sys
import types
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TESTS_DIR.parent
ADAPTER_SRC = PROJECT_DIR / "src"
REPO_ROOT = PROJECT_DIR.parents[2]
UPSTREAM_T3A_PY = (
    REPO_ROOT / "ref" / "android_world" / "android_world" / "agents" / "t3a.py"
)
UPSTREAM_M3A_UTILS_PY = (
    REPO_ROOT / "ref" / "android_world" / "android_world" / "agents" / "m3a_utils.py"
)
TASKS_JSON = ADAPTER_SRC / "androidworld" / "tasks.json"

for p in (str(ADAPTER_SRC), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from harbor.agents.base import BaseAgent  # noqa: E402
from harbor.agents.factory import AgentFactory  # noqa: E402
from harbor.models.agent.context import AgentContext  # noqa: E402
from harbor.utils.trajectory_validator import TrajectoryValidator  # noqa: E402

from androidworld.adapter import AndroidWorldAdapter, parity_subset  # noqa: E402
from androidworld.agents import (  # noqa: E402
    ACTION_SELECTION_PROMPT_TEMPLATE,
    GUIDANCE,
    PROMPT_PREFIX,
    SUMMARIZATION_PROMPT_TEMPLATE,
    T3AAgent,
    T3ALlmClient,
    action_selection_prompt,
    allocate_step_budget,
    extract_json,
    generate_ui_elements_description_list_full,
    parse_reason_action_output,
    summarize_prompt,
)
from androidworld.agents import env_bridge  # noqa: E402
from androidworld.agents.t3a_core import BoundingBox, JSONAction, UIElement  # noqa: E402
from original_parity_runner import run_parity  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers to load upstream t3a.py in-process without needing full android_env
# ---------------------------------------------------------------------------


def _load_upstream_t3a_module(monkeypatch: pytest.MonkeyPatch):
    """Import upstream ref/android_world t3a.py with lightweight stubs for android_env."""

    class _DummyEnv:
        pass

    class _DummyLlmWrapper:
        def predict(self, text_prompt: str):
            raise NotImplementedError

    class _DummyBaseAgent:
        def __init__(self, env: Any, name: str = "", transition_pause: float | None = 1.0):
            self._env = env
            self._name = name
            self._transition_pause = transition_pause
            self._max_steps = None

        @property
        def env(self):
            return self._env

        def reset(self, go_home: bool = False):
            self._env.reset(go_home=go_home)

        def get_post_transition_state(self):
            return self._env.get_state(wait_to_stabilize=self._transition_pause is None)

    @dataclasses.dataclass()
    class _DummyAgentInteractionResult:
        done: bool
        data: dict[str, Any]

    # Build minimal stub packages in sys.modules
    stubs: dict[str, types.ModuleType] = {}

    def _pkg(name: str) -> types.ModuleType:
        mod = types.ModuleType(name)
        mod.__path__ = []  # type: ignore[attr-defined]
        stubs[name] = mod
        return mod

    _pkg("android_world")
    _pkg("android_world.agents")
    _pkg("android_world.env")
    _pkg("android_env")
    _pkg("android_env.proto")
    _pkg("android_env.proto.a11y")

    a11y_pb2 = types.ModuleType("android_env.proto.a11y.android_accessibility_forest_pb2")
    a11y_pb2.AndroidAccessibilityForest = Any  # type: ignore[attr-defined]
    stubs["android_env.proto.a11y.android_accessibility_forest_pb2"] = a11y_pb2

    # Stub cv2 / numpy / google.generativeai / PIL only if missing
    cv2_stub = types.ModuleType("cv2")
    stubs["cv2"] = cv2_stub
    if "numpy" not in sys.modules:
        np_stub = types.ModuleType("numpy")
        np_stub.ndarray = Any  # type: ignore[attr-defined]
        np_stub.isnan = lambda x: False  # type: ignore[attr-defined]
        stubs["numpy"] = np_stub

    # Load real upstream json_action, representation_utils, agent_utils, m3a_utils, t3a
    env_dir = REPO_ROOT / "ref" / "android_world" / "android_world" / "env"
    agents_dir = REPO_ROOT / "ref" / "android_world" / "android_world" / "agents"

    base_mod = types.ModuleType("android_world.agents.base_agent")
    base_mod.EnvironmentInteractingAgent = _DummyBaseAgent  # type: ignore[attr-defined]
    base_mod.AgentInteractionResult = _DummyAgentInteractionResult  # type: ignore[attr-defined]
    stubs["android_world.agents.base_agent"] = base_mod

    infer_mod = types.ModuleType("android_world.agents.infer")
    infer_mod.LlmWrapper = _DummyLlmWrapper  # type: ignore[attr-defined]
    stubs["android_world.agents.infer"] = infer_mod

    iface_mod = types.ModuleType("android_world.env.interface")
    iface_mod.AsyncEnv = _DummyEnv  # type: ignore[attr-defined]
    stubs["android_world.env.interface"] = iface_mod

    adb_mod = types.ModuleType("android_world.env.adb_utils")
    adb_mod.get_physical_frame_boundary = lambda _ctrl: (0, 0, 1080, 2400)  # type: ignore[attr-defined]
    adb_mod.get_orientation = lambda _ctrl: 0  # type: ignore[attr-defined]
    stubs["android_world.env.adb_utils"] = adb_mod

    for k, v in stubs.items():
        monkeypatch.setitem(sys.modules, k, v)

    def _load_file(mod_name: str, file_path: Path):
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, mod_name, mod)
        spec.loader.exec_module(mod)
        return mod

    rep_mod = _load_file("android_world.env.representation_utils", env_dir / "representation_utils.py")
    _load_file("android_world.env.json_action", env_dir / "json_action.py")
    _load_file("android_world.agents.agent_utils", agents_dir / "agent_utils.py")
    m3a_mod = _load_file("android_world.agents.m3a_utils", agents_dir / "m3a_utils.py")
    # Avoid cv2 rectangle calls during mark visualization in unit tests
    monkeypatch.setattr(m3a_mod, "add_ui_element_mark", lambda *a, **k: None)
    t3a_mod = _load_file("android_world.agents.t3a", agents_dir / "t3a.py")
    return t3a_mod, rep_mod, m3a_mod


class _FakePixels:
    def copy(self) -> "_FakePixels":
        return self


class _FakeUpstreamEnv:
    def __init__(self, states: list[tuple[tuple[int, int], list[Any]]]):
        self._states = list(states)
        self._idx = 0
        self.controller = SimpleNamespace()
        self.executed_actions: list[Any] = []
        self.hide_ui_called = False
        self.reset_calls: list[bool] = []
        self.interaction_cache = ""

    def reset(self, go_home: bool = False):
        self.reset_calls.append(go_home)
        self.interaction_cache = ""

    def hide_automation_ui(self):
        self.hide_ui_called = True

    @property
    def logical_screen_size(self) -> tuple[int, int]:
        return self._states[min(self._idx, len(self._states) - 1)][0]

    def get_state(self, wait_to_stabilize: bool = False):
        size, elems = self._states[min(self._idx, len(self._states) - 1)]
        _ = size, wait_to_stabilize
        return SimpleNamespace(pixels=_FakePixels(), ui_elements=elems)

    def execute_action(self, action: Any):
        self.executed_actions.append(action)
        if action.action_type == "answer":
            self.interaction_cache = action.text or ""
        if self._idx + 1 < len(self._states):
            self._idx += 1


# ---------------------------------------------------------------------------
# 1. Upstream T3A prompt & observation parity tests
# ---------------------------------------------------------------------------


def test_t3a_prompts_and_ui_description_match_upstream_byte_for_byte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_t3a, upstream_rep, _ = _load_upstream_t3a_module(monkeypatch)

    assert PROMPT_PREFIX == upstream_t3a.PROMPT_PREFIX
    assert GUIDANCE == upstream_t3a.GUIDANCE
    assert ACTION_SELECTION_PROMPT_TEMPLATE == upstream_t3a.ACTION_SELECTION_PROMPT_TEMPLATE
    assert SUMMARIZATION_PROMPT_TEMPLATE == upstream_t3a.SUMMARIZATION_PROMPT_TEMPLATE

    local_elems = [
        UIElement(
            text="Wi-Fi",
            class_name="android.widget.TextView",
            bbox_pixels=BoundingBox(10, 200, 100, 180),
            is_clickable=True,
            is_visible=True,
        ),
        UIElement(
            text="Hidden",
            bbox_pixels=BoundingBox(10, 200, 100, 180),
            is_visible=False,
        ),
        UIElement(
            text="Offscreen",
            bbox_pixels=BoundingBox(1200, 1400, 100, 180),
            is_visible=True,
        ),
        UIElement(
            text="Connect",
            content_description="Connect button",
            bbox_pixels=BoundingBox(300, 500, 400, 480),
            is_clickable=True,
            is_enabled=True,
            is_visible=True,
        ),
    ]
    upstream_elems = [
        upstream_rep.UIElement(
            text=e.text,
            content_description=e.content_description,
            class_name=e.class_name,
            bbox_pixels=(
                upstream_rep.BoundingBox(
                    e.bbox_pixels.x_min,
                    e.bbox_pixels.x_max,
                    e.bbox_pixels.y_min,
                    e.bbox_pixels.y_max,
                )
                if e.bbox_pixels
                else None
            ),
            is_clickable=e.is_clickable,
            is_enabled=e.is_enabled,
            is_visible=e.is_visible,
        )
        for e in local_elems
    ]

    screen = (1080, 2400)
    local_desc = generate_ui_elements_description_list_full(local_elems, screen)
    upstream_desc = upstream_t3a._generate_ui_elements_description_list_full(
        upstream_elems, screen
    )
    assert local_desc == upstream_desc
    assert "UI element 0:" in local_desc
    assert "UI element 1:" not in local_desc
    assert "UI element 2:" not in local_desc
    assert "UI element 3:" in local_desc

    assert action_selection_prompt(
        "Turn on Wi-Fi.", [], ""
    ) == upstream_t3a._action_selection_prompt("Turn on Wi-Fi.", [], "")
    assert action_selection_prompt(
        "Turn on Wi-Fi.",
        ["Step 1: Action selected: {\"action_type\": \"open_app\", \"app_name\": \"settings\"}. Opened settings."],
        local_desc,
        ["Stay in Settings."],
    ) == upstream_t3a._action_selection_prompt(
        "Turn on Wi-Fi.",
        ["Step 1: Action selected: {\"action_type\": \"open_app\", \"app_name\": \"settings\"}. Opened settings."],
        upstream_desc,
        ["Stay in Settings."],
    )
    assert summarize_prompt(
        "Turn on Wi-Fi.",
        '{"action_type": "click", "index": 0}',
        "Tap Wi-Fi",
        local_desc,
        "",
    ) == upstream_t3a._summarize_prompt(
        "Turn on Wi-Fi.",
        '{"action_type": "click", "index": 0}',
        "Tap Wi-Fi",
        upstream_desc,
        "",
    )


def test_parse_reason_action_and_json_action_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, upstream_m3a = _load_upstream_t3a_module(monkeypatch)

    outputs = [
        "Reason: Need to tap Wi-Fi.\nAction: {'action_type': 'click', 'index': 0}",
        'Reason: Done now.\nAction: {"action_type": "status", "goal_status": "complete"}',
        "Reason: Missing action braces\nAction: click element 0",
        "Totally malformed response",
    ]
    for raw in outputs:
        assert parse_reason_action_output(raw) == upstream_m3a.parse_reason_action_output(raw)

    parsed = extract_json('{"action_type": "input_text", "text": "hello", "index": "3"}')
    assert parsed is not None
    action = JSONAction(**parsed)
    assert action.index == 3
    assert action.as_dict() == {"action_type": "input_text", "index": 3, "text": "hello"}

    with pytest.raises(ValueError, match="Invalid action type"):
        JSONAction(action_type="fly_away")
    with pytest.raises(ValueError, match="Invalid scroll direction"):
        JSONAction(action_type="scroll", direction="diagonal")
    with pytest.raises(ValueError, match="Either an index or a <x, y>"):
        JSONAction(action_type="click", index=1, x=10, y=20)


# ---------------------------------------------------------------------------
# 2. Custom Gateway OpenAI / Anthropic LLM Client Tests
# ---------------------------------------------------------------------------


def test_llm_client_openai_gateway_endpoint_and_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def fake_post(self, url, headers, payload):
        captured.append((url, headers, payload))
        return {
            "choices": [
                {
                    "message": {
                        "content": 'Reason: Tap OK.\nAction: {"action_type": "click", "index": 0}'
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 18},
        }

    monkeypatch.setattr(T3ALlmClient, "_post_json", fake_post)
    client = T3ALlmClient(
        model_name="openai/gpt-4o-2024-11-20",
        env={
            "OPENAI_BASE_URL": "https://api.gateway.example/v1/",
            "OPENAI_API_KEY": "sk-test-openai",
        },
    )
    pred = client.predict_with_usage("test prompt")

    assert client.protocol == "openai"
    assert captured[0][0] == "https://api.gateway.example/v1/chat/completions"
    assert captured[0][1]["Authorization"] == "Bearer sk-test-openai"
    assert captured[0][2] == {
        "model": "gpt-4o-2024-11-20",
        "temperature": 0.0,
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": "test prompt"}],
    }
    assert pred.prompt_tokens == 120
    assert pred.completion_tokens == 18
    assert pred.is_safe is None


def test_llm_client_anthropic_gateway_endpoint_and_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def fake_post(self, url, headers, payload):
        captured.append((url, headers, payload))
        return {
            "content": [{"type": "text", "text": "Reason: Done.\nAction: {\"action_type\": \"status\", \"goal_status\": \"complete\"}"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 200, "output_tokens": 25},
        }

    monkeypatch.setattr(T3ALlmClient, "_post_json", fake_post)
    client = T3ALlmClient(
        model_name="anthropic/claude-sonnet-4-5-20250929",
        env={
            "ANTHROPIC_BASE_URL": "https://api.gateway.example/anthropic",
            "ANTHROPIC_API_KEY": "sk-test-ant",
        },
    )
    pred = client.predict_with_usage("anthropic prompt")

    assert client.protocol == "anthropic"
    assert captured[0][0] == "https://api.gateway.example/anthropic/v1/messages"
    assert captured[0][1]["x-api-key"] == "sk-test-ant"
    assert captured[0][1]["anthropic-version"] == "2023-06-01"
    assert captured[0][2] == {
        "model": "claude-sonnet-4-5-20250929",
        "max_tokens": 1000,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": "anthropic prompt"}],
    }
    assert pred.prompt_tokens == 200
    assert pred.completion_tokens == 25

    # If ANTHROPIC_BASE_URL already ends with /v1, avoid /v1/v1/messages
    client_v1 = T3ALlmClient(
        model_name="claude-3-5-sonnet-20241022",
        env={
            "ANTHROPIC_BASE_URL": "https://api.gateway.example/v1",
            "ANTHROPIC_API_KEY": "sk-test-ant",
        },
    )
    assert client_v1.endpoint_url == "https://api.gateway.example/v1/messages"


def test_llm_client_retries_and_safety_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def flaky_post(self, url, headers, payload):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise urllib.error.HTTPError(
                url, 429, "Too Many Requests", {}, io.BytesIO(b"rate limit")
            )
        return {
            "choices": [{"message": {"content": "blocked"}, "finish_reason": "content_filter"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1},
        }

    monkeypatch.setattr(T3ALlmClient, "_post_json", flaky_post)
    monkeypatch.setattr("androidworld.agents.llm.time.sleep", lambda _s: None)
    client = T3ALlmClient(
        model_name="gpt-4-turbo-2024-04-09",
        env={"OPENAI_API_KEY": "k"},
        max_retry=3,
    )
    pred = client.predict_with_usage("p")
    assert attempts == 2
    assert pred.is_safe is False


def test_llm_client_gateway_gpt5_and_verified_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def fake_post(self, url, headers, payload):
        captured.append((url, headers, payload))
        if self.protocol == "anthropic":
            return {
                "content": [{"type": "text", "text": "Reason: OK.\nAction: {\"action_type\": \"wait\"}"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        return {
            "choices": [{"message": {"content": "Reason: OK.\nAction: {\"action_type\": \"wait\"}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    monkeypatch.setattr(T3ALlmClient, "_post_json", fake_post)

    # 1. gpt-5-mini and gpt-5.4 at https://gateway.example/v1 and https://gateway.example
    for model_id in ("openai/gpt-5-mini", "gpt-5-mini", "openai/gpt-5.4", "gpt-5.4"):
        for base in ("https://gateway.example/v1", "https://gateway.example"):
            captured.clear()
            client = T3ALlmClient(
                model_name=model_id,
                env={"OPENAI_BASE_URL": base, "OPENAI_API_KEY": "sk-test"},
            )
            client.predict_with_usage("hi")
            url, headers, payload = captured[0]
            assert url == "https://gateway.example/v1/chat/completions"
            assert headers["Authorization"] == "Bearer sk-test"
            assert payload["model"] == model_id.removeprefix("openai/")
            assert payload["max_completion_tokens"] == 1000
            assert "max_tokens" not in payload
            assert "temperature" not in payload

    # 2. gpt-4o preserves temperature & max_tokens and normalizes root base_url
    captured.clear()
    client_4o = T3ALlmClient(
        model_name="gpt-4o",
        env={"OPENAI_BASE_URL": "https://gateway.example", "OPENAI_API_KEY": "sk-test"},
    )
    client_4o.predict_with_usage("hi")
    assert captured[0][0] == "https://gateway.example/v1/chat/completions"
    assert captured[0][2]["max_tokens"] == 1000
    assert captured[0][2]["temperature"] == 0.0
    assert "max_completion_tokens" not in captured[0][2]

    # 3. claude-sonnet-4-6 and claude-haiku-4-5 at https://gateway.example and https://gateway.example/v1
    for model_id in ("claude-sonnet-4-6", "anthropic/claude-sonnet-4-6", "claude-haiku-4-5"):
        for base in ("https://gateway.example", "https://gateway.example/v1"):
            captured.clear()
            client_c = T3ALlmClient(
                model_name=model_id,
                env={"ANTHROPIC_BASE_URL": base, "ANTHROPIC_API_KEY": "sk-ant"},
            )
            client_c.predict_with_usage("hi")
            assert client_c.protocol == "anthropic"
            assert captured[0][0] == "https://gateway.example/v1/messages"
            assert captured[0][2]["model"] == model_id.removeprefix("anthropic/")
            assert captured[0][2]["max_tokens"] == 1000
            assert captured[0][2]["temperature"] == 0.0


# ---------------------------------------------------------------------------
# 3. Harbor BaseAgent Contract + Full Mocked Episode Parity vs Upstream T3A
# ---------------------------------------------------------------------------


class _FakeDockerEnvironment:
    """Mock Harbor BaseEnvironment routing bridge HTTP calls to in-process env_bridge."""

    def __init__(self, task_spec: dict[str, Any], fake_env: _FakeUpstreamEnv):
        self.task_spec = task_spec
        self.fake_env = fake_env
        self.uploaded_files: list[tuple[Path, str]] = []
        self.exec_commands: list[str] = []
        self.answer_written: str | None = None

    @staticmethod
    def type() -> str:
        return "docker"

    async def upload_file(self, source_path: Path | str, target_path: str) -> None:
        self.uploaded_files.append((Path(source_path), target_path))

    async def exec(
        self,
        *,
        command: str,
        user: str | int | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> SimpleNamespace:
        _ = user, env, cwd, timeout_sec
        self.exec_commands.append(command)
        if "env_bridge.py call" not in command:
            return SimpleNamespace(return_code=0, stdout="", stderr="")

        tokens = shlex.split(command)
        endpoint = tokens[tokens.index("--endpoint") + 1]
        payload_str = (
            tokens[tokens.index("--payload") + 1] if "--payload" in tokens else "{}"
        )
        payload = json.loads(payload_str)

        if endpoint == "/health":
            return SimpleNamespace(
                return_code=0,
                stdout=json.dumps({"ok": True, "task_spec": self.task_spec}),
                stderr="",
            )
        if endpoint == "/reset":
            self.fake_env.reset(go_home=bool(payload.get("go_home", True)))
            self.fake_env.hide_automation_ui()
            return SimpleNamespace(
                return_code=0,
                stdout=json.dumps({"ok": True, "task_spec": self.task_spec}),
                stderr="",
            )
        if endpoint == "/state":
            state = self.fake_env.get_state(
                wait_to_stabilize=payload.get("transition_pause") is None
            )
            desc = generate_ui_elements_description_list_full(
                state.ui_elements, self.fake_env.logical_screen_size
            )
            return SimpleNamespace(
                return_code=0,
                stdout=json.dumps(
                    {
                        "ui_elements_description": desc,
                        "num_ui_elements": len(state.ui_elements),
                        "logical_screen_size": list(self.fake_env.logical_screen_size),
                        "screenshot_path": None,
                    }
                ),
                stderr="",
            )
        if endpoint == "/execute":
            action = JSONAction(**payload["action"])
            if action.action_type == "answer":
                self.answer_written = action.text or ""
            self.fake_env.execute_action(action)
            state = self.fake_env.get_state(
                wait_to_stabilize=payload.get("transition_pause") is None
            )
            desc = generate_ui_elements_description_list_full(
                state.ui_elements, self.fake_env.logical_screen_size
            )
            return SimpleNamespace(
                return_code=0,
                stdout=json.dumps(
                    {
                        "ok": True,
                        "after_element_list": desc,
                        "num_ui_elements": len(state.ui_elements),
                        "logical_screen_size": list(self.fake_env.logical_screen_size),
                        "screenshot_path": None,
                    }
                ),
                stderr="",
            )
        raise AssertionError(f"Unexpected endpoint: {endpoint}")


def test_harbor_agent_factory_instantiation_and_capabilities(tmp_path: Path) -> None:
    assert issubclass(T3AAgent, BaseAgent)
    assert T3AAgent.capabilities.atif is True
    assert T3AAgent.capabilities.base_url is True
    assert T3AAgent.name() == "t3a-agent"

    agent = AgentFactory.create_agent_from_import_path(
        "androidworld.agents:T3AAgent",
        logs_dir=tmp_path,
        model_name="openai/gpt-4o-2024-11-20",
        base_url="https://api.gateway.example/v1",
        extra_env={"OPENAI_API_KEY": "sk-test"},
        temperature=0.0,
        max_tokens=1000,
    )
    assert isinstance(agent, T3AAgent)
    assert agent.options.temperature == 0.0
    assert agent.options.max_tokens == 1000
    assert agent.options.base_url == "https://api.gateway.example/v1"


def test_t3a_agent_and_upstream_t3a_produce_identical_prompts_and_actions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _run() -> None:
        upstream_t3a, upstream_rep, _ = _load_upstream_t3a_module(monkeypatch)

        goal = "What is the Wi-Fi status?"
        local_states = [
            (
                (1080, 2400),
                [
                    UIElement(
                        text="Settings",
                        bbox_pixels=BoundingBox(10, 200, 100, 200),
                        is_clickable=True,
                        is_visible=True,
                    )
                ],
            ),
            (
                (1080, 2400),
                [
                    UIElement(
                        text="Wi-Fi On",
                        bbox_pixels=BoundingBox(10, 200, 300, 400),
                        is_clickable=True,
                        is_visible=True,
                    )
                ],
            ),
        ]
        upstream_states = [
            (
                size,
                [
                    upstream_rep.UIElement(
                        text=e.text,
                        bbox_pixels=upstream_rep.BoundingBox(
                            e.bbox_pixels.x_min,
                            e.bbox_pixels.x_max,
                            e.bbox_pixels.y_min,
                            e.bbox_pixels.y_max,
                        ),
                        is_clickable=e.is_clickable,
                        is_visible=e.is_visible,
                    )
                    for e in elems
                ],
            )
            for size, elems in local_states
        ]

        scripted_responses = [
            # Step 1: click Settings + summary
            'Reason: Open settings.\nAction: {"action_type": "click", "index": 0}',
            "Clicked Settings and now Wi-Fi On is visible.",
            # Step 2: answer + summary
            'Reason: Report Wi-Fi status.\nAction: {"action_type": "answer", "text": "Wi-Fi is on"}',
            "Answered user with Wi-Fi status.",
            # Step 3: status complete
            'Reason: Task finished.\nAction: {"action_type": "status", "goal_status": "complete"}',
        ]

        # Run upstream T3A
        up_prompts: list[str] = []

        class _UpstreamMockLlm:
            def __init__(self):
                self.idx = 0

            def predict(self, prompt: str):
                up_prompts.append(prompt)
                text = scripted_responses[self.idx]
                self.idx += 1
                return text, None, {"id": self.idx}

        up_env = _FakeUpstreamEnv(upstream_states)
        up_agent = upstream_t3a.T3A(up_env, _UpstreamMockLlm())
        up_agent.transition_pause = None
        up_agent.reset(go_home_on_reset=True)
        for _ in range(allocate_step_budget(1.2)):
            res = up_agent.step(goal)
            if res.done:
                break

        # Run Harbor T3AAgent
        harbor_prompts: list[str] = []
        idx_box = {"i": 0}

        def fake_post(self, url, headers, payload):
            _ = url, headers
            harbor_prompts.append(payload["messages"][0]["content"])
            text = scripted_responses[idx_box["i"]]
            idx_box["i"] += 1
            return {
                "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10},
            }

        monkeypatch.setattr(T3ALlmClient, "_post_json", fake_post)

        task_spec = {
            "name": "SystemWifiCheck",
            "family": "abc",
            "seed": 12345,
            "goal": goal,
            "complexity": 1.2,
            "answer_task": True,
        }
        hb_env = _FakeDockerEnvironment(task_spec, _FakeUpstreamEnv(local_states))
        logs_dir = tmp_path / "agent_logs"
        hb_agent = T3AAgent(
            logs_dir=logs_dir,
            model_name="openai/gpt-4o-2024-11-20",
            extra_env={
                "OPENAI_BASE_URL": "https://api.gateway.example/v1",
                "OPENAI_API_KEY": "sk-test",
            },
        )
        ctx = AgentContext()
        await hb_agent.setup(hb_env)  # type: ignore[arg-type]
        await hb_agent.run("Wrapper instruction ignored in favor of task_spec goal", hb_env, ctx)  # type: ignore[arg-type]

        # Exact prompt parity at every action selection and summarization call!
        assert harbor_prompts == up_prompts
        assert len(harbor_prompts) == 5

        # Exact action sequence parity
        assert [a.action_type for a in hb_env.fake_env.executed_actions] == [
            a.action_type for a in up_env.executed_actions
        ]
        assert hb_env.answer_written == "Wi-Fi is on"
        assert hb_env.fake_env.interaction_cache == "Wi-Fi is on"

        # Harbor context + ATIF trajectory validation
        assert ctx.n_input_tokens == 500
        assert ctx.n_output_tokens == 50
        assert ctx.metadata is not None
        assert ctx.metadata["terminal_status"] == "complete"
        assert ctx.metadata["answer_text"] == "Wi-Fi is on"
        assert ctx.metadata["max_steps"] == 12  # int(10 * 1.2)

        traj_path = logs_dir / "trajectory.json"
        validator = TrajectoryValidator()
        assert validator.validate(traj_path), validator.errors

        # Post-run backfill works from t3a_result.json
        post_ctx = AgentContext()
        hb_agent.populate_context_post_run(post_ctx)
        assert post_ctx.n_input_tokens == 500
        assert post_ctx.metadata["terminal_status"] == "complete"

    asyncio.run(_run())


def test_t3a_agent_handles_edge_cases_and_turn_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _run() -> None:
        states = [
            (
                (1080, 2400),
                [
                    UIElement(
                        text="OnlyOne",
                        bbox_pixels=BoundingBox(10, 200, 100, 200),
                        is_visible=True,
                    )
                ],
            )
        ]
        responses = [
            # 1. Malformed output
            "No reason or action here",
            # 2. Out of range click index
            'Reason: Click missing.\nAction: {"action_type": "click", "index": 99}',
            # 3. Invalid JSONAction field
            'Reason: Bad action.\nAction: {"action_type": "nonexistent"}',
        ]
        idx_box = {"i": 0}

        def fake_post(self, url, headers, payload):
            _ = url, headers, payload
            text = responses[idx_box["i"]]
            idx_box["i"] += 1
            return {
                "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

        monkeypatch.setattr(T3ALlmClient, "_post_json", fake_post)

        hb_env = _FakeDockerEnvironment(
            {"name": "TestTask", "goal": "Do X", "complexity": 0.3},
            _FakeUpstreamEnv(states),
        )
        agent = T3AAgent(
            logs_dir=tmp_path,
            model_name="gpt-4o-2024-11-20",
            extra_env={"OPENAI_API_KEY": "sk-test"},
        )
        ctx = AgentContext()
        await agent.setup(hb_env)  # type: ignore[arg-type]
        await agent.run("Do X", hb_env, ctx)  # type: ignore[arg-type]

        assert len(agent.history) == 3
        assert "not in the correct format" in agent.history[0]["summary"]
        assert "index is out of range" in agent.history[1]["summary"]
        assert "Can not parse the output to a valid action" in agent.history[2]["summary"]
        assert ctx.metadata["terminal_status"] is None

    asyncio.run(_run())


def test_t3a_agent_safety_classifier_triggers_infeasible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _run() -> None:
        states = [((1080, 2400), [])]

        def fake_post(self, url, headers, payload):
            _ = url, headers, payload
            return {
                "choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}],
                "usage": {"prompt_tokens": 15, "completion_tokens": 0},
            }

        monkeypatch.setattr(T3ALlmClient, "_post_json", fake_post)
        hb_env = _FakeDockerEnvironment(
            {"name": "SafetyTest", "goal": "Do Y", "complexity": 1.0},
            _FakeUpstreamEnv(states),
        )
        agent = T3AAgent(
            logs_dir=tmp_path,
            model_name="gpt-4o-2024-11-20",
            extra_env={"OPENAI_API_KEY": "sk-test"},
        )
        ctx = AgentContext()
        await agent.setup(hb_env)  # type: ignore[arg-type]
        await agent.run("Do Y", hb_env, ctx)  # type: ignore[arg-type]

        assert len(agent.history) == 1
        assert ctx.metadata["terminal_status"] == "infeasible"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 4. Container env_bridge isolation & answer-file tests
# ---------------------------------------------------------------------------


def test_env_bridge_imports_without_harbor() -> None:
    script = """
import importlib.abc
import sys

class BlockHarbor(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "harbor" or fullname.startswith("harbor."):
            raise ImportError(f"blocked harbor import: {fullname}")
        return None

sys.meta_path.insert(0, BlockHarbor())
import androidworld.agents.env_bridge
import androidworld.agents.t3a_core
import androidworld.agents.llm
assert "harbor" not in sys.modules
"""
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ADAPTER_SRC)
    res = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr


def test_env_bridge_answer_action_writes_workspace_answer_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_t3a, upstream_rep, _ = _load_upstream_t3a_module(monkeypatch)
    _ = upstream_t3a

    fake_env = _FakeUpstreamEnv(
        [
            (
                (1080, 2400),
                [
                    upstream_rep.UIElement(
                        text="42",
                        bbox_pixels=upstream_rep.BoundingBox(0, 100, 0, 100),
                        is_visible=True,
                    )
                ],
            )
        ]
    )
    answer_file = tmp_path / "answer.txt"
    spec_file = tmp_path / "task_spec.json"
    spec_file.write_text(json.dumps({"goal": "Q?", "complexity": 1.0}), encoding="utf-8")

    monkeypatch.setattr(env_bridge, "ANSWER_FILE", answer_file)
    monkeypatch.setattr(env_bridge, "TASK_SPEC_PATH", spec_file)
    monkeypatch.setattr(env_bridge, "_ENV", fake_env)

    reset_res = env_bridge._handle_reset({"go_home": True})
    assert reset_res["ok"] is True
    assert fake_env.reset_calls == [True]
    assert fake_env.hide_ui_called is True

    exec_res = env_bridge._handle_execute(
        {"action": {"action_type": "answer", "text": "42"}}
    )
    assert exec_res["ok"] is True
    assert answer_file.read_text(encoding="utf-8") == "42"
    assert fake_env.interaction_cache == "42"


# ---------------------------------------------------------------------------
# 5. Symmetric Upstream Parity Runner Tests
# ---------------------------------------------------------------------------


def test_parity_runner_loads_exact_35_tasks_and_recipe_seed_index_1() -> None:
    adapter_tasks = AndroidWorldAdapter(Path("/tmp/unused"), split="parity")._select()
    runner_tasks = run_parity.load_task_entries(TASKS_JSON, split="parity")

    assert len(runner_tasks) == 35
    assert [t["name"] for t in runner_tasks] == [t["name"] for t in adapter_tasks]
    assert [t["seed"] for t in runner_tasks] == [t["seed"] for t in adapter_tasks]

    # Verify every task's seed matches sha256(f"30_{name}_{seed_index}") % 2**32
    full_tasks = run_parity.load_task_entries(TASKS_JSON, split="full")
    assert len(full_tasks) == 116
    for entry in full_tasks:
        expected = (
            int(
                hashlib.sha256(
                    f"30_{entry['name']}_{entry['seed_index']}".encode()
                ).hexdigest(),
                16,
            )
            % 2**32
        )
        assert entry["seed"] == expected

    # Specifically verify RecipeDeleteMultipleRecipesWithConstraint uses seed_index == 1
    recipe_entry = next(
        e for e in full_tasks if e["name"] == "RecipeDeleteMultipleRecipesWithConstraint"
    )
    assert recipe_entry["seed_index"] == 1
    assert recipe_entry["seed"] == run_parity.compute_task_seed(
        "RecipeDeleteMultipleRecipesWithConstraint", 1
    )
    assert recipe_entry["seed"] != run_parity.compute_task_seed(
        "RecipeDeleteMultipleRecipesWithConstraint", 0
    )

    # Verify mock upstream suite instantiation preserves unpickled params & goal
    class _FakeTaskEval:
        def __init__(self, params: dict[str, Any]):
            self.params = params
            self.goal = recipe_entry["goal"]

    class _FakeSuite(dict):
        suite_family = None

    # Test with pickle-safe params
    fake_entry = dict(recipe_entry)
    fake_params = {"seed": recipe_entry["seed"], "foo": "bar"}
    fake_entry["params_pickle_b64"] = base64.b64encode(
        pickle.dumps(fake_params, protocol=4)
    ).decode()

    suite = run_parity.build_suite_from_entries(
        [fake_entry],
        {"RecipeDeleteMultipleRecipesWithConstraint": _FakeTaskEval},
        suite_cls=_FakeSuite,
    )
    assert suite.suite_family == "android_world"
    inst = suite["RecipeDeleteMultipleRecipesWithConstraint"][0]
    assert inst.params["seed"] == recipe_entry["seed"]
    assert inst.goal == recipe_entry["goal"]


def test_parity_runner_dry_run_cli(capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_parity.main(
        [
            "--model",
            "gpt-4-turbo-2024-04-09",
            "--split",
            "parity",
            "--dry-run",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["split"] == "parity"
    assert out["task_count"] == 35
    assert out["temperature"] == 0.0
    assert out["max_tokens"] == 1000
    assert len(out["tasks"]) == 35
    assert all(
        t["step_budget"] == allocate_step_budget(t["complexity"]) for t in out["tasks"]
    )
