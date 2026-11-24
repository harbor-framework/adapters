"""Tool-output truncation, ported from Inspect (inspect-ai 0.3.285).

Inspect truncates every tool result before the model sees it
(`inspect_ai.model._call_tools.truncate_tool_output`, using
`inspect_ai._util.text.truncate_string_to_bytes`): outputs longer than
`max_tool_output` bytes (default 16 KiB; `--max-tool-output` overrides)
are middle-truncated and wrapped in a fixed notice. The parity agent
applies the same rule so long tool results (e.g. `read_all_tickets`)
look identical on both sides.
"""

from __future__ import annotations

from textwrap import dedent

DEFAULT_MAX_TOOL_OUTPUT = 16 * 1024  # Inspect's default


def _truncate_str(text: str, max_bytes: int) -> str:
    half = max_bytes // 2
    return text[:half] + text[-(max_bytes - half):]


def _truncate_bytes(data: bytes, max_bytes: int) -> str:
    half = max_bytes // 2
    start = data[:half].decode("utf-8", errors="ignore")
    end = data[-(max_bytes - half):].decode("utf-8", errors="ignore")
    return start + end


def truncate_string_to_bytes(text: str, max_bytes: int) -> str | None:
    """Middle-truncated text if longer than max_bytes, else None."""
    if not text or max_bytes <= 0:
        return None
    if text.isascii():
        return None if len(text) <= max_bytes else _truncate_str(text, max_bytes)
    if len(text) * 4 <= max_bytes:
        return None
    try:
        encoded = text.encode("utf-8", errors="replace")
    except Exception:  # Inspect: never fail, just skip truncation
        return None
    return None if len(encoded) <= max_bytes else _truncate_bytes(encoded, max_bytes)


def truncate_tool_output(tool_name: str, output: str, max_output: int) -> str:
    """Return the tool output exactly as Inspect would pass it to the model."""
    truncated = truncate_string_to_bytes(output, max_output)
    if truncated is None:
        return output
    return dedent("""
        The output of your call to {tool_name} was too long to be displayed.
        Here is a truncated version:
        <START_TOOL_OUTPUT>
        {truncated_output}
        <END_TOOL_OUTPUT>
        """).format(tool_name=tool_name, truncated_output=truncated)
