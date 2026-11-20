"""The attribution rule: decide the credit of each ATIF tool call (ATTRIBUTION.md)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from ..vendor_api import ContextStep
from .receipts import ObservationAttributor, SourceRepository, shell_claim
from .types import (
    BACKGROUND_OUTPUT_TOOLS,
    DISCOVERY_TOOLS,
    EXTERNAL_CONTENT_TOOLS,
    MULTI_READ_TOOLS,
    MUTATION_TOOLS,
    NON_CONTEXT_TOOLS,
    READ_TOOLS,
    SEARCH_TOOLS,
    SHELL_TOOLS,
    SUBAGENT_TOOLS,
    UNATTRIBUTED_CONTENT_TOOLS,
    Claim,
    Classification,
    LineRanges,
    Observation,
    RangeSet,
    canonical_tool_name,
)

# Version of the attribution rule defined in ATTRIBUTION.md. Bump whenever a
# change alters which calls receive credit; the calibration test pins the
# rule's behavior against the vendored oracle on the retained corpus for
# each version.
ATTRIBUTION_VERSION = 6

_PATH_KEYS = ("file_path", "filePath", "path", "filename")
_PATH_LIST_KEYS = ("paths", "files", "file_paths", "filePaths")
_VIEW_COMMANDS = {"", "open", "read", "view"}
# Read schemas whose `offset` counts lines from 0, as (tool, path key): Qwen
# Code's `read_file`. Every other `offset`, and every other line argument,
# counts from 1. ATTRIBUTION.md lists the schemas each range argument comes
# from. Decoding restates the 0-based schemas that this key cannot tell apart
# from 1-based ones before the rule reads them (see trajectory.py).
_ZERO_BASED_OFFSET_SCHEMAS = {("read_file", "file_path")}


class ResultStatus(StrEnum):
    """Outcome of applying the rule to one call."""

    NO_MATCH = "no_match"
    NO_CREDIT = "no_credit"
    CREDIT = "credit"
    MALFORMED = "malformed"


class ToolFamily(StrEnum):
    READ = "read"
    MULTI_READ = "multi_read"
    SEARCH = "search"
    SHELL = "shell"
    BACKGROUND = "background"
    DISCOVERY = "discovery"
    MUTATION = "mutation"
    NON_CONTEXT = "non_context"
    EXTERNAL = "external"
    UNATTRIBUTED = "unattributed"
    SUBAGENT = "subagent"
    OFFLOADED = "offloaded"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BackgroundShell:
    """A shell call whose output named a background session."""

    arguments: dict[str, Any]
    credited: bool


@dataclass(frozen=True)
class CallContext:
    """Normalized inputs available to the rule."""

    raw_tool: str
    tool: str
    family: ToolFamily
    arguments: dict[str, Any]
    observation: Observation | None
    repository: SourceRepository
    # Checkout files that an earlier structured call in the trajectory changed.
    mutated_files: frozenset[str] = frozenset()
    # A background poll's shell call, when the trajectory recorded it.
    background_origin: BackgroundShell | None = None
    # Whether the call that offloaded content was credited.
    offloaded_source_credited: bool = False


@dataclass(frozen=True)
class RuleOutcome:
    """The rule's decision about a call, and the step of the rule that made it."""

    status: ResultStatus
    classification: Classification
    reason: str
    step: ContextStep | None = None
    rule_id: str = ""

    @classmethod
    def no_credit(
        cls,
        reason: str,
        classification: Classification = Classification.NON_BASE_CONTEXT,
    ) -> RuleOutcome:
        return cls(ResultStatus.NO_CREDIT, classification, reason)

    @classmethod
    def credit(cls, step: ContextStep, reason: str) -> RuleOutcome:
        return cls(ResultStatus.CREDIT, Classification.PROJECTED, reason, step)

    @property
    def credited(self) -> bool:
        return self.status is ResultStatus.CREDIT and self.step is not None

    def decided_by(self, rule_id: str) -> RuleOutcome:
        return replace(self, rule_id=rule_id)


# Decisions made before a call is examined, and when its examination raises.
COPIED_CONTEXT = RuleOutcome(
    ResultStatus.NO_CREDIT,
    Classification.INTENTIONAL_NON_CONTEXT,
    "copied continuation context is not counted twice",
    rule_id="atif.copied_context",
)


def unpaired_results(reason: str) -> RuleOutcome:
    return RuleOutcome(
        ResultStatus.MALFORMED,
        Classification.MALFORMED,
        reason,
        rule_id="atif.unpaired_results",
    )


def contained_failure(error: Exception) -> RuleOutcome:
    return RuleOutcome(
        ResultStatus.MALFORMED,
        Classification.MALFORMED,
        "attribution failed for this call and was contained: "
        f"{type(error).__name__}: {error}",
        rule_id="registry.contained_failure",
    )


def tool_family(tool: str) -> ToolFamily:
    """Classify a canonical Harbor tool name into a broad semantic family."""
    normalized = canonical_tool_name(tool)
    families = (
        (READ_TOOLS, ToolFamily.READ),
        (MULTI_READ_TOOLS, ToolFamily.MULTI_READ),
        (SEARCH_TOOLS, ToolFamily.SEARCH),
        (SHELL_TOOLS, ToolFamily.SHELL),
        (BACKGROUND_OUTPUT_TOOLS, ToolFamily.BACKGROUND),
        (DISCOVERY_TOOLS, ToolFamily.DISCOVERY),
        (MUTATION_TOOLS, ToolFamily.MUTATION),
        (NON_CONTEXT_TOOLS, ToolFamily.NON_CONTEXT),
        (EXTERNAL_CONTENT_TOOLS, ToolFamily.EXTERNAL),
        (UNATTRIBUTED_CONTENT_TOOLS, ToolFamily.UNATTRIBUTED),
        (SUBAGENT_TOOLS, ToolFamily.SUBAGENT),
    )
    for names, family in families:
        if normalized in names:
            return family
    if normalized == "retrieve_offloaded_content":
        return ToolFamily.OFFLOADED
    return ToolFamily.UNKNOWN


# Families decided by the tool alone.
_STATIC_OUTCOMES = {
    ToolFamily.DISCOVERY: (
        "tool discovers repository paths without reading source",
        Classification.DISCOVERY_ONLY,
    ),
    ToolFamily.MUTATION: (
        "file mutation is not a context retrieval",
        Classification.INTENTIONAL_NON_CONTEXT,
    ),
    ToolFamily.NON_CONTEXT: (
        "agent bookkeeping does not expose repository context",
        Classification.INTENTIONAL_NON_CONTEXT,
    ),
    ToolFamily.EXTERNAL: (
        "external content has no pinned-checkout provenance",
        Classification.NON_BASE_CONTEXT,
    ),
    ToolFamily.UNATTRIBUTED: (
        "tool has no source-attribution contract",
        Classification.UNMAPPED,
    ),
    ToolFamily.SUBAGENT: (
        "subagent coordination is represented by its referenced trajectory",
        Classification.INTENTIONAL_NON_CONTEXT,
    ),
}
_READ_FAMILIES = frozenset({ToolFamily.READ, ToolFamily.MULTI_READ})
# Families whose output is examined as receipts.
_OBSERVED_FAMILIES = frozenset(
    {
        ToolFamily.READ,
        ToolFamily.MULTI_READ,
        ToolFamily.SEARCH,
        ToolFamily.SHELL,
        ToolFamily.OFFLOADED,
        ToolFamily.UNKNOWN,
    }
)


def _tool_error(context: CallContext) -> RuleOutcome | None:
    """A failed structured read earns nothing (see ATTRIBUTION.md).

    Read credit comes from the call's arguments, so the producer's failure
    flag is the only evidence that the read did not happen. Every other
    family is credited from validated receipts, which prove themselves; a
    failed call of those families goes through `_observation`.
    """
    observation = context.observation
    if observation is None or observation.error is None:
        return None
    return RuleOutcome.no_credit(
        f"tool reported failure; its output earns no credit: {observation.error}",
        Classification.TOOL_ERROR,
    )


def path_key(arguments: dict[str, Any]) -> str | None:
    """The argument that names a structured call's path, as the rule reads it."""
    for key in _PATH_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return key
    return None


def _path_argument(arguments: dict[str, Any]) -> str:
    key = path_key(arguments)
    return str(arguments[key]) if key is not None else ""


def _editor_command(arguments: dict[str, Any]) -> str:
    return str(arguments.get("command") or arguments.get("action") or "").casefold()


def _line_pair(start: Any, end: Any) -> tuple[int, int] | None:
    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
    ):
        return None
    if start < 1 or end < start:
        return None
    return start, end


def _view_range(
    arguments: dict[str, Any],
) -> tuple[list[tuple[int, int]], str | None] | None:
    """OpenHands, Strands and Copilot editors: a 1-based `[start, end]`."""
    if "view_range" not in arguments:
        return None
    value = arguments["view_range"]
    pair = (
        _line_pair(value[0], value[1])
        if isinstance(value, list) and len(value) >= 2
        else None
    )
    return ([pair], None) if pair is not None else ([], "invalid view_range")


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _offset_range(
    tool: str,
    arguments: dict[str, Any],
) -> tuple[list[tuple[int, int]], str | None] | None:
    offset = arguments.get("offset")
    limit = arguments.get("limit")
    if offset is None and limit is None:
        return None
    if (offset is not None and not _is_integer(offset)) or (
        limit is not None and not _is_integer(limit)
    ):
        return [], "invalid offset/limit range"
    first = 0 if (tool, path_key(arguments)) in _ZERO_BASED_OFFSET_SCHEMAS else 1
    start = max(int(offset) + 1 - first if offset is not None else 1, 1)
    if limit is None:
        return [], None
    if limit < 1:
        return [], "invalid offset/limit range"
    return [(start, start + limit - 1)], None


def _line_offset_range(
    arguments: dict[str, Any],
) -> tuple[list[tuple[int, int]], str | None] | None:
    """kimi-code and kimi-cli: a 1-based `line_offset`, negative for a tail."""
    if "line_offset" not in arguments and "n_lines" not in arguments:
        return None
    offset = arguments.get("line_offset", 1)
    count = arguments.get("n_lines")
    if (
        not _is_integer(offset)
        or offset == 0
        or (count is not None and (not _is_integer(count) or count < 1))
    ):
        return [], "invalid line_offset/n_lines range"
    if offset < 0 or count is None:
        return [], None
    return [(offset, offset + count - 1)], None


def _explicit_range(
    arguments: dict[str, Any],
) -> tuple[list[tuple[int, int]], str | None] | None:
    count = arguments.get("line_count")
    if count is not None:
        # fx: a 1-based `start_line` and a `line_count`.
        start = arguments.get("start_line", 1)
        if not _is_integer(start) or not _is_integer(count) or count < 1:
            return [], "invalid start_line/line_count range"
        pair = _line_pair(start, start + count - 1)
        return ([pair] if pair is not None else []), (
            None if pair is not None else "invalid start_line/line_count range"
        )
    # Gemini CLI: a 1-based `start_line` and `end_line`.
    start = arguments.get("start_line")
    end = arguments.get("end_line")
    if start is None and end is None:
        return None
    pair = _line_pair(start if start is not None else 1, end)
    return ([pair] if pair is not None else []), (
        None if pair is not None else "invalid start/end line range"
    )


def _read_ranges(
    tool: str,
    arguments: dict[str, Any],
) -> tuple[list[tuple[int, int]], str | None]:
    """Parse a structured read's declared line ranges, 1-based and inclusive."""
    for result in (
        _view_range(arguments),
        _offset_range(tool, arguments),
        _line_offset_range(arguments),
        _explicit_range(arguments),
    ):
        if result:
            return result
    return [], None


def _clamped(
    ranges: list[tuple[int, int]],
    line_count: int,
) -> tuple[list[tuple[int, int]], bool]:
    """Clamp ranges to the base file; drop, and report, those that start past it."""
    kept = [
        (start, min(end, line_count)) for start, end in ranges if start <= line_count
    ]
    return kept, len(kept) < len(ranges)


def _receipt_ranges(context: CallContext, paths: tuple[str, ...]) -> LineRanges:
    """Return what the call's own output validates for `paths`."""
    observation = context.observation
    if observation is None or not observation.content.strip():
        return {}
    claim = ObservationAttributor(
        context.repository,
        cwd=context.repository.root,
        path_hints=paths,
    ).project(observation.content)
    return {
        path: ranges for path, ranges in (claim.ranges or {}).items() if path in paths
    }


def _declared_ranges(
    context: CallContext,
    path: str,
    arguments: dict[str, Any],
) -> tuple[list[tuple[int, int]], list[str]]:
    """A read's declared ranges, clamped to the base file, and what was ignored."""
    ranges, range_error = _read_ranges(context.tool, arguments)
    ranges, past_end = _clamped(ranges, context.repository.line_count(path))
    ignored: list[str] = [range_error] if range_error is not None else []
    if past_end:
        ignored.append("a range that starts past the end of the base file")
    return ranges, ignored


def _read(context: CallContext) -> RuleOutcome | None:
    if _editor_command(context.arguments) not in _VIEW_COMMANDS:
        return RuleOutcome.no_credit(
            "file-editor mutation is not a context retrieval",
            Classification.INTENTIONAL_NON_CONTEXT,
        )
    raw_path = _path_argument(context.arguments)
    if not raw_path:
        return None
    repository = context.repository
    if repository.directory(raw_path) is not None:
        return RuleOutcome.no_credit(
            "structured read names a directory",
            Classification.DISCOVERY_ONLY,
        )
    path = repository.file(raw_path)
    if path is None:
        # A path outside the repository roots earns no request credit, but
        # the read's output can still validate as receipts.
        return None
    if path in context.mutated_files:
        # Declared lines name the edited file, not the base revision.
        ranges = _receipt_ranges(context, (path,)).get(path, [])
        return RuleOutcome.credit(
            RangeSet.step({path: ranges}),
            "structured read of a file changed earlier in the trajectory; "
            "spans only from validated receipts",
        )
    ranges, ignored = _declared_ranges(context, path, context.arguments)
    reason = "structured ATIF file read"
    if ignored:
        reason += f"; ignored {'; '.join(ignored)}"
    return RuleOutcome.credit(RangeSet.step({path: ranges}), reason)


def _multi_read_values(arguments: dict[str, Any]) -> list[Any] | None:
    for key in _PATH_LIST_KEYS:
        value = arguments.get(key)
        if isinstance(value, list):
            return value
    return None


def _multi_read(context: CallContext) -> RuleOutcome | None:
    values = _multi_read_values(context.arguments)
    if values is None:
        return None
    repository = context.repository
    ranges = RangeSet()
    files: set[str] = set()
    mutated: list[str] = []
    ignored = 0
    for value in values:
        item = value if isinstance(value, dict) else {"path": value}
        raw_path = _path_argument(item)
        if not raw_path:
            ignored += 1
            continue
        path = repository.file(raw_path)
        if path is None:
            continue
        files.add(path)
        if path in context.mutated_files:
            mutated.append(path)
            continue
        item_ranges, item_ignored = _declared_ranges(context, path, item)
        ignored += bool(item_ignored)
        ranges.add({path: item_ranges})
    if mutated:
        ranges.add(_receipt_ranges(context, tuple(mutated)))
    step = ranges.as_step()
    step["files"] = sorted(files)
    if not files:
        return RuleOutcome.no_credit(
            "multi-file read names no file in the pinned checkout"
        )
    reason = "structured ATIF multi-file read"
    if mutated:
        reason += f"; spans of {len(mutated)} changed file(s) from validated receipts"
    if ignored:
        reason += f"; ignored malformed or past-end ranges of {ignored} item(s)"
    return RuleOutcome.credit(step, reason)


def _candidate_search_paths(arguments: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (*_PATH_KEYS, "include", "target"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)
    for key in _PATH_LIST_KEYS:
        value = arguments.get(key)
        if isinstance(value, list):
            values.extend(item for item in value if isinstance(item, str))
    return values


def _observation_hints(context: CallContext) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the files and directories a structured call's arguments name."""
    repository = context.repository
    candidates = _candidate_search_paths(context.arguments)
    files = tuple(
        dict.fromkeys(
            path
            for candidate in candidates
            for path in repository.candidate_files(candidate)
        )
    )
    directories = tuple(
        dict.fromkeys(
            directory.relative_to(repository.root).as_posix()
            for candidate in candidates
            if (directory := repository.directory(candidate)) is not None
            and directory != repository.root
        )
    )
    return files, directories


def _outcome_from_claim(claim: Claim) -> RuleOutcome:
    if claim.classification is Classification.PROJECTED and claim.ranges:
        return RuleOutcome.credit(RangeSet.step(claim.ranges), claim.reason)
    return RuleOutcome.no_credit(claim.reason, claim.classification)


def _undecided_observation_outcome(
    context: CallContext,
    claim: Claim,
) -> RuleOutcome | None:
    """Classify an examined observation that yielded no credit.

    Search credit is receipts-only, so a search whose output shows no source
    contents (counts, file lists, "no matches") is discovery whatever its
    structured arguments targeted. Any other known tool with examined,
    sourceless output is a decided outcome, not a mapping gap: `unmapped` is
    reserved for unknown tools and unexaminable calls so it stays a true
    false-negative surface.
    """
    if context.family is ToolFamily.SEARCH:
        return RuleOutcome.no_credit(
            "search output exposes no source contents; search credit is receipts-only",
            Classification.DISCOVERY_ONLY,
        )
    if context.family is not ToolFamily.UNKNOWN:
        return _outcome_from_claim(claim)
    return None


def _observation_claim(context: CallContext, content: str) -> Claim:
    if context.family is ToolFamily.SHELL:
        return shell_claim(context.repository, context.arguments, content)
    files, directories = _observation_hints(context)
    return ObservationAttributor(
        context.repository,
        cwd=context.repository.root,
        path_hints=files,
        directory_hints=directories,
    ).project(content)


def _observation(context: CallContext) -> RuleOutcome | None:
    observation = context.observation
    if observation is None or not observation.content.strip():
        if observation is not None and observation.error is not None:
            return RuleOutcome.no_credit(
                f"tool failed without returning source: {observation.error}",
                Classification.TOOL_ERROR,
            )
        return None
    claim = _observation_claim(context, observation.content)
    if claim.classification is Classification.PROJECTED:
        # Validated receipts prove themselves, even from a failed call.
        return _outcome_from_claim(claim)
    if observation.error is not None:
        return RuleOutcome.no_credit(
            "tool reported failure and its output has no validated source: "
            f"{observation.error}",
            Classification.TOOL_ERROR,
        )
    if claim.classification is Classification.DISCOVERY_ONLY:
        return _outcome_from_claim(claim)
    return _undecided_observation_outcome(context, claim)


def _common(context: CallContext) -> RuleOutcome:  # noqa: PLR0911 - one per step.
    """Apply the common steps of the rule in order; the first that decides wins."""
    family = context.family
    if family in _STATIC_OUTCOMES:
        reason, classification = _STATIC_OUTCOMES[family]
        return RuleOutcome.no_credit(reason, classification).decided_by("common.static")
    if family in _READ_FAMILIES and (outcome := _tool_error(context)):
        return outcome.decided_by("common.tool_error")
    if family is ToolFamily.READ and (outcome := _read(context)):
        return outcome.decided_by("common.read")
    if family is ToolFamily.MULTI_READ and (outcome := _multi_read(context)):
        return outcome.decided_by("common.multi_read")
    if family in _OBSERVED_FAMILIES and (outcome := _observation(context)):
        return outcome.decided_by("common.observation")
    if family is not ToolFamily.UNKNOWN:
        # A known tool whose call shows no output put no context in front of the
        # agent; `unmapped` stays reserved for unknown tools.
        return RuleOutcome.no_credit(
            "call has no recorded observation"
            if context.observation is None
            else "call returned no output",
            Classification.NON_BASE_CONTEXT,
        ).decided_by("common.known_no_credit")
    return RuleOutcome(
        ResultStatus.NO_MATCH,
        Classification.UNMAPPED,
        f"no extraction heuristic matched tool {context.raw_tool!r}",
        rule_id="registry.unmapped",
    )


def attribute(context: CallContext) -> RuleOutcome:
    """Decide the credit of one examined call (ATTRIBUTION.md)."""
    if context.family is ToolFamily.BACKGROUND:
        origin = context.background_origin
        if origin is None:
            # Exact source evidence can still recover output when an agent
            # omitted the background identifier.
            return _common(replace(context, family=ToolFamily.UNKNOWN))
        if origin.credited:
            return RuleOutcome(
                ResultStatus.NO_CREDIT,
                Classification.INTENTIONAL_NON_CONTEXT,
                "background command retrieval was already credited when launched",
                rule_id="common.background.deduplicate",
            )
        return _common(
            replace(context, arguments=origin.arguments, family=ToolFamily.SHELL)
        )
    if context.family is ToolFamily.OFFLOADED and context.offloaded_source_credited:
        return RuleOutcome(
            ResultStatus.NO_CREDIT,
            Classification.INTENTIONAL_NON_CONTEXT,
            "offloaded content is already represented by its source call",
            rule_id="common.offloaded.deduplicate",
        )
    return _common(context)


def context_for_call(  # noqa: PLR0913 - one argument per decoded input.
    *,
    raw_tool: str,
    arguments: dict[str, Any],
    observation: Observation | None,
    repository: SourceRepository,
    mutated_files: frozenset[str] = frozenset(),
    background_origin: BackgroundShell | None = None,
    offloaded_source_credited: bool = False,
) -> CallContext:
    """Build the normalized context that `attribute` decides."""
    normalized = canonical_tool_name(raw_tool)
    return CallContext(
        raw_tool=raw_tool,
        tool=normalized,
        family=tool_family(normalized),
        arguments=arguments,
        observation=observation,
        repository=repository,
        mutated_files=mutated_files,
        background_origin=background_origin,
        offloaded_source_credited=offloaded_source_credited,
    )


def mutated_file(context: CallContext) -> str | None:
    """Return the base checkout file a successful structured mutation changes."""
    observation = context.observation
    if observation is not None and observation.error is not None:
        return None
    is_editor_mutation = (
        context.family is ToolFamily.READ
        and _editor_command(context.arguments) not in _VIEW_COMMANDS
    )
    if context.family is not ToolFamily.MUTATION and not is_editor_mutation:
        return None
    raw_path = _path_argument(context.arguments)
    return context.repository.file(raw_path) if raw_path else None


__all__ = [
    "ATTRIBUTION_VERSION",
    "COPIED_CONTEXT",
    "BackgroundShell",
    "CallContext",
    "ResultStatus",
    "RuleOutcome",
    "ToolFamily",
    "attribute",
    "contained_failure",
    "context_for_call",
    "mutated_file",
    "path_key",
    "tool_family",
    "unpaired_results",
]
