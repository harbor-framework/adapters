"""Convert Epoch AI's Chess Puzzles v2 benchmark into Harbor tasks.

Source data is ``puzzles.csv`` (100 rows: ``input`` = FEN, ``target`` = best move in UCI) from
the public ``epoch-research/chess-puzzles-mirror`` repository, pinned to one commit and
verified by SHA-256 so the generated tasks are reproducible.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.request import urlopen

UPSTREAM_REPO = "epoch-research/chess-puzzles-mirror"
UPSTREAM_COMMIT = "2c9416aac2a6b0731a3680eadfff3735fdaad396"
DATA_SHA256 = "e85df658a305c29f722fe0bc9f4de678ebeb5ce839b132c55210030ab7ff6fe8"
DATA_URL = (
    f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_COMMIT}"
    "/bench/task/chess_puzzles/puzzles.csv"
)
# Scoring semantics of upstream Chess Puzzles 2.0.1 (Inspect exact()). Upstream's changelog lists
# 2.1.0 (SAN also accepted) as "unreleased", and the pinned commit predates it.
SCORING_VERSION = "2.0.1"
EXPECTED_ROWS = 100

PACKAGE_DIR = Path(__file__).parent
TEMPLATE_DIR = PACKAGE_DIR / "task-template"

# QUESTION_TEMPLATE is verbatim from upstream bench/task/chess_puzzles/__init__.py.
# SUBMIT_DESCRIPTION is upstream's text minus its last sentence (see below).
QUESTION_TEMPLATE = (
    "Below is a FEN string representing the state of a chess game. Analyze the position and "
    "determine the best next move for the player whose turn it is.\n"
    "\n"
    "{prompt}"
)
SUBMIT_DESCRIPTION = (
    "Submit the best next move as a four-character string stating the starting and ending "
    "squares of the piece to be moved, e.g. b1c3."
    # Upstream continues "The conversation will end immediately."; that sentence describes the
    # submit_answer tool and does not apply to a file hand-off, so it is left out on purpose.
)
# Handoff replacing upstream's `submit_answer` tool for file-based agents. Prompt changes of
# this kind are acceptable when applied to both sides of a parity experiment.
ANSWER_HANDOFF = (
    "\n\n{submit} Write only that move to /app/answer.txt and nothing else. "
    "This is a closed-book puzzle: do not use chess engines (such as Stockfish), search "
    "the web, or write code to analyze the position. Use the terminal only to write the "
    "answer file.\n"
)

_FEN_RE = re.compile(r"^\S+ [wb] \S+ \S+ \d+ \d+$")
_MOVE_RE = re.compile(r"^[a-h][1-8][a-h][1-8]$")


def task_id(sample_id: int) -> str:
    """Stable local task id; ``sample_id`` is upstream's 1-based dataset-order id."""
    return f"chess-puzzles-{sample_id:03d}"


def parse_records(data: bytes) -> list[dict[str, Any]]:
    """Parse puzzles.csv. Ids follow Inspect's ``auto_id=True``: 1-100 in file order."""
    reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
    if reader.fieldnames != ["input", "target"]:
        raise ValueError(f"Unexpected columns: {reader.fieldnames}")
    records = [
        {"id": index, "fen": row["input"], "target": row["target"]}
        for index, row in enumerate(reader, start=1)
    ]
    validate_records(records)
    return records


def validate_records(records: list[dict[str, Any]]) -> None:
    if len(records) != EXPECTED_ROWS:
        raise ValueError(f"Expected {EXPECTED_ROWS} puzzles, found {len(records)}")
    seen: set[str] = set()
    for record in records:
        if not _FEN_RE.match(record["fen"]):
            raise ValueError(f"Malformed FEN for id {record['id']}: {record['fen']!r}")
        if not _MOVE_RE.match(record["target"]):
            raise ValueError(f"Malformed target for id {record['id']}: {record['target']!r}")
        if record["fen"] in seen:
            raise ValueError(f"Duplicate position: {record['fen']!r}")
        seen.add(record["fen"])


def load_records(path: Path | None, cache_dir: Path) -> list[dict[str, Any]]:
    """Load the pinned puzzles; refuse data whose checksum differs from the pin."""
    if path is None:
        path = cache_dir / f"puzzles-{UPSTREAM_COMMIT[:12]}.csv"
        if not path.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            with urlopen(DATA_URL, timeout=120) as response:
                downloaded = response.read()
            if hashlib.sha256(downloaded).hexdigest() != DATA_SHA256:
                raise ValueError("Downloaded puzzles.csv does not match the pinned checksum")
            path.write_bytes(downloaded)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != DATA_SHA256:
        raise ValueError(f"puzzles.csv checksum mismatch: {path}")
    return parse_records(data)


def render_instruction(fen: str) -> str:
    return QUESTION_TEMPLATE.format(prompt=fen) + ANSWER_HANDOFF.format(
        submit=SUBMIT_DESCRIPTION
    )


def normalize_task_ids(task_ids: list[str]) -> set[int]:
    """Accept ``chess-puzzles-007``, ``007`` or ``7``."""
    wanted: set[int] = set()
    for raw in task_ids:
        match = re.fullmatch(r"(?:chess-puzzles-)?(\d+)", raw.strip())
        if not match:
            raise ValueError(f"Unrecognized task id: {raw!r}")
        wanted.add(int(match.group(1)))
    return wanted


class ChessPuzzlesAdapter:
    NAME = "chess-puzzles"

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        data_path: Path | None = None,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.data_path = data_path
        self.cache_dir = cache_dir or Path(".cache/chess-puzzles")

    def select(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.task_ids:
            wanted = normalize_task_ids(self.task_ids)
            unknown = wanted - {record["id"] for record in records}
            if unknown:
                raise ValueError(f"Unknown task ids: {sorted(unknown)}")
            records = [record for record in records if record["id"] in wanted]
        if self.limit is not None:
            records = records[: self.limit]
        return records

    def run(self) -> list[Path]:
        records = self.select(load_records(self.data_path, self.cache_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        targets = [self.output_dir / task_id(record["id"]) for record in records]
        for target in targets:
            if target.exists() and not self.overwrite:
                raise FileExistsError(f"Task exists; pass --overwrite to replace: {target}")
        # The manifest describes the whole directory, so refuse to leave tasks behind that
        # are not part of this selection.
        selected = {target.name for target in targets}
        stale = sorted(
            path.name
            for path in self.output_dir.iterdir()
            if (path / "task.toml").is_file() and path.name not in selected
        )
        if stale:
            raise ValueError(
                f"Output directory already holds {len(stale)} task(s) outside this selection "
                f"(e.g. {stale[0]}); use a fresh --output-dir"
            )
        for record, target in zip(records, targets, strict=True):
            self._generate(record, target)
        manifest = {
            "benchmark": "Chess Puzzles",
            "upstream": f"https://github.com/{UPSTREAM_REPO}",
            "upstream_commit": UPSTREAM_COMMIT,
            "data_sha256": DATA_SHA256,
            "scoring_version": SCORING_VERSION,
            "generated_count": len(targets),
            "task_ids": [task_id(record["id"]) for record in records],
        }
        (self.output_dir / "generation_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        return targets

    def _generate(self, record: dict[str, Any], target: Path) -> None:
        name = task_id(record["id"])
        with tempfile.TemporaryDirectory(prefix=".chess-puzzles-", dir=self.output_dir) as tmp:
            task = Path(tmp) / "task"
            shutil.copytree(TEMPLATE_DIR, task)

            config = (task / "task.toml").read_text()
            config = config.replace("__TASK_ID__", name).replace(
                "__SAMPLE_ID__", str(record["id"])
            )
            (task / "task.toml").write_text(config)

            (task / "instruction.md").write_text(render_instruction(record["fen"]))

            # The gold move lives only under tests/ and solution/, which are not part of the
            # agent's container image.
            (task / "tests" / "record.json").write_text(
                json.dumps(
                    {"id": record["id"], "fen": record["fen"], "target": record["target"]}
                )
                + "\n"
            )
            shutil.copyfile(PACKAGE_DIR / "scoring.py", task / "tests" / "scoring.py")

            solve = (task / "solution" / "solve.sh").read_text()
            (task / "solution" / "solve.sh").write_text(
                solve.replace("__TARGET__", record["target"])
            )

            if target.exists():
                shutil.rmtree(target)
            task.replace(target)
