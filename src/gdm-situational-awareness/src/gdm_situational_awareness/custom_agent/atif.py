"""Live ATIF trajectory for the parity agent (`harbor view` support).

The agent rewrites `<logs_dir>/trajectory.json` after every model turn
(atomically: write to a temp file, then rename), so `harbor view jobs`
shows the episode step by step while it is still running, and Harbor
reads token usage from `final_metrics` when the trial ends. Shared with
the gdm-stealth adapter; the situational-awareness tasks have no grader
models, so the grader-call helpers are unused here.

Recording is observational only: it never changes what the model sees,
and any failure to record is logged and swallowed so it cannot affect
an episode.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harbor.models.trajectories import (
    Agent,
    FinalMetrics,
    Metrics,
    Observation,
    ObservationResult,
    Step,
    ToolCall,
    Trajectory,
)

logger = logging.getLogger(__name__)
FILENAME = "trajectory.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TrajectoryRecorder:
    def __init__(
        self,
        logs_dir: Path,
        *,
        session_id: str,
        agent_name: str,
        agent_version: str,
        model_name: str | None,
        tool_definitions: list[dict[str, Any]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.path = Path(logs_dir) / FILENAME
        self._session_id = session_id
        self._agent = Agent(
            name=agent_name,
            version=agent_version,
            model_name=model_name,
            tool_definitions=tool_definitions,
        )
        self._model_name = model_name
        self._extra = extra or {}
        self._steps: list[Step] = []
        self._totals = {"prompt": 0, "completion": 0, "cached": 0}
        self._notes: str | None = None
        self._pending_graders: list[Step] = []
        self._grader_totals: dict[str, dict[str, int]] = {}

    # -- steps -------------------------------------------------------------
    def _next_id(self) -> int:
        return len(self._steps) + 1

    def add_message(self, source: str, text: str) -> None:
        self._steps.append(
            Step(step_id=self._next_id(), timestamp=_now(), source=source, message=text)
        )

    def add_agent_turn(
        self,
        turn: Any,
        results: list[tuple[str, str]],
    ) -> None:
        """Record one model turn and the tool results the model was shown.

        `results` pairs each tool_call_id with the (truncated) tool output.
        """
        usage = getattr(turn, "usage", {}) or {}
        prompt = int(usage.get("prompt_tokens", 0) or 0)
        completion = int(usage.get("completion_tokens", 0) or 0)
        cached = int(usage.get("cached_tokens", 0) or 0)
        self._totals["prompt"] += prompt
        self._totals["completion"] += completion
        self._totals["cached"] += cached
        calls = [
            ToolCall(
                tool_call_id=str(c.id),
                function_name=str(c.name),
                arguments=c.arguments if isinstance(c.arguments, dict) else {"raw": c.arguments},
            )
            for c in (getattr(turn, "tool_calls", None) or [])
        ]
        observation = (
            Observation(
                results=[
                    ObservationResult(source_call_id=call_id, content=content)
                    for call_id, content in results
                ]
            )
            if results
            else None
        )
        self._steps.append(
            Step(
                step_id=self._next_id(),
                timestamp=_now(),
                source="agent",
                model_name=self._model_name,
                message=getattr(turn, "content", None) or "",
                reasoning_content=getattr(turn, "raw_reasoning", None) or None,
                tool_calls=calls or None,
                observation=observation,
                metrics=Metrics(
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    cached_tokens=cached,
                ),
                extra={"retries": int(getattr(turn, "retries", 0) or 0)},
            )
        )
        self.drain_grader_calls()

    def add_grader_call(
        self,
        role: str,
        model_name: str | None,
        messages: list[dict[str, Any]],
        turn: Any = None,
        error: BaseException | None = None,
    ) -> None:
        """Queue one grader call; it is placed after the current agent turn."""
        try:
            prompt = "\n\n".join(
                f"[{m.get('role', 'user')}]\n{m.get('content', '')}"
                for m in messages
            )
            if error is not None:
                response = f"ERROR: {type(error).__name__}: {error}"
            else:
                response = getattr(turn, "content", "") or ""
            usage = (getattr(turn, "usage", None) or {}) if error is None else {}
            metrics = None
            if usage:
                metrics = Metrics(
                    prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                    cached_tokens=int(usage.get("cached_tokens", 0) or 0),
                )
                tot = self._grader_totals.setdefault(
                    f"{role}:{model_name}", {"prompt": 0, "completion": 0, "cached": 0}
                )
                tot["prompt"] += metrics.prompt_tokens or 0
                tot["completion"] += metrics.completion_tokens or 0
                tot["cached"] += metrics.cached_tokens or 0
            header = (
                f"[grader call: {role} ({model_name}); "
                "not shown to the tested model]"
            )
            self._pending_graders.append(
                Step(
                    step_id=1,  # renumbered when placed
                    timestamp=_now(),
                    # ATIF allows model_name/metrics only on agent-source
                    # steps; the header and extra mark it as a grader call.
                    source="agent",
                    model_name=model_name,
                    message=(
                        f"{header}\n\n----- prompt -----\n{prompt}"
                        f"\n\n----- response -----\n{response}"
                    ),
                    reasoning_content=(
                        getattr(turn, "raw_reasoning", None) or None
                        if error is None
                        else None
                    ),
                    metrics=metrics,
                    extra={
                        "grader_role": role,
                        "visible_to_tested_model": False,
                        "retries": int(getattr(turn, "retries", 0) or 0),
                    },
                )
            )
        except Exception:
            logger.debug("grader record failed", exc_info=True)

    def drain_grader_calls(self) -> None:
        for step in self._pending_graders:
            step.step_id = self._next_id()
            self._steps.append(step)
        self._pending_graders = []

    def set_notes(self, notes: str) -> None:
        self._notes = notes

    # -- output ------------------------------------------------------------
    def build(self) -> Trajectory:
        return Trajectory(
            session_id=self._session_id,
            agent=self._agent,
            steps=list(self._steps),
            notes=self._notes,
            final_metrics=FinalMetrics(
                total_prompt_tokens=self._totals["prompt"]
                + sum(t["prompt"] for t in self._grader_totals.values()),
                total_completion_tokens=self._totals["completion"]
                + sum(t["completion"] for t in self._grader_totals.values()),
                total_cached_tokens=self._totals["cached"]
                + sum(t["cached"] for t in self._grader_totals.values()),
                total_steps=len(self._steps),
                extra={
                    "tested_model": {
                        "model_name": self._model_name,
                        **{f"{k}_tokens": v for k, v in self._totals.items()},
                    },
                    "graders": {
                        key: {f"{k}_tokens": v for k, v in tot.items()}
                        for key, tot in self._grader_totals.items()
                    },
                },
            ),
            extra=self._extra or None,
        )

    def flush(self) -> None:
        """Atomically rewrite trajectory.json; never raises."""
        try:
            self.drain_grader_calls()
            data = json.dumps(self.build().to_json_dict(), ensure_ascii=False, indent=2)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(FILENAME + ".tmp")
            tmp.write_text(data, encoding="utf-8")
            tmp.replace(self.path)
        except Exception:  # recording must never break an episode
            logger.warning("trajectory.json not updated", exc_info=True)
