"""Traverse Harbor ATIF and extract ContextBench's custom-agent format."""

from __future__ import annotations

import json
import re
import traceback
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from ..vendor_api import ContextStep, aggregate_steps
from .receipts import TERMINAL_PROMPT, SourceRepository
from .rules import (
    COPIED_CONTEXT,
    BackgroundShell,
    RuleOutcome,
    ToolFamily,
    attribute,
    contained_failure,
    context_for_call,
    mutated_file,
    path_key,
    tool_family,
    unpaired_results,
)
from .types import (
    BACKGROUND_ID_KEYS,
    NON_CONTEXT_TOOLS,
    Observation,
    canonical_tool_name,
)

_SHELL_IDENTIFIERS = (
    re.compile(r"\bRunning in background with ID\s+([A-Za-z0-9_-]+)\b"),
    re.compile(r"\bProcess running with session ID\s+([A-Za-z0-9_-]+)\b"),
)
_CODEX_CHUNK_ID = re.compile(r"Chunk ID: [^\r\n]+")
_CODEX_WALL_TIME = re.compile(r"Wall time: [^\r\n]+")
_CODEX_PROCESS = re.compile(
    r"Process (?:exited with code -?\d+|running with session ID [A-Za-z0-9_-]+)"
)
_CODEX_TOKEN_COUNT = re.compile(r"Original token count: \d+")
# An offloaded-content reference, naming the call whose output was offloaded.
_OFFLOADED_REFERENCE = re.compile(r"mem_\d+_(tooluse_[A-Za-z0-9]+)_\d+")
_SHELL_ENVELOPE_KEYS = frozenset(
    {
        "returncode",
        "output",
        "exception_info",
        "output_head",
        "output_tail",
        "elided_chars",
        "warning",
    }
)
# Producer read schemas whose `offset` counts lines from 0 although the rule
# reads their tool name and path key as 1-based, as (ATIF `agent.name`, tool,
# path key): Mistral Vibe's `read_file` and Cortex Code's `read`.
_ZERO_BASED_PRODUCER_READS = frozenset(
    {("vibe", "read_file", "path"), ("cortex-code", "read", "file_path")}
)


@dataclass(frozen=True)
class _ToolCall:
    call_id: str
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class _ResolvedReference:
    trajectory: dict[str, Any]
    key: str
    label: str
    origin: Path | None


@dataclass
class _ProjectionState:
    # The IDs of the calls whose credit entered the prediction.
    credited_calls: set[str] = field(default_factory=set)
    background_shells: dict[str, BackgroundShell] = field(default_factory=dict)
    mutated_files: set[str] = field(default_factory=set)


@dataclass
class _ProjectionOutput:
    prediction_steps: list[ContextStep] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _TrajectoryContext:
    label: str
    origin_dir: Path | None
    embedded: dict[str, dict[str, Any]]
    state: _ProjectionState
    # The ATIF `agent.name` of the agent that produced the trajectory.
    producer: str | None


class _ObservationDecoder:
    """Normalize agent-specific ATIF observation envelopes."""

    @classmethod
    def for_call(
        cls,
        step: dict[str, Any],
        call_id: str,
        *,
        decode_cursor_result: bool,
    ) -> Observation | None:
        results = cls._results(step)
        if results is None:
            return None
        matched = next(
            (
                result
                for result in results
                if isinstance(result, dict) and result.get("source_call_id") == call_id
            ),
            None,
        ) or cls._paired_by_order(step, results, call_id)
        if matched is not None:
            return cls.result(
                matched,
                decode_cursor_result=decode_cursor_result,
            )
        batch = cls._terminus_batch(step)
        return batch.get(call_id)

    @staticmethod
    def _results(step: dict[str, Any]) -> list[Any] | None:
        observation = step.get("observation")
        return None if observation is None else observation.get("results")

    @staticmethod
    def _paired_by_order(
        step: dict[str, Any],
        results: list[Any],
        call_id: str,
    ) -> dict[str, Any] | None:
        """Pair results that name no call with the step's calls, in order.

        Harbor's mini-swe-agent converter records results without a
        `source_call_id`. When every result is unlinked and there is one per
        call, the n-th result belongs to the n-th call.
        """
        calls = step.get("tool_calls")
        if (
            not isinstance(calls, list)
            or len(calls) != len(results)
            or any(
                not isinstance(result, dict)
                or result.get("source_call_id") not in {None, ""}
                for result in results
            )
        ):
            return None
        return next(
            (
                result
                for call, result in zip(calls, results, strict=True)
                if isinstance(call, dict) and call.get("tool_call_id") == call_id
            ),
            None,
        )

    @classmethod
    def unpaired_results(cls, step: dict[str, Any]) -> str | None:
        """Explain why a step's unlinked results cannot be matched to its calls."""
        results = cls._results(step) or []
        calls = step.get("tool_calls")
        unlinked = [
            result
            for result in results
            if isinstance(result, dict)
            and result.get("source_call_id") in {None, ""}
            and result.get("content") not in {None, ""}
        ]
        if (
            not unlinked
            or not isinstance(calls, list)
            or not calls
            or cls._terminus_batch(step)
        ):
            return None
        return (
            f"step has {len(unlinked)} observation result(s) without a call ID for "
            f"{len(calls)} call(s); results cannot be matched to calls"
        )

    @classmethod
    def result(
        cls,
        result: dict[str, Any],
        *,
        decode_cursor_result: bool = False,
    ) -> Observation:
        content, error = cls._shell_envelope(cls._content(result.get("content")))
        extra = result.get("extra")
        if isinstance(extra, dict):
            raw_error = extra.get("error")
            if raw_error:
                error = str(raw_error)
            elif cls._extra_reports_error(extra):
                # Flag-only failures (Claude Code ``tool_result_is_error``,
                # Copilot ``success: False``) put the error text in the
                # content body, so the content is the message.
                error = content.strip() or "tool observation reports an error"
        if decode_cursor_result:
            content, error = cls._cursor(content, error)
        return Observation(content, error)

    @staticmethod
    def _shell_envelope(content: str) -> tuple[str, str | None]:
        """Unwrap mini-swe-agent's JSON shell observation.

        mini-swe-agent renders `{"returncode", "output"}`, adds
        `exception_info` when the command did not run, and replaces `output`
        with `output_head` and `output_tail` when it elides a long output.
        """
        if not content.startswith("{"):
            return content, None
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            return content, None
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("returncode"), int)
            or not set(value) <= _SHELL_ENVELOPE_KEYS
        ):
            return content, None
        output, head, tail = (
            value.get(key) for key in ("output", "output_head", "output_tail")
        )
        if isinstance(output, str):
            text = output
        elif isinstance(head, str) and isinstance(tail, str):
            # The marker line keeps the head and tail from joining into a run.
            elided = value.get("elided_chars", "some")
            text = f"{head}\n[{elided} characters elided]\n{tail}"
        else:
            return content, None
        exception = value.get("exception_info")
        return text, str(exception) if exception else None

    @staticmethod
    def _extra_reports_error(extra: dict[str, Any]) -> bool:
        """True when producer result metadata marks the tool call as failed.

        Producers spell the failure flag differently: OpenHands-style results
        use ``is_error``/``isError``, Claude Code forwards the raw content
        block flag as ``tool_result_is_error``, and Copilot CLI preserves the
        session event's ``success`` flag.
        """
        if any(
            extra.get(key) is True
            for key in ("is_error", "isError", "tool_result_is_error")
        ):
            return True
        return extra.get("success") is False

    @staticmethod
    def _content(raw_content: Any) -> str:
        content = "" if raw_content is None else raw_content
        if isinstance(content, list):
            if any(
                not isinstance(part, dict)
                or part.get("type") != "text"
                or not isinstance(part.get("text"), str)
                for part in content
            ):
                raise TypeError("ATIF observation contains non-text content")
            content = "\n".join(str(part["text"]) for part in content)
        if not isinstance(content, str):
            raise TypeError("ATIF observation content must be text")
        return content

    @classmethod
    def _cursor(
        cls,
        content: str,
        error: str | None,
    ) -> tuple[str, str | None]:
        try:
            decoded = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return content, error
        if not isinstance(decoded, dict) or set(decoded) not in (
            {"success"},
            {"failure"},
        ):
            return content, error
        decoded_content = cls._decoded_text(decoded)
        decoded_error = cls._decoded_error(decoded)
        return decoded_content or content, decoded_error or error

    @classmethod
    def _decoded_text(cls, value: dict[str, Any]) -> str | None:
        direct: list[str] = []
        has_direct_text = False
        for key in ("output", "stdout", "content", "text", "stderr"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                has_direct_text = True
                if candidate and candidate not in direct:
                    direct.append(candidate)
        if has_direct_text:
            return "\n".join(direct)
        for key in ("success", "result", "data", "response"):
            candidate = value.get(key)
            if isinstance(candidate, dict):
                nested = cls._decoded_text(candidate)
                if nested is not None:
                    return nested
        return None

    @classmethod
    def _decoded_error(cls, value: dict[str, Any]) -> str | None:
        if raw_error := value.get("error"):
            return str(raw_error)
        if value.get("is_error") is True or value.get("isError") is True:
            return "tool observation reports an error"
        failure = value.get("failure")
        if isinstance(failure, str) and failure:
            return failure
        if isinstance(failure, dict):
            return cls._decoded_error(failure) or json.dumps(failure, sort_keys=True)
        return None

    @classmethod
    def _terminus_batch(cls, step: dict[str, Any]) -> dict[str, Observation]:
        calls = cls._terminus_calls(step.get("tool_calls"))
        observation = step.get("observation")
        if calls is None or len(calls) < 2 or not isinstance(observation, dict):
            return {}
        results = observation.get("results")
        if (
            not isinstance(results, list)
            or len(results) != 1
            or not isinstance(results[0], dict)
            or results[0].get("source_call_id") not in {None, ""}
        ):
            return {}
        shared = cls.result(results[0])
        if shared.error is not None:
            return {}
        lines = shared.content.splitlines()
        if not lines or lines[0] not in {
            "New Terminal Output:",
            "Current Terminal Screen:",
        }:
            return {}

        prompts = [
            (index, match.group(1).strip())
            for index, line in enumerate(lines[1:], start=1)
            if (match := TERMINAL_PROMPT.fullmatch(line)) is not None
        ]
        expected = [command for _, command in calls if command]
        if [command for _, command in prompts if command] != expected:
            return {}
        result: dict[str, Observation] = {
            call_id: Observation("") for call_id, command in calls if not command
        }
        prompt_index = 0
        for call_id, command in calls:
            if not command:
                continue
            start = prompts[prompt_index][0] + 1
            end = (
                prompts[prompt_index + 1][0]
                if prompt_index + 1 < len(prompts)
                else len(lines)
            )
            result[call_id] = Observation("\n".join(lines[start:end]))
            prompt_index += 1
        return result

    @staticmethod
    def _terminus_calls(raw_calls: Any) -> list[tuple[str, str]] | None:
        if not isinstance(raw_calls, list):
            return None
        calls: list[tuple[str, str]] = []
        for raw_call in raw_calls:
            if not isinstance(raw_call, dict):
                return None
            normalized = canonical_tool_name(str(raw_call.get("function_name") or ""))
            if normalized in NON_CONTEXT_TOOLS:
                continue
            if normalized != "bash_command":
                return None
            arguments = raw_call.get("arguments")
            call_id = str(raw_call.get("tool_call_id") or "")
            if not isinstance(arguments, dict) or not call_id:
                return None
            calls.append((call_id, str(arguments.get("keystrokes") or "").strip()))
        return calls

    @staticmethod
    def codex_content(content: str) -> tuple[str | None, str | None]:
        if not content.startswith("Chunk ID:"):
            return content, None
        lines = content.splitlines(keepends=True)
        if len(lines) < 4:
            return None, "Codex terminal observation has an incomplete result envelope"
        values = [line.rstrip("\r\n") for line in lines]
        if (
            _CODEX_CHUNK_ID.fullmatch(values[0]) is None
            or _CODEX_WALL_TIME.fullmatch(values[1]) is None
            or _CODEX_PROCESS.fullmatch(values[2]) is None
        ):
            return None, "Codex terminal observation has an unknown result envelope"
        output_index = 3
        if _CODEX_TOKEN_COUNT.fullmatch(values[output_index]) is not None:
            output_index += 1
        if output_index >= len(lines) or values[output_index] not in {
            "Output:",
            "Final output:",
        }:
            return None, "Codex terminal observation has no recognized output boundary"
        return "".join(lines[output_index + 1 :]), None


class _TrajectoryLoader:
    """Load continuation chains and constrain all references to one directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def load(self, path: Path) -> dict[str, Any]:
        """Load a continuation chain from the file of its first document."""
        current = path.resolve()
        if not current.is_relative_to(self.root):
            raise ValueError("ATIF continuation escapes the trajectory directory")
        return self._merged(self._read(current), current.parent, {current})

    def continued(self, trajectory: dict[str, Any], origin_dir: Path) -> dict[str, Any]:
        """Merge an embedded trajectory with the chain its continuation names."""
        if not trajectory.get("continued_trajectory_ref"):
            return trajectory
        return self._merged(trajectory, origin_dir, set())

    def _merged(
        self, first: dict[str, Any], base: Path, seen: set[Path]
    ) -> dict[str, Any]:
        """Join the documents of a chain; `base` resolves the first's reference."""
        steps: list[Any] = []
        embedded: list[Any] = []
        document = first
        while continuation := self._append_document(document, steps, embedded):
            if not isinstance(continuation, str):
                raise TypeError("ATIF continued_trajectory_ref must be a string")
            current = self.path(base, continuation, "continued_trajectory_ref")
            if current in seen:
                raise ValueError(f"ATIF continuation cycle at {current.name}")
            seen.add(current)
            document, base = self._read(current), current.parent
        merged = {**first, "steps": steps, "continued_trajectory_ref": None}
        if embedded:
            merged["subagent_trajectories"] = embedded
        else:
            merged.pop("subagent_trajectories", None)
        return merged

    @staticmethod
    def _append_document(
        document: dict[str, Any],
        steps: list[Any],
        embedded: list[Any],
    ) -> Any:
        document_steps = document.get("steps")
        if not isinstance(document_steps, list):
            raise TypeError("ATIF trajectory steps must be an array")
        steps.extend(document_steps)
        document_embedded = document.get("subagent_trajectories")
        if document_embedded is not None:
            if not isinstance(document_embedded, list):
                raise TypeError("ATIF subagent_trajectories must be an array")
            embedded.extend(document_embedded)
        return document.get("continued_trajectory_ref")

    def path(self, base: Path, raw_path: str, reference: str) -> Path:
        """Resolve a `reference` (a continuation or subagent trajectory) in the root."""
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", raw_path):
            raise ValueError(
                f"remote ATIF {reference} is not available to the verifier"
            )
        candidate = Path(raw_path)
        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (base / candidate).resolve()
        )
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"ATIF {reference} escapes the trajectory directory")
        return resolved

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError(f"ATIF trajectory is missing: {path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"ATIF trajectory is invalid JSON: {error}") from error
        if not isinstance(document, dict):
            raise TypeError("ATIF trajectory root must be an object")
        return document


class _AtifProjector:
    """Validate and traverse one ATIF trajectory graph."""

    def __init__(
        self,
        repository: SourceRepository,
        trajectory_root: Path | None,
    ) -> None:
        self.repository = repository
        self.trajectory_root = trajectory_root
        self.loader = _TrajectoryLoader(trajectory_root) if trajectory_root else None
        self.output = _ProjectionOutput()
        self.active_subagents: set[str] = set()
        self.visited_subagents: set[str] = set()

    def project(
        self,
        trajectory: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        self._trajectory(trajectory, "root", self.trajectory_root)
        final_files, final_spans = aggregate_steps(self.output.prediction_steps)
        prediction = {
            "pred_steps": self.output.prediction_steps,
            "pred_files": final_files,
            "pred_spans": final_spans,
        }
        return prediction, self.output.evidence

    def _trajectory(
        self,
        trajectory: dict[str, Any],
        label: str,
        origin_dir: Path | None,
    ) -> None:
        steps = _validated_steps(trajectory)
        agent = trajectory.get("agent")
        producer = agent.get("name") if isinstance(agent, dict) else None
        context = _TrajectoryContext(
            label,
            origin_dir,
            self._embedded(trajectory),
            _ProjectionState(),
            producer if isinstance(producer, str) else None,
        )
        for index, step in enumerate(steps):
            self._step(step, index, context)

    def _step(
        self,
        step: dict[str, Any],
        index: int,
        context: _TrajectoryContext,
    ) -> None:
        calls = step.get("tool_calls") or []
        for raw_call in calls:
            self._call(raw_call, step, index, context)
        if step.get("is_copied_context") is True:
            return
        observation = step.get("observation")
        results = observation.get("results") if observation is not None else None
        for result_index, raw_result in enumerate(results or []):
            self._result_references(
                raw_result,
                result_index,
                index,
                calls,
                context,
            )

    def _call(
        self,
        raw_call: dict[str, Any],
        step: dict[str, Any],
        step_index: int,
        context: _TrajectoryContext,
    ) -> None:
        call = _ToolCall(
            str(raw_call["tool_call_id"]),
            str(raw_call["function_name"]),
            cast(dict[str, Any], raw_call["arguments"]),
        )
        failure: str | None = None
        try:
            result = self._attribute_call(call, step, context)
        except Exception as error:  # noqa: BLE001 - containment boundary.
            # Attribution consumes agent-authored text and producer-shaped
            # observations; an unanticipated defect while examining one call
            # must degrade to a diagnosed malformed call, not abort the
            # trial. Structural trajectory errors are validated before this
            # point and remain fatal.
            failure = traceback.format_exc(limit=8)
            result = contained_failure(error)
        self._record_result(result, call, step_index, context, failure=failure)

    def _attribute_call(
        self,
        call: _ToolCall,
        step: dict[str, Any],
        context: _TrajectoryContext,
    ) -> RuleOutcome:
        if step.get("is_copied_context") is True:
            return COPIED_CONTEXT
        observation, raw_observation = self._observation(step, call)
        if observation is None and (
            reason := _ObservationDecoder.unpaired_results(step)
        ):
            return unpaired_results(reason)
        state = context.state
        arguments = self._arguments(call, context.producer)
        family = tool_family(call.tool)
        call_context = context_for_call(
            raw_tool=call.tool,
            arguments=arguments,
            observation=observation,
            repository=self.repository,
            mutated_files=frozenset(state.mutated_files),
            background_origin=(
                state.background_shells.get(_background_session(arguments))
                if family is ToolFamily.BACKGROUND
                else None
            ),
            offloaded_source_credited=(
                family is ToolFamily.OFFLOADED
                and _offloaded_source(arguments) in state.credited_calls
            ),
        )
        result = attribute(call_context)
        if (changed := mutated_file(call_context)) is not None:
            state.mutated_files.add(changed)
        if call_context.family is ToolFamily.SHELL:
            # Session identifiers are scanned in the raw result too:
            # Codex reports them in the envelope that ``codex_content``
            # strips before attribution.
            self._record_background(
                call.arguments,
                (observation, raw_observation),
                result.credited,
                state,
            )
        return result

    @staticmethod
    def _arguments(call: _ToolCall, producer: str | None) -> dict[str, Any]:
        """Restate a producer's 0-based read `offset` as the rule's 1-based one."""
        arguments = call.arguments
        offset = arguments.get("offset")
        if (
            not isinstance(offset, int)
            or isinstance(offset, bool)
            or (producer, canonical_tool_name(call.tool), path_key(arguments))
            not in _ZERO_BASED_PRODUCER_READS
        ):
            return arguments
        return {**arguments, "offset": offset + 1}

    def _observation(
        self,
        step: dict[str, Any],
        call: _ToolCall,
    ) -> tuple[Observation | None, Observation | None]:
        """Return the decoded observation and the raw pre-decode observation."""
        raw_tool = call.tool.casefold()
        observation = _ObservationDecoder.for_call(
            step,
            call.call_id,
            decode_cursor_result=(
                raw_tool.endswith(("toolcall", "tool_call"))
                or raw_tool.startswith("cursor")
            ),
        )
        if observation is None:
            return None, None
        if canonical_tool_name(call.tool) == "exec_command":
            content, error = _ObservationDecoder.codex_content(observation.content)
            return Observation(content or "", error or observation.error), observation
        return observation, observation

    @staticmethod
    def _record_background(
        arguments: dict[str, Any],
        observations: tuple[Observation | None, ...],
        credited: bool,
        state: _ProjectionState,
    ) -> None:
        contents = [observation.content for observation in observations if observation]
        if not contents:
            return
        identifiers = {
            str(match.group(1))
            for content in contents
            for pattern in _SHELL_IDENTIFIERS
            if (match := pattern.search(content)) is not None
        }
        for identifier in identifiers:
            state.background_shells[identifier] = BackgroundShell(arguments, credited)

    def _record_result(
        self,
        result: RuleOutcome,
        call: _ToolCall,
        step_index: int,
        context: _TrajectoryContext,
        failure: str | None = None,
    ) -> None:
        family = tool_family(call.tool)
        record: dict[str, Any] = {
            "trajectory": context.label,
            "step_index": step_index,
            "tool_call_id": call.call_id,
            "tool": call.tool,
            "canonical_tool": canonical_tool_name(call.tool),
            "family": family.value,
            "result": result.status.value,
            "classification": result.classification.value,
            "heuristic": result.rule_id,
            "reason": result.reason,
        }
        if result.step is not None:
            record["step"] = result.step
        if failure is not None:
            # The contained traceback keeps a defect diagnosable from the
            # verifier output alone, without re-running the trial.
            record["failure_traceback"] = failure[:4000]
        self.output.evidence.append(record)
        if result.credited and result.step and result.step.get("files"):
            self.output.prediction_steps.append(result.step)
            context.state.credited_calls.add(call.call_id)

    def _result_references(
        self,
        raw_result: dict[str, Any],
        result_index: int,
        step_index: int,
        calls: list[Any],
        context: _TrajectoryContext,
    ) -> None:
        references = raw_result.get("subagent_trajectory_ref")
        call_id = str(raw_result.get("source_call_id") or "")
        if not calls and not call_id and not references:
            self._unlinked_observation(raw_result, step_index, context)
            return
        if references is None:
            return
        if not isinstance(references, list):
            raise TypeError(
                f"ATIF trajectory step {step_index} observation result "
                f"{result_index} subagent_trajectory_ref must be an array"
            )
        for reference in references:
            self._reference(reference, context)

    def _reference(
        self,
        raw_reference: Any,
        context: _TrajectoryContext,
    ) -> None:
        if not isinstance(raw_reference, dict):
            raise TypeError("ATIF subagent trajectory reference must be an object")
        resolved = self._resolve_reference(raw_reference, context)
        if resolved.key in self.active_subagents:
            raise ValueError(
                f"ATIF subagent trajectory reference cycle at {resolved.label}"
            )
        if resolved.key in self.visited_subagents:
            return
        self.active_subagents.add(resolved.key)
        try:
            self._trajectory(
                resolved.trajectory,
                resolved.label,
                resolved.origin,
            )
        finally:
            self.active_subagents.remove(resolved.key)
        self.visited_subagents.add(resolved.key)

    def _resolve_reference(
        self,
        reference: dict[str, Any],
        context: _TrajectoryContext,
    ) -> _ResolvedReference:
        raw_id = reference.get("trajectory_id")
        raw_path = reference.get("trajectory_path")
        if raw_id is not None and (not isinstance(raw_id, str) or not raw_id):
            raise ValueError("ATIF subagent trajectory_id must be a nonempty string")
        if raw_path is not None and (not isinstance(raw_path, str) or not raw_path):
            raise ValueError("ATIF subagent trajectory_path must be a nonempty string")
        if raw_id is not None and raw_id in context.embedded:
            return self._resolve_embedded(raw_id, context)
        if raw_path is not None:
            return self._resolve_external(raw_path, context)
        if raw_id is not None:
            raise ValueError(
                f"ATIF embedded subagent trajectory {raw_id!r} does not exist"
            )
        raise ValueError(
            "ATIF subagent reference has neither trajectory_id nor trajectory_path"
        )

    def _resolve_embedded(
        self,
        trajectory_id: str,
        context: _TrajectoryContext,
    ) -> _ResolvedReference:
        trajectory = context.embedded[trajectory_id]
        if self.loader is not None and context.origin_dir is not None:
            trajectory = self.loader.continued(trajectory, context.origin_dir)
        return _ResolvedReference(
            trajectory,
            f"{context.label}/embedded:{trajectory_id}",
            f"{context.label}/subagent:{trajectory_id}",
            context.origin_dir,
        )

    def _resolve_external(
        self,
        raw_path: str,
        context: _TrajectoryContext,
    ) -> _ResolvedReference:
        if self.loader is None or context.origin_dir is None:
            raise ValueError(
                "external subagent trajectory cannot be resolved without "
                "the root trajectory directory"
            )
        path = self.loader.path(
            context.origin_dir, raw_path, "subagent trajectory reference"
        )
        trajectory = self.loader.load(path)
        return _ResolvedReference(
            trajectory,
            f"file:{path}",
            f"{context.label}/subagent-file:{path.name}",
            path.parent,
        )

    def _unlinked_observation(
        self,
        raw_result: dict[str, Any],
        step_index: int,
        context: _TrajectoryContext,
    ) -> None:
        observation = _ObservationDecoder.result(raw_result)
        if not observation.content.strip():
            return
        call_context = context_for_call(
            raw_tool="unlinked_observation",
            arguments={},
            observation=observation,
            repository=self.repository,
        )
        result = attribute(call_context)
        call = _ToolCall("", "unlinked_observation", {})
        self._record_result(result, call, step_index, context)

    @staticmethod
    def _embedded(trajectory: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw_embedded = trajectory.get("subagent_trajectories")
        if raw_embedded is None:
            return {}
        if not isinstance(raw_embedded, list):
            raise TypeError("ATIF subagent_trajectories must be an array")
        embedded: dict[str, dict[str, Any]] = {}
        for index, candidate in enumerate(raw_embedded):
            if not isinstance(candidate, dict):
                raise TypeError(
                    f"ATIF subagent_trajectories[{index}] must be an object"
                )
            trajectory_id = candidate.get("trajectory_id")
            if not isinstance(trajectory_id, str) or not trajectory_id:
                raise ValueError(
                    f"ATIF subagent_trajectories[{index}] has no trajectory_id"
                )
            if trajectory_id in embedded:
                raise ValueError(
                    "ATIF subagent_trajectories has duplicate trajectory_id "
                    f"{trajectory_id!r}"
                )
            embedded[trajectory_id] = candidate
        return embedded


def _background_session(arguments: dict[str, Any]) -> str:
    """The session a background poll reads, as its shell call reported it."""
    return next(
        (str(arguments[key]) for key in BACKGROUND_ID_KEYS if arguments.get(key)), ""
    )


def _offloaded_source(arguments: dict[str, Any]) -> str | None:
    """The ID of the call whose output an offloaded-content read retrieves."""
    match = _OFFLOADED_REFERENCE.fullmatch(str(arguments.get("reference") or ""))
    return str(match.group(1)) if match is not None else None


def _validated_steps(trajectory: Any) -> list[dict[str, Any]]:
    """Return a trajectory's steps after checking their structure.

    Structural defects raise. A call ID may be empty: Codex records its
    built-in web_search_call actions without IDs. Such a call never links to a
    result but is still classified, so only non-empty IDs must be unique.
    Results without a call ID are paired with calls in order, or their calls
    are classified malformed.
    """
    if not isinstance(trajectory, dict):
        raise TypeError("ATIF trajectory must be a JSON object")
    steps = trajectory.get("steps")
    if not isinstance(steps, list):
        raise TypeError("ATIF trajectory steps must be a JSON array")
    call_ids: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise TypeError(f"ATIF trajectory step {index} must be an object")
        calls = step.get("tool_calls")
        if calls is not None and not isinstance(calls, list):
            raise TypeError(f"ATIF trajectory step {index} tool_calls must be an array")
        step_call_ids: set[str] = set()
        for call in calls or []:
            if call_id := _validated_call_id(call, index, call_ids):
                call_ids.add(call_id)
                step_call_ids.add(call_id)
        _validate_results(step, index, step_call_ids)
    return steps


def _validated_call_id(raw_call: Any, step_index: int, call_ids: set[str]) -> str:
    if not isinstance(raw_call, dict):
        raise TypeError(f"ATIF trajectory step {step_index} contains a non-object call")
    call_id = raw_call.get("tool_call_id")
    if not isinstance(call_id, str):
        raise TypeError(
            f"ATIF trajectory step {step_index} has a non-string tool_call_id"
        )
    if call_id and call_id in call_ids:
        raise ValueError(f"ATIF trajectory has duplicate tool_call_id {call_id!r}")
    function_name = raw_call.get("function_name")
    if not isinstance(function_name, str) or not function_name:
        raise ValueError(
            f"ATIF trajectory step {step_index} has an empty or "
            "non-string function_name"
        )
    if not isinstance(raw_call.get("arguments"), dict):
        raise TypeError(
            f"ATIF trajectory step {step_index} tool call arguments must be an object"
        )
    return call_id


def _validate_results(
    step: dict[str, Any], step_index: int, step_call_ids: set[str]
) -> None:
    observation = step.get("observation")
    if observation is not None and not isinstance(observation, dict):
        raise TypeError(
            f"ATIF trajectory step {step_index} observation must be an object"
        )
    results = observation.get("results") if isinstance(observation, dict) else None
    if results is None:
        return
    if not isinstance(results, list):
        raise TypeError(
            f"ATIF trajectory step {step_index} observation results must be an array"
        )
    linked: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            raise TypeError(
                f"ATIF trajectory step {step_index} contains a non-object "
                "observation result"
            )
        call_id = result.get("source_call_id")
        if call_id in {None, ""}:
            continue
        if not isinstance(call_id, str):
            raise TypeError(
                f"ATIF trajectory step {step_index} has a non-string "
                "observation source_call_id"
            )
        if call_id in linked:
            raise ValueError(
                f"ATIF trajectory step {step_index} has duplicate observation "
                f"source_call_id {call_id!r}"
            )
        linked.add(call_id)
        if call_id not in step_call_ids:
            raise ValueError(
                f"ATIF trajectory step {step_index} observation references "
                f"unknown tool_call_id {call_id!r}"
            )


def load_trajectory_chain(
    path: Path,
    *,
    allowed_root: Path | None = None,
) -> dict[str, Any]:
    """Load one local ATIF continuation chain within a fixed directory."""
    return _TrajectoryLoader(allowed_root or path.parent).load(path)


def project_atif(
    trajectory: dict[str, Any],
    repo_dir: Path | str,
    *,
    roots: Iterable[str],
    trajectory_dir: Path | str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Produce ContextBench custom-agent data and non-fatal call diagnostics.

    `repo_dir` is the scoring checkout. `roots` are the absolute paths at which
    the agent's environment mounted the repository; a path under one of them
    names a checkout file exactly. Unsupported valid calls receive no credit
    plus diagnostics; structural ATIF errors raise.
    """
    repository = SourceRepository(repo_dir, roots=roots)
    root = Path(trajectory_dir).resolve() if trajectory_dir is not None else None
    if root is not None and not root.is_dir():
        raise ValueError(f"trajectory directory does not exist: {root}")
    return _AtifProjector(repository, root).project(trajectory)


__all__ = ["load_trajectory_chain", "project_atif"]
