"""Checkout-validated receipts: path resolution, diffs, terminal output, shell hints."""

from __future__ import annotations

import posixpath
import re
import shlex
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .types import Claim, LineRanges, RangeSet

_PATH_LINE = re.compile(r"^(.+?):(\d+):(.*)$")
_PATH_CONTEXT_LINE = re.compile(r"^(.+?)-(\d+)-(.*)$")

# A run of unnumbered output lines credited to a file the call did not name
# needs this many non-blank lines; a run in a named file needs RUN_MINIMUM.
UNHINTED_RUN_MINIMUM = 3
RUN_MINIMUM = 2

# A checkout-unique run: observed first and last index, file, source start and end.
Run = tuple[int, int, str, int, int]


def split_lines(text: str) -> list[str]:
    """Split text into lines the way ContextBench numbers them.

    Lines end at `\\n` only, as in ContextBench's byte-offset line mapping, and
    one trailing `\\r` belongs to the line ending. Characters that
    `str.splitlines` also breaks on (form feed, U+2028, ...) stay in the line.
    """
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return [line.removesuffix("\r") for line in lines]


def _is_blank(text: str) -> bool:
    return not text.strip()


def _matches(displayed: str, source: str) -> bool:
    """Whether non-blank displayed text is a source line, tabs expanded or not."""
    return not _is_blank(displayed) and (
        displayed == source or displayed == source.expandtabs(8)
    )


def _lines_agree(observed: str, source: str) -> bool:
    """Whether an output line continues a run: it matches, or both are blank."""
    return (_is_blank(observed) and _is_blank(source)) or _matches(observed, source)


def _root(value: str) -> str:
    normalized = posixpath.normpath(value)
    if (
        not normalized.startswith("/")
        or normalized.startswith("//")
        or normalized == "/"
    ):
        raise ValueError(f"repository root must be an absolute path below /: {value!r}")
    return normalized


class SourceRepository:
    """Resolve checkout paths and validate observed source against that checkout.

    `roots` are the absolute paths at which the agent's environment mounts the
    repository, such as `/workspace` and the task's native repository path. A
    path under a root resolves exactly, relative to the longest such root; a
    relative path resolves against the working directory. Any other absolute
    path names nothing in the checkout, although it may still hint at the file
    an output shows (`candidate_files`).
    """

    def __init__(self, root: Path | str, *, roots: Iterable[str] = ()) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"repository does not exist: {self.root}")
        self.roots = tuple(sorted({_root(value) for value in roots}, key=len)[::-1])
        self._source_cache: dict[str, list[str]] = {}
        self._text_paths: tuple[str, ...] | None = None
        # Text paths by file name, and the name of every file in the checkout.
        self._text_paths_by_name: dict[str, list[str]] = {}
        self._file_names: frozenset[str] = frozenset()
        self._line_index: dict[str, list[tuple[str, int]]] | None = None
        # The checkout does not change while it is scored, so the files a
        # hint names are cached. Search output names the same paths on many
        # lines, and each resolution costs several system calls. Only hints
        # whose last component names a checkout file are cached, so the cache
        # grows with the paths an output names, not with its length.
        self._candidates: dict[tuple[str, Path | None], tuple[str, ...]] = {}

    @staticmethod
    def _clean_path(raw_path: str) -> str:
        value = raw_path.strip().strip("'\"").replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        return value

    def _under_root(self, value: str) -> str | None:
        """Return the path of `value` relative to the longest root it is under."""
        for root in self.roots:
            if value == root:
                return ""
            if value.startswith(f"{root}/"):
                return value[len(root) + 1 :]
        return None

    def _resolve(self, raw_path: str, cwd: Path | None) -> tuple[Path | None, str]:
        value = self._clean_path(raw_path)
        if (
            not value
            or "\0" in value
            or "\n" in value
            or any(len(part) > 255 for part in value.split("/"))
        ):
            return None, value
        relative = self._under_root(value)
        if relative is not None:
            parts = [part for part in relative.split("/") if part]
            if any(part in {".", ".."} for part in parts):
                return None, value
            candidate = self.root.joinpath(*parts)
        elif value.startswith("/"):
            return None, value
        else:
            candidate = (cwd or self.root) / value
        # Path text is agent-authored: resolution and stat calls on it can
        # exceed OS path limits and must never raise.
        try:
            resolved = candidate.resolve()
        except OSError:
            return None, value
        return (resolved if resolved.is_relative_to(self.root) else None), value

    def file(self, raw_path: str, *, cwd: Path | None = None) -> str | None:
        """Resolve a path to an existing checkout file, exactly."""
        resolved, value = self._resolve(raw_path, cwd)
        if resolved is None or value == "-":
            return None
        try:
            if not resolved.is_file():
                return None
        except OSError:
            return None
        return resolved.relative_to(self.root).as_posix()

    def directory(self, raw_path: str, *, cwd: Path | None = None) -> Path | None:
        """Resolve a path to an existing checkout directory, exactly."""
        resolved, _ = self._resolve(raw_path, cwd)
        try:
            return resolved if resolved is not None and resolved.is_dir() else None
        except OSError:
            return None

    def lines(self, relative_path: str) -> list[str]:
        if relative_path not in self._source_cache:
            self._source_cache[relative_path] = split_lines(
                (self.root / relative_path)
                .read_bytes()
                .decode("utf-8", errors="replace")
            )
        return self._source_cache[relative_path]

    def line_count(self, relative_path: str) -> int:
        return len(self.lines(relative_path))

    def text_paths(self) -> tuple[str, ...]:
        """Return readable checkout files that can contribute source evidence."""
        if self._text_paths is None:
            paths: list[str] = []
            names: set[str] = set()
            for path in self.root.rglob("*"):
                if not path.is_file():
                    continue
                names.add(path.name)
                if ".git" in path.relative_to(self.root).parts:
                    continue
                if not path.resolve().is_relative_to(self.root):
                    continue
                try:
                    with path.open("rb") as source_file:
                        if b"\0" in source_file.read(8192):
                            continue
                except OSError:
                    continue
                paths.append(path.relative_to(self.root).as_posix())
            self._text_paths = tuple(sorted(paths))
            for relative in self._text_paths:
                self._text_paths_by_name.setdefault(
                    PurePosixPath(relative).name, []
                ).append(relative)
            self._file_names = frozenset(names)
        return self._text_paths

    def _names_a_file(self, value: str) -> bool:
        """Return whether a path's last component is the name of a checkout file.

        Every file a hint can resolve to has the name of the hint's last
        component, so other hints are rejected without touching the file system.
        """
        self.text_paths()
        return PurePosixPath(self._clean_path(value)).name in self._file_names

    @staticmethod
    def _hint_value(raw_path: str) -> str:
        """Strip shell punctuation, `--flag=`, `:line` and `revision:` from a hint."""
        value = raw_path.strip().strip("'\"`")
        if "\0" in value or "\n" in value or len(value) > 1024:
            return ""
        if "=" in value and value.startswith("-"):
            value = value.split("=", 1)[1]
        value = value.rstrip(",;)]}")
        value = re.sub(r":\d+(?::\d+)?$", "", value)
        if ":" in value and not value.startswith("/"):
            revision, candidate = value.split(":", 1)
            if revision and "/" in candidate:
                value = candidate
        if value.startswith(("http://", "https://")):
            return ""
        return value

    def _glob_files(self, pattern: str, cwd: Path | None) -> tuple[str, ...]:
        # The pattern is agent-authored text: pathlib rejects some shapes
        # outright (for example `**` fused to a component), and no shell
        # token may ever abort attribution.
        try:
            globbed = list((cwd or self.root).resolve().glob(pattern))
        except (ValueError, OSError):
            return ()
        return tuple(
            sorted(
                {
                    path.resolve().relative_to(self.root).as_posix()
                    for path in globbed
                    if path.is_file() and path.resolve().is_relative_to(self.root)
                }
            )
        )

    def _stripped(self, value: str) -> tuple[str, ...]:
        """Strip leading components until the rest names a file, as ContextBench does."""
        parts = [part for part in value.split("/") if part]
        for index in range(len(parts)):
            if resolved := self.file("/".join(parts[index:])):
                return (resolved,)
        return ()

    def candidate_files(
        self,
        raw_path: str,
        *,
        cwd: Path | None = None,
    ) -> tuple[str, ...]:
        """Resolve a receipt hint: a path that may name the file an output shows.

        A hint never earns credit; it only steers receipt validation, so it
        resolves more loosely than a structured read. A path under a root
        resolves exactly. Any other absolute path loses leading components
        until it names a file, and a relative path may match a glob or one
        checkout path by suffix.
        """
        value = self._hint_value(raw_path)
        if not value:
            return ()
        is_pattern = not value.startswith("/") and any(
            character in value for character in "*?["
        )
        if is_pattern:
            return self._candidate_files(value, is_pattern, cwd)
        if not self._names_a_file(value):
            return ()
        key = (value, cwd)
        if key not in self._candidates:
            self._candidates[key] = self._candidate_files(value, is_pattern, cwd)
        return self._candidates[key]

    def _candidate_files(
        self, value: str, is_pattern: bool, cwd: Path | None
    ) -> tuple[str, ...]:
        if resolved := self.file(value, cwd=cwd):
            return (resolved,)
        cleaned = self._clean_path(value)
        if cleaned.startswith("/"):
            return (
                () if self._under_root(cleaned) is not None else self._stripped(cleaned)
            )
        if is_pattern and (globbed := self._glob_files(value, cwd)):
            return globbed
        suffix_matches = [
            path
            for path in self._text_paths_by_name.get(PurePosixPath(cleaned).name, ())
            if path == cleaned or path.endswith(f"/{cleaned}")
        ]
        return tuple(suffix_matches) if len(suffix_matches) == 1 else ()

    def line_locations(self, content: str) -> list[tuple[str, int]]:
        """Locate a non-blank displayed source line in every checkout file."""
        if _is_blank(content):
            return []
        if self._line_index is None:
            index: dict[str, list[tuple[str, int]]] = {}
            for path in self.text_paths():
                for number, source in enumerate(self.lines(path), start=1):
                    if _is_blank(source):
                        continue
                    index.setdefault(source, []).append((path, number))
                    expanded = source.expandtabs(8)
                    if expanded != source:
                        index.setdefault(expanded, []).append((path, number))
            self._line_index = index
        return list(self._line_index.get(content, ()))

    def unique_runs(
        self,
        observed: list[str],
        minimum: Callable[[str], int],
    ) -> list[Run]:
        """Find checkout-unique runs of exact source lines in unnumbered output.

        A run starts and ends at a non-blank line, and a blank line inside it
        matches a blank source line. It needs `minimum(file)` non-blank lines,
        and its longest extension must be at exactly one checkout location.
        The selected runs do not overlap.
        """
        candidates: list[Run] = []
        for observed_start, first in enumerate(observed):
            extended: list[tuple[str, int, int]] = []
            for path, source_start in self.line_locations(first):
                source = self.lines(path)
                length = trimmed = nonblank = 0
                while (
                    observed_start + length < len(observed)
                    and source_start - 1 + length < len(source)
                    and _lines_agree(
                        observed[observed_start + length],
                        source[source_start - 1 + length],
                    )
                ):
                    length += 1
                    if not _is_blank(observed[observed_start + length - 1]):
                        nonblank += 1
                        trimmed = length
                if nonblank >= minimum(path):
                    extended.append((path, source_start, trimmed))
            if not extended:
                continue
            longest = max(length for _, _, length in extended)
            locations = {
                (path, source_start)
                for path, source_start, length in extended
                if length == longest
            }
            if len(locations) != 1:
                continue
            path, source_start = locations.pop()
            candidates.append(
                (
                    observed_start,
                    observed_start + longest - 1,
                    path,
                    source_start,
                    source_start + longest - 1,
                )
            )

        selected: list[Run] = []
        occupied: set[int] = set()
        for match in sorted(
            candidates,
            key=lambda item: (-(item[1] - item[0]), item[0]),
        ):
            positions = set(range(match[0], match[1] + 1))
            if positions.isdisjoint(occupied):
                selected.append(match)
                occupied.update(positions)
        return sorted(selected)


@dataclass
class _Evidence:
    """The source lines one call's receipts showed, per checkout file."""

    repository: SourceRepository
    # Validated non-blank lines.
    lines: dict[str, set[int]] = field(default_factory=dict)
    # Blank lines displayed at blank source lines: never evidence, but they
    # join the validated lines around them into one span.
    blanks: dict[str, set[int]] = field(default_factory=dict)

    def observe(self, path: str, number: int, displayed: tuple[str, ...]) -> bool:
        """Record text displayed as line `number` of `path`; return whether it fits.

        `displayed` holds the readings of one output line, such as with and
        without a separator space.
        """
        source = self.repository.lines(path)
        if not 1 <= number <= len(source):
            return False
        expected = source[number - 1]
        if all(_is_blank(text) for text in displayed):
            if _is_blank(expected):
                self.blanks.setdefault(path, set()).add(number)
                return True
            return False
        if any(_matches(text, expected) for text in displayed):
            self.lines.setdefault(path, set()).add(number)
            return True
        return False

    def run(self, path: str, start: int, end: int) -> None:
        source = self.repository.lines(path)
        for number in range(start, end + 1):
            target = self.blanks if _is_blank(source[number - 1]) else self.lines
            target.setdefault(path, set()).add(number)

    def _bridged(self, path: str) -> set[int]:
        validated = self.lines[path]
        covered = set(validated)
        blanks = sorted(self.blanks.get(path, ()))
        start = 0
        while start < len(blanks):
            end = start
            while end + 1 < len(blanks) and blanks[end + 1] == blanks[end] + 1:
                end += 1
            if blanks[start] - 1 in validated and blanks[end] + 1 in validated:
                covered.update(blanks[start : end + 1])
            start = end + 1
        return covered

    def ranges(self) -> LineRanges:
        """Return the credited ranges; a whole-file view is the file without spans.

        A view is whole when the call showed every non-blank line of the file.
        """
        ranges: LineRanges = {}
        for path in sorted(self.lines):
            covered = self._bridged(path)
            nonblank = {
                number
                for number, source in enumerate(self.repository.lines(path), start=1)
                if not _is_blank(source)
            }
            ranges[path] = (
                []
                if nonblank <= covered
                else RangeSet.merge_intervals([(number, number) for number in covered])
            )
        return ranges


_UNIFIED_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")
_NORMAL_CHANGE = re.compile(r"^(\d+)(?:,(\d+))?([acd])(\d+)(?:,(\d+))?$")
_GIT_EXTENDED_HEADERS = (
    "index ",
    "old mode ",
    "new mode ",
    "deleted file mode ",
    "new file mode ",
    "similarity index ",
    "dissimilarity index ",
    "rename from ",
    "rename to ",
    "copy from ",
    "copy to ",
    "Binary files ",
)
_NO_NEWLINE = "\\ No newline at end of file"


@dataclass
class _NormalRecord:
    """One normal-diff change (`3,4c3`) and the lines it still expects."""

    operation: str
    old_line: int
    new_line: int
    old_left: int
    new_left: int
    separated: bool = False


@dataclass
class _DiffReader:
    """Consume the diff-shaped lines of an output and validate them.

    A unified hunk is read by its header counts, so an empty line inside it is
    a context line whose leading space was stripped. A normal-diff record is
    read by its change ranges, against the command's first and second path
    hint. A line that does not fit closes the hunk or record and is left for
    the other receipts. Diff-shaped lines are consumed whether or not they
    validate.
    """

    repository: SourceRepository
    cwd: Path
    paths: tuple[str, ...]
    evidence: _Evidence
    consumed: set[int] = field(default_factory=set)
    saw_hunk: bool = False
    old_path: str | None = None
    new_path: str | None = None
    old_line: int = 0
    new_line: int = 0
    old_left: int = 0
    new_left: int = 0
    in_git_header: bool = False
    expects_new_header: bool = False
    after_body: bool = False
    record: _NormalRecord | None = None

    def read(self, lines: tuple[str, ...]) -> set[int]:
        for index, line in enumerate(lines):
            if self._hunk_line(line) or self._normal_line(line):
                self.consumed.add(index)
                self.after_body = True
                continue
            after_body, self.after_body = self.after_body, False
            if self._structure_line(line, lines[index + 1 : index + 2], after_body):
                self.consumed.add(index)
        return self.consumed

    def _observe(self, path: str | None, number: int, content: str) -> None:
        if path is not None:
            self.evidence.observe(path, number, (content,))

    def _hunk_line(self, line: str) -> bool:
        if self.old_left <= 0 and self.new_left <= 0:
            return False
        if line.startswith(_NO_NEWLINE):
            return True
        prefix, content = (line[0], line[1:]) if line else (" ", "")
        if prefix == " " and self.old_left > 0 and self.new_left > 0:
            self._observe(self.old_path, self.old_line, content)
            if (self.new_path, self.new_line) != (self.old_path, self.old_line):
                self._observe(self.new_path, self.new_line, content)
            self.old_line, self.new_line = self.old_line + 1, self.new_line + 1
            self.old_left, self.new_left = self.old_left - 1, self.new_left - 1
        elif prefix == "-" and self.old_left > 0:
            self._observe(self.old_path, self.old_line, content)
            self.old_line, self.old_left = self.old_line + 1, self.old_left - 1
        elif prefix == "+" and self.new_left > 0:
            self._observe(self.new_path, self.new_line, content)
            self.new_line, self.new_left = self.new_line + 1, self.new_left - 1
        else:
            self.old_left = self.new_left = 0
            return False
        self.saw_hunk = True
        return True

    def _normal_line(self, line: str) -> bool:
        record = self.record
        if record is None:
            return False
        if line.startswith(_NO_NEWLINE):
            return True
        if (line == "<" or line.startswith("< ")) and (
            record.old_left > 0 and not record.separated
        ):
            self._observe(
                self.paths[0] if self.paths else None, record.old_line, line[2:]
            )
            record.old_line, record.old_left = record.old_line + 1, record.old_left - 1
        elif (
            line == "---"
            and record.operation == "c"
            and record.old_left == 0
            and not record.separated
        ):
            record.separated = True
        elif (line == ">" or line.startswith("> ")) and (
            record.new_left > 0 and (record.operation != "c" or record.separated)
        ):
            new_path = self.paths[1] if len(self.paths) > 1 else None
            self._observe(new_path, record.new_line, line[2:])
            record.new_line, record.new_left = record.new_line + 1, record.new_left - 1
        else:
            self.record = None
            return False
        self.saw_hunk = True
        return True

    def _structure_line(
        self,
        line: str,
        following: tuple[str, ...],
        after_body: bool,
    ) -> bool:
        """Consume a diff header or record start; return whether it was one."""
        in_git_header, self.in_git_header = self.in_git_header, False
        expects_new_header, self.expects_new_header = self.expects_new_header, False
        if line.startswith("diff --git "):
            self.old_path, self.new_path = self._git_header_paths(line)
            self.in_git_header = True
        elif in_git_header and line.startswith(_GIT_EXTENDED_HEADERS):
            self.in_git_header = True
        elif line.startswith("--- ") and any(
            next_line.startswith("+++ ") for next_line in following
        ):
            self.old_path = self._path(line[4:])
            self.expects_new_header = True
        elif line.startswith("+++ ") and expects_new_header:
            self.new_path = self._path(line[4:])
        elif hunk := _UNIFIED_HUNK.fullmatch(line):
            self.old_line, self.new_line = int(hunk.group(1)), int(hunk.group(3))
            self.old_left = int(hunk.group(2) or 1)
            self.new_left = int(hunk.group(4) or 1)
            self.saw_hunk = True
        elif line.startswith(_NO_NEWLINE) and after_body:
            pass
        elif change := _NORMAL_CHANGE.fullmatch(line):
            self.record = self._normal_record(change)
        else:
            return False
        return True

    @staticmethod
    def _normal_record(change: re.Match[str]) -> _NormalRecord:
        old_start, new_start = int(change.group(1)), int(change.group(4))
        old_end = int(change.group(2) or old_start)
        new_end = int(change.group(5) or new_start)
        operation = change.group(3)
        return _NormalRecord(
            operation,
            old_start,
            new_start,
            0 if operation == "a" else max(old_end - old_start + 1, 0),
            0 if operation == "d" else max(new_end - new_start + 1, 0),
        )

    def _path(self, raw_path: str) -> str | None:
        value = raw_path.split("\t", 1)[0].strip()
        if value == "/dev/null":
            return None
        if value.startswith(("a/", "b/")):
            value = value[2:]
        return self.repository.file(value, cwd=self.cwd)

    def _git_header_paths(self, line: str) -> tuple[str | None, str | None]:
        try:
            header = shlex.split(line)
        except ValueError:
            return None, None
        if len(header) != 4:
            return None, None
        return self._path(header[2]), self._path(header[3])


_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_NUMBERED_LINES = (
    re.compile(r"^\s*(\d+):(.*)$"),
    re.compile(r"^\s*(\d+)\t(.*)$"),
    re.compile(r"^\s*(\d+) {2}(.*)$"),
    re.compile(r"^\s*(\d+)\|\s?(.*)$"),
)
_GREP_CONTEXT_LINE = re.compile(r"^\s*(\d+)-(.*)$")
_NESTED_NUMBERED_LINE = re.compile(r"^\s*\d+[:-](\d+)[:-](.*)$")
# A Python traceback frame; the line after it repeats source from that frame.
_TRACEBACK_FRAME = re.compile(r'\s*File "[^"]+", line \d+')
# pytest marks the failing source line with `>` and the error with `E`, each
# in column 0 followed by three spaces.
_PYTEST_MARKERS = (">   ", "E   ")
# A shell prompt line (`user@host:/dir$ command`); group 1 is the command.
TERMINAL_PROMPT = re.compile(r"^.*?[@:].*?[#$]\s+(.*)$")


@dataclass(frozen=True)
class _ObservedText:
    lines: tuple[str, ...]
    ignored: frozenset[int]

    def available(self, consumed: set[int]) -> list[tuple[int, str]]:
        return [
            (index, line)
            for index, line in enumerate(self.lines)
            if index not in self.ignored and index not in consumed and line.strip()
        ]


@dataclass(frozen=True)
class _Numbered:
    index: int
    number: int
    displayed: tuple[str, ...]
    path: str | None

    @property
    def blank(self) -> bool:
        return all(_is_blank(text) for text in self.displayed)


class ObservationAttributor:
    """Decode source-shaped output and validate it against a checkout."""

    def __init__(
        self,
        repository: SourceRepository,
        *,
        cwd: Path,
        path_hints: tuple[str, ...] = (),
        directory_hints: tuple[str, ...] = (),
        authored_text: frozenset[str] = frozenset(),
    ) -> None:
        self.repository = repository
        self.cwd = cwd
        self.path_hints = tuple(
            dict.fromkeys(
                resolved
                for path in path_hints
                if (resolved := repository.file(path)) is not None
            )
        )
        self.directory_hints = tuple(
            dict.fromkeys(path for path in directory_hints if path not in {"", "."})
        )
        self.authored_text = frozenset(
            text.strip() for text in authored_text if text.strip()
        )

    def _hinted(self, path: str) -> bool:
        return path in self.path_hints or any(
            path.startswith(f"{directory}/") for directory in self.directory_hints
        )

    def _run_minimum(self, path: str) -> int:
        return RUN_MINIMUM if self._hinted(path) else UNHINTED_RUN_MINIMUM

    def project(self, observation: str) -> Claim:
        text = self._normalize(observation)
        if not text.available(set()):
            return Claim.no_base_context(
                "observation contains no attributable checkout text"
            )
        evidence = _Evidence(self.repository)
        diff = _DiffReader(self.repository, self.cwd, self.path_hints, evidence)
        consumed = diff.read(text.lines)
        self._path_numbered(text, evidence, consumed)
        self._numbered(text, evidence, consumed)
        self._path_prefixed_runs(text, evidence, consumed)
        if (
            not evidence.lines
            and not diff.saw_hunk
            and self._is_path_list(text, consumed)
        ):
            return Claim.discovery(
                "observation lists checkout paths without source content"
            )
        self._contiguous_lines(text, evidence, consumed)

        ranges = evidence.ranges()
        if ranges:
            reason = "validated base-checkout source in the observation"
            if whole := [path for path, spans in ranges.items() if not spans]:
                reason += (
                    f"; whole-file view of {', '.join(whole)} credits the file only"
                )
            if unresolved := len(text.available(consumed)):
                reason += f"; ignored {unresolved} unattributed line(s)"
            return Claim.verified(ranges, reason)
        if diff.saw_hunk:
            return Claim.no_base_context(
                "observed diff contains no base-revision source at its coordinates"
            )
        return Claim.no_base_context(
            "observation contains no source matching the base checkout"
        )

    def _normalize(self, observation: str) -> _ObservedText:
        lines: list[str] = []
        ignored: set[int] = set()
        traceback_source = False
        for raw_line in split_lines(observation):
            line = _ANSI.sub("", raw_line)
            for prefix in ("[stdout]", "[stderr]"):
                if line.startswith(prefix):
                    line = line[len(prefix) :]
                    line = line.removeprefix(" ")
            prompt = TERMINAL_PROMPT.fullmatch(line)
            authored = line.strip() in self.authored_text or (
                prompt is not None and prompt.group(1).strip() in self.authored_text
            )
            index = len(lines)
            lines.append(line)
            if authored or traceback_source or line.startswith(_PYTEST_MARKERS):
                ignored.add(index)
            traceback_source = _TRACEBACK_FRAME.match(line) is not None
        return _ObservedText(tuple(lines), frozenset(ignored))

    def _path_numbered(
        self,
        text: _ObservedText,
        evidence: _Evidence,
        consumed: set[int],
    ) -> None:
        for index, line in text.available(consumed):
            match = _PATH_LINE.fullmatch(line) or _PATH_CONTEXT_LINE.fullmatch(line)
            if match is None:
                continue
            paths = self.repository.candidate_files(match.group(1), cwd=self.cwd)
            if len(paths) != 1:
                continue
            content = match.group(3)
            if evidence.observe(
                paths[0], int(match.group(2)), (content, content.removeprefix(" "))
            ):
                consumed.add(index)

    def _shows(self, path: str, number: int, displayed: tuple[str, ...]) -> bool:
        source = self.repository.lines(path)
        return 1 <= number <= len(source) and any(
            _matches(text, source[number - 1]) for text in displayed
        )

    def _locate(self, number: int, displayed: tuple[str, ...]) -> str | None:
        """Return the one file whose line `number` is the displayed text."""
        if self.path_hints:
            locations = {
                path for path in self.path_hints if self._shows(path, number, displayed)
            }
        else:
            locations = {
                path
                for text in displayed
                for path, source_number in self.repository.line_locations(text)
                if source_number == number
            }
        return locations.pop() if len(locations) == 1 else None

    def _numbered_lines(
        self,
        text: _ObservedText,
        consumed: set[int],
    ) -> list[_Numbered]:
        # `grep -n -C` marks context lines `N-`; with one file named they are
        # read as numbered lines of that file.
        patterns = (
            (*_NUMBERED_LINES, _GREP_CONTEXT_LINE)
            if len(self.path_hints) == 1
            else _NUMBERED_LINES
        )
        numbered: list[_Numbered] = []
        for index, line in text.available(consumed):
            match = next(
                (
                    found
                    for pattern in patterns
                    if (found := pattern.fullmatch(line)) is not None
                ),
                None,
            )
            if match is None:
                continue
            number = int(match.group(1))
            displayed = (match.group(2), match.group(2).removeprefix(" "))
            path = self._locate(number, displayed)
            nested = _NESTED_NUMBERED_LINE.fullmatch(line)
            if path is None and self.path_hints and nested is not None:
                # `grep -n ... FILE | grep -n ...` prefixes the first grep's
                # output with its own line number; the inner number is the
                # file's, and it counts when it validates in one named file.
                inner = int(nested.group(1))
                inner_displayed = (nested.group(2), nested.group(2).removeprefix(" "))
                if (inner_path := self._locate(inner, inner_displayed)) is not None:
                    number, displayed, path = inner, inner_displayed, inner_path
            numbered.append(_Numbered(index, number, displayed, path))
        return numbered

    def _numbered(
        self,
        text: _ObservedText,
        evidence: _Evidence,
        consumed: set[int],
    ) -> None:
        """Credit line-numbered output.

        With a path hint, each numbered line counts on its own. Without one, a
        line counts only among at least two consecutive output lines that
        locate in the same file; numbered blank lines may sit between them.
        """
        numbered = self._numbered_lines(text, consumed)
        if self.path_hints:
            for line in numbered:
                if line.blank:
                    for path in self.path_hints:
                        evidence.observe(path, line.number, line.displayed)
                elif line.path is not None:
                    evidence.observe(line.path, line.number, line.displayed)
                    consumed.add(line.index)
            return
        group: list[_Numbered] = []
        for line in [*numbered, None]:
            group_path = next((item.path for item in group if not item.blank), None)
            continues = (
                line is not None
                and group
                and line.index == group[-1].index + 1
                and (line.blank or line.path == group_path or group_path is None)
            )
            if not continues:
                self._numbered_group(group, evidence, consumed)
                group = []
            if line is not None and (line.blank or line.path is not None):
                group.append(line)

    @staticmethod
    def _numbered_group(
        group: list[_Numbered],
        evidence: _Evidence,
        consumed: set[int],
    ) -> None:
        located = [line for line in group if not line.blank]
        if len(located) < 2:
            return
        path = located[0].path
        if path is None:
            return
        for line in group:
            evidence.observe(path, line.number, line.displayed)
            if not line.blank:
                consumed.add(line.index)

    def _prefixed_lines(
        self,
        text: _ObservedText,
        consumed: set[int],
    ) -> list[tuple[int, str, str]]:
        """Return the lines that name exactly one file before a `:` or `-`."""
        prefixed: list[tuple[int, str, str]] = []
        for index, line in text.available(consumed):
            candidates: set[tuple[str, str]] = set()
            for offset, character in enumerate(line):
                if character not in {":", "-"}:
                    continue
                paths = self.repository.candidate_files(line[:offset], cwd=self.cwd)
                if len(paths) == 1:
                    candidates.add((paths[0], line[offset + 1 :]))
            if len(candidates) == 1:
                prefixed.append((index, *candidates.pop()))
        return prefixed

    def _path_prefixed_runs(
        self,
        text: _ObservedText,
        evidence: _Evidence,
        consumed: set[int],
    ) -> None:
        prefixed = self._prefixed_lines(text, consumed)
        start = 0
        while start < len(prefixed):
            end = start + 1
            while (
                end < len(prefixed)
                and prefixed[end][0] == prefixed[end - 1][0] + 1
                and prefixed[end][1] == prefixed[start][1]
            ):
                end += 1
            run = prefixed[start:end]
            raw_contents = [item[2] for item in run]
            matches: list[Run] = []
            for contents in (
                raw_contents,
                [content.removeprefix(" ") for content in raw_contents],
            ):
                matches = self.repository.unique_runs(
                    contents, lambda _path: RUN_MINIMUM
                )
                if matches:
                    break
            if len(matches) == 1 and matches[0][2] == run[0][1]:
                first, last, path, source_start, source_end = matches[0]
                evidence.run(path, source_start, source_end)
                consumed.update(item[0] for item in run[first : last + 1])
            start = end

    def _is_path_list(self, text: _ObservedText, consumed: set[int]) -> bool:
        available = text.available(consumed)
        if not available:
            return False
        for _, line in available:
            value = line.strip()
            if self.repository.candidate_files(value, cwd=self.cwd):
                continue
            if self.repository.directory(value, cwd=self.cwd) is not None:
                continue
            return False
        return True

    def _contiguous_lines(
        self,
        text: _ObservedText,
        evidence: _Evidence,
        consumed: set[int],
    ) -> None:
        observed = [
            "\0" if index in text.ignored or index in consumed else line
            for index, line in enumerate(text.lines)
        ]
        for first, last, path, start, end in self.repository.unique_runs(
            observed, self._run_minimum
        ):
            evidence.run(path, start, end)
            consumed.update(range(first, last + 1))


def shell_claim(
    repository: SourceRepository, arguments: dict[str, Any], observation: str
) -> Claim:
    """Validate shell output, using the command text only as hints."""
    command = _command_text(arguments)
    tokens = _tokens(command)
    cwd = _working_directory(repository, arguments, tokens)
    paths = tuple(
        dict.fromkeys(
            path
            for token in tokens
            for path in repository.candidate_files(token, cwd=cwd)
        )
    )
    # The working directory, and a `cd` target, are not hints.
    directories = tuple(
        dict.fromkeys(
            directory.relative_to(repository.root).as_posix()
            for previous, token in zip(("", *tokens), tokens, strict=False)
            if previous != "cd"
            and (directory := repository.directory(token, cwd=cwd)) is not None
            and directory not in {repository.root, cwd}
        )
    )
    authored = frozenset(line.strip() for line in command.splitlines() if line.strip())
    return ObservationAttributor(
        repository,
        cwd=cwd,
        path_hints=paths,
        directory_hints=directories,
        authored_text=authored,
    ).project(observation)


def _command_text(arguments: dict[str, Any]) -> str:
    command_list = arguments.get("commands")
    listed = (
        [item for item in command_list if isinstance(item, str) and item.strip()]
        if isinstance(command_list, list)
        else []
    )
    value = next(
        (
            str(arguments[key])
            for key in ("command", "cmd", "keystrokes", "raw_action", "input")
            if arguments.get(key) is not None
        ),
        " ; ".join(listed),
    )
    return str(value).strip()


def _tokens(command: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(command, comments=False, posix=True))
    except ValueError:
        return tuple(command.split())


def _working_directory(
    repository: SourceRepository, arguments: dict[str, Any], tokens: tuple[str, ...]
) -> Path:
    raw_cwd = str(
        arguments.get("workdir")
        or arguments.get("cwd")
        or arguments.get("dir_path")
        or arguments.get("directory")
        or "."
    )
    cwd = repository.directory(raw_cwd) or repository.root
    for index, token in enumerate(tokens[:-1]):
        if token != "cd":
            continue
        changed = repository.directory(tokens[index + 1], cwd=cwd)
        if changed is not None:
            cwd = changed
    return cwd


__all__ = [
    "TERMINAL_PROMPT",
    "ObservationAttributor",
    "SourceRepository",
    "shell_claim",
    "split_lines",
]
