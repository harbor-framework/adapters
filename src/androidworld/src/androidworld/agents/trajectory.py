"""ATIF-v1.7 trajectory and result sidecar recorder for T3AAgent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from androidworld.agents.t3a_core import ACTION_TYPES

T3A_RESULT_FILENAME = "t3a_result.json"


@dataclass(frozen=True)
class T3AActionObservation:
    """One T3A JSON action and its post-action observation."""

    action: dict[str, Any]
    image_path: str | None = None
    media_type: str = "image/png"
    info: dict[str, Any] | None = None


class T3ATrajectoryRecorder:
    """Records T3A episodes as Harbor ATIF-v1.7 trajectories + ``t3a_result.json``."""

    def __init__(
        self,
        *,
        logs_dir: Path,
        agent_name: str,
        agent_version: str,
        model_name: str | None,
        instruction: str,
        initial_image_path: str | None = None,
        extra: dict[str, Any] | None = None,
    ):
        self.logs_dir = Path(logs_dir)
        self.agent_name = agent_name
        self.agent_version = agent_version
        self.model_name = model_name
        self.session_id = str(uuid4())
        self.extra = extra or {}
        self.steps: list[dict[str, Any]] = [
            _strip_none(
                {
                    "step_id": 1,
                    "timestamp": _now_iso(),
                    "source": "user",
                    "message": _initial_message(instruction, initial_image_path),
                }
            )
        ]
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cached_tokens = 0
        self.total_cost_usd = 0.0
        self.action_count = 0
        self.last_action: dict[str, Any] | None = None
        self.terminal_status: str | None = None
        self.answer_text: str | None = None

    def record_turn(
        self,
        *,
        response: str,
        action_obs: T3AActionObservation | None,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float = 0.0,
        llm_call_count: int = 1,
        summary: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost_usd += cost_usd
        tool_calls, observation = self._action_payloads(action_obs)
        extra_meta: dict[str, Any] = {}
        if summary is not None:
            extra_meta["summary"] = summary

        self.steps.append(
            _strip_none(
                {
                    "step_id": len(self.steps) + 1,
                    "timestamp": _now_iso(),
                    "source": "agent",
                    "model_name": model_name or self.model_name,
                    "message": response,
                    "tool_calls": tool_calls,
                    "observation": observation,
                    "metrics": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "cached_tokens": 0,
                        "cost_usd": cost_usd,
                    },
                    "llm_call_count": llm_call_count,
                    "extra": extra_meta or None,
                }
            )
        )

    def write(self, context: Any | None = None) -> Path:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        trajectory_path = self.logs_dir / "trajectory.json"
        trajectory_path.write_text(
            json.dumps(self._build_trajectory(), indent=2) + "\n",
            encoding="utf-8",
        )
        self._write_result()
        if context is not None:
            self.populate_context(context)
        return trajectory_path

    def context_payload(self) -> dict[str, Any]:
        metadata = {
            "action_count": self.action_count,
            "agent": self.agent_name,
            "terminal_status": self.terminal_status,
            "answer_text": self.answer_text,
        }
        metadata.update(self.extra)
        return {
            "n_input_tokens": self.total_prompt_tokens,
            "n_output_tokens": self.total_completion_tokens,
            "cost_usd": self.total_cost_usd,
            "metadata": metadata,
        }

    def populate_context(self, context: Any) -> None:
        payload = self.context_payload()
        context.n_input_tokens = payload["n_input_tokens"]
        context.n_output_tokens = payload["n_output_tokens"]
        context.cost_usd = payload["cost_usd"]
        context.metadata = payload["metadata"]

    def _action_payloads(
        self, action_obs: T3AActionObservation | None
    ) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
        if action_obs is None:
            return None, None

        self.action_count += 1
        self.last_action = dict(action_obs.action)
        action_type = str(action_obs.action.get("action_type") or "unknown")
        if action_type == "status":
            self.terminal_status = str(
                action_obs.action.get("goal_status") or "complete"
            )
        elif action_type == "answer":
            self.answer_text = str(action_obs.action.get("text") or "")

        call_id = f"t3a_action_{self.action_count:03d}"
        tool_call = _strip_none(
            {
                "tool_call_id": call_id,
                "function_name": action_type,
                "arguments": dict(action_obs.action),
            }
        )
        obs_result = _strip_none(
            {
                "source_call_id": call_id,
                "content": _observation_content(action_obs),
                "extra": action_obs.info,
            }
        )
        return [tool_call], {"results": [obs_result]}

    def _build_trajectory(self) -> dict[str, Any]:
        return _strip_none(
            {
                "schema_version": "ATIF-v1.7",
                "session_id": self.session_id,
                "trajectory_id": f"androidworld-{self.session_id}",
                "agent": {
                    "name": self.agent_name,
                    "version": self.agent_version,
                    "model_name": self.model_name,
                    "tool_definitions": _tool_definitions(),
                    "extra": {"adapter": "androidworld"},
                },
                "steps": self.steps,
                "final_metrics": {
                    "total_prompt_tokens": self.total_prompt_tokens,
                    "total_completion_tokens": self.total_completion_tokens,
                    "total_cached_tokens": self.total_cached_tokens,
                    "total_cost_usd": self.total_cost_usd,
                    "total_steps": len(self.steps),
                    "extra": {
                        "action_count": self.action_count,
                        "terminal_status": self.terminal_status,
                    },
                },
                "extra": {
                    "adapter": "androidworld",
                    "action_count": self.action_count,
                    "terminal_status": self.terminal_status,
                    **self.extra,
                },
            }
        )

    def _write_result(self) -> None:
        result_path = self.logs_dir / T3A_RESULT_FILENAME
        result_path.write_text(
            json.dumps(
                {
                    "terminal_status": self.terminal_status,
                    "answer_text": self.answer_text,
                    "action_count": self.action_count,
                    "last_action": self.last_action,
                    "context": self.context_payload(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initial_message(
    instruction: str, initial_image_path: str | None
) -> str | list[dict[str, Any]]:
    if not initial_image_path:
        return instruction
    return [
        {"type": "text", "text": instruction},
        {
            "type": "image",
            "source": {"media_type": "image/png", "path": initial_image_path},
        },
    ]


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"Execute AndroidWorld T3A JSON action '{name}'.",
                "parameters": {
                    "type": "object",
                    "properties": {"action_type": {"type": "string"}},
                    "required": ["action_type"],
                },
            },
        }
        for name in ACTION_TYPES
    ]


def _observation_content(
    action_obs: T3AActionObservation,
) -> str | list[dict[str, Any]]:
    text = (
        json.dumps(action_obs.info, ensure_ascii=False)
        if action_obs.info
        else f"Executed T3A action: {action_obs.action.get('action_type')}"
    )
    if action_obs.image_path is None:
        return text
    return [
        {"type": "text", "text": text},
        {
            "type": "image",
            "source": {
                "media_type": action_obs.media_type,
                "path": action_obs.image_path,
            },
        },
    ]


def _strip_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_none(v) for v in value]
    return value
