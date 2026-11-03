"""Generate Harbor tasks from the EvoEval benchmark.

EvoEval (Xia, Deng & Zhang, 2024; https://github.com/evo-eval/evoeval) evolves HumanEval
problems into seven new benchmarks. Each problem is a Python function stub (signature +
docstring) that has to be completed. The upstream evaluator runs the canonical solution
to obtain the expected outputs and then compares the candidate's outputs input by input.

For every problem this adapter writes one Harbor task:

- ``instruction.md``: the problem prompt plus where to put the solution.
- ``environment/``: a Python 3.9 image with the upstream evaluator's dependencies
  (identical for every task).
- ``solution/``: the upstream ground-truth program (``prompt + "\\n" +
  canonical_solution``).
- ``tests/``: the unmodified upstream evaluator (vendored) and the problem record,
  including the hidden canonical solution and inputs.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

EVOEVAL_RELEASE_VERSION = "v0.1.0"
EVOEVAL_RELEASE_URL = (
    "https://github.com/evo-eval/evoeval_release/releases/download/"
    "{version}/{dataset}.jsonl.gz"
)
# Upstream ``evoeval.data.get_dataset_metadata`` accepts exactly these names.
EVOEVAL_DATASETS = (
    "EvoEval_difficult",
    "EvoEval_creative",
    "EvoEval_subtle",
    "EvoEval_combine",
    "EvoEval_tool_use",
    "EvoEval_verbose",
    "EvoEval_concise",
)
DEFAULT_DATASET = "EvoEval_difficult"
# md5 of the decompressed v0.1.0 release file, checked when it is known.
KNOWN_MD5 = {
    "EvoEval_difficult": "5888868439a2392c01bbcf078c7ee810",
}

TEMPLATE_DIR = Path(__file__).parent / "task-template"
TASK_ORG = "evoeval"


def dataset_slug(dataset: str) -> str:
    """``EvoEval_tool_use`` -> ``evoeval-tool-use``."""
    return re.sub(r"[^a-z0-9]+", "-", dataset.lower()).strip("-")


def task_number(source_id: str) -> int:
    """``EvoEval/7`` or ``HumanEval/7`` -> ``7``."""
    match = re.fullmatch(r"[A-Za-z]+/(\d+)", source_id)
    if match is None:
        raise ValueError(f"Unexpected EvoEval task id: {source_id!r}")
    return int(match.group(1))


def harbor_task_name(dataset: str, source_id: str) -> str:
    """Stable, registry-safe task name, e.g. ``evoeval-difficult-7``."""
    return f"{dataset_slug(dataset)}-{task_number(source_id)}"


def toml_str(value: Any) -> str:
    """Escape a value for use inside a TOML basic string ("...")."""
    return json.dumps(str(value), ensure_ascii=False)[1:-1]


@dataclass
class EvoEvalProblem:
    dataset: str
    record: dict[str, Any]

    @property
    def source_id(self) -> str:
        return self.record["task_id"]

    @property
    def name(self) -> str:
        return harbor_task_name(self.dataset, self.source_id)

    @property
    def prompt(self) -> str:
        return self.record["prompt"]

    @property
    def entry_point(self) -> str:
        return self.record["entry_point"]

    @property
    def ground_truth_program(self) -> str:
        # Identical to evoeval.evaluate.get_groundtruth: prompt + "\n" + canonical_solution
        return self.record["prompt"] + "\n" + self.record["canonical_solution"]

    @property
    def parent(self) -> str:
        if "parent" in self.record:
            return str(self.record["parent"])
        parents = [str(self.record[k]) for k in ("p1", "p2") if k in self.record]
        return " + ".join(parents)


def _download(url: str, attempts: int = 3) -> bytes:
    """Download and decompress a release file, retrying transient network errors."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            logger.info("Downloading %s (attempt %d/%d)", url, attempt, attempts)
            with urllib.request.urlopen(url, timeout=120) as resp:
                return gzip.decompress(resp.read())
        except (OSError, EOFError) as e:  # URLError is an OSError; bad gzip -> OSError/EOFError
            last_error = e
            time.sleep(2 * attempt)
    raise RuntimeError(f"Could not download {url}: {last_error}") from last_error


REQUIRED_FIELDS = ("task_id", "prompt", "canonical_solution", "entry_point")


def validate_record(dataset: str, record: dict[str, Any]) -> None:
    """Reject a problem record that the verifier could not grade."""
    missing = [k for k in REQUIRED_FIELDS if not isinstance(record.get(k), str) or not record[k]]
    if "verbose" in dataset or "concise" in dataset:
        if not isinstance(record.get("base_input"), list):
            missing.append("base_input")
        if not isinstance(record.get("plus_input"), list):
            missing.append("plus_input")
    elif not isinstance(record.get("inputs"), list) or not record["inputs"]:
        missing.append("inputs")
    if missing:
        raise ValueError(
            f"{dataset} record {record.get('task_id', '?')!r} lacks required fields: {missing}"
        )
    task_number(record["task_id"])  # raises on an unexpected id format
    if f"def {record['entry_point']}(" not in record["prompt"]:
        raise ValueError(f"{record['task_id']}: entry point not defined in the prompt")


def load_evoeval(
    dataset: str,
    data_path: Path | None = None,
    cache_dir: Path | None = None,
) -> list[EvoEvalProblem]:
    """Load an EvoEval dataset (release v0.1.0), sorted by numeric task id."""
    if dataset not in EVOEVAL_DATASETS:
        raise ValueError(
            f"Unknown EvoEval dataset {dataset!r}; choose one of {EVOEVAL_DATASETS}"
        )

    if data_path is not None:
        raw = data_path.read_bytes()
        if data_path.suffix == ".gz":
            raw = gzip.decompress(raw)
        logger.info("Loaded %s from %s", dataset, data_path)
    else:
        cache_file = (
            cache_dir / f"{dataset}-{EVOEVAL_RELEASE_VERSION}.jsonl" if cache_dir else None
        )
        if cache_file is not None and cache_file.exists():
            raw = cache_file.read_bytes()
            logger.info("Loaded %s from cache %s", dataset, cache_file)
        else:
            url = EVOEVAL_RELEASE_URL.format(
                version=EVOEVAL_RELEASE_VERSION, dataset=dataset
            )
            raw = _download(url)
            if cache_file is not None:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(raw)

    digest = hashlib.md5(raw).hexdigest()
    expected = KNOWN_MD5.get(dataset)
    if expected is not None and digest != expected:
        raise ValueError(
            f"{dataset} data md5 {digest} does not match the v0.1.0 release ({expected})"
        )
    logger.info("%s md5=%s", dataset, digest)

    records = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    for record in records:
        validate_record(dataset, record)
    problems = [EvoEvalProblem(dataset=dataset, record=r) for r in records]
    problems.sort(key=lambda p: task_number(p.source_id))
    names = [p.name for p in problems]
    if len(set(names)) != len(names):
        raise ValueError(f"Duplicate task names generated for {dataset}")
    return problems


class EvoEvalAutoAdapter:
    """Write one Harbor task directory per EvoEval problem into ``output_dir``."""

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        dataset: str = DEFAULT_DATASET,
        data_path: Path | None = None,
        cache_dir: Path | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.dataset = dataset
        self.data_path = data_path
        self.cache_dir = cache_dir

    # ------------------------------------------------------------------ selection
    def _matches(self, problem: EvoEvalProblem, wanted: set[str]) -> bool:
        number = str(task_number(problem.source_id))
        return bool(
            {problem.source_id, problem.name, f"{TASK_ORG}/{problem.name}", number}
            & wanted
        )

    def select(self, problems: Iterable[EvoEvalProblem]) -> list[EvoEvalProblem]:
        selected = list(problems)
        if self.task_ids:
            wanted = {t.strip() for t in self.task_ids if t.strip()}
            selected = [p for p in selected if self._matches(p, wanted)]
            found = set()
            for p in selected:
                found |= {p.source_id, p.name, f"{TASK_ORG}/{p.name}", str(task_number(p.source_id))}
            missing = sorted(wanted - found)
            if missing:
                logger.warning("Unknown task ids ignored: %s", ", ".join(missing))
        if self.limit is not None:
            selected = selected[: max(0, self.limit)]
        return selected

    # ------------------------------------------------------------------ rendering
    def _render(self, text: str, problem: EvoEvalProblem, *, toml: bool = False) -> str:
        values = {
            "task_name": f"{TASK_ORG}/{problem.name}",
            "dataset": problem.dataset,
            "dataset_slug": dataset_slug(problem.dataset),
            "source_id": problem.source_id,
            "parent": problem.parent,
            "entry_point": problem.entry_point,
            "difficulty": "hard" if problem.dataset == "EvoEval_difficult" else "medium",
        }
        for key, value in values.items():
            text = text.replace("{" + key + "}", toml_str(value) if toml else value)
        if not toml:
            # The prompt goes in last so that braces inside it are never re-substituted.
            # Ten EvoEval_difficult prompts use CRLF line endings; Harbor reads
            # instruction.md with universal newlines, so normalise them explicitly.
            prompt = problem.prompt.replace("\r\n", "\n").strip("\n")
            text = text.replace("{prompt}", prompt)
        return text

    REQUIRED_TASK_FILES = (
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "solution/solve.sh",
        "solution/solution.py",
        "tests/test.sh",
        "tests/evaluate.py",
        "tests/isolated_runner.py",
        "tests/problem.json",
    )

    def is_complete(self, task_dir: Path) -> bool:
        return all((task_dir / rel).is_file() for rel in self.REQUIRED_TASK_FILES)

    def generate_task(self, problem: EvoEvalProblem) -> Path:
        task_dir = self.output_dir / problem.name
        if task_dir.exists() and not self.overwrite:
            if self.is_complete(task_dir):
                logger.info("Skipping %s (exists; use --overwrite)", task_dir)
                return task_dir
            logger.warning("Regenerating incomplete task directory %s", task_dir)

        # Build the task in a temporary sibling directory, then move it into place, so an
        # interrupted run never leaves a half-written task behind.
        staging = Path(
            tempfile.mkdtemp(prefix=f".{problem.name}.", dir=self.output_dir)
        )
        try:
            build_dir = staging / problem.name
            shutil.copytree(
                TEMPLATE_DIR,
                build_dir,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

            # task.toml and instruction.md
            task_toml = build_dir / "task.toml"
            task_toml.write_text(self._render(task_toml.read_text(), problem, toml=True))
            instruction = build_dir / "instruction.md"
            instruction.write_text(self._render(instruction.read_text(), problem))

            # Oracle: the upstream ground-truth program.
            (build_dir / "solution" / "solution.py").write_text(
                problem.ground_truth_program + "\n"
            )

            # Tests: the full upstream record (hidden from the agent until verification).
            (build_dir / "tests" / "problem.json").write_text(
                json.dumps(
                    {
                        "dataset": problem.dataset,
                        "release": EVOEVAL_RELEASE_VERSION,
                        "problem": problem.record,
                    },
                    indent=1,
                    ensure_ascii=False,
                )
                + "\n"
            )

            for script in (
                build_dir / "solution" / "solve.sh",
                build_dir / "tests" / "test.sh",
            ):
                script.chmod(0o755)
            if not self.is_complete(build_dir):
                raise RuntimeError(f"generated task {problem.name} is incomplete")

            if task_dir.exists():
                shutil.rmtree(task_dir)
            os.replace(build_dir, task_dir)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return task_dir

    def run(self) -> list[Path]:
        problems = load_evoeval(self.dataset, self.data_path, self.cache_dir)
        selected = self.select(problems)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = [self.generate_task(p) for p in selected]
        logger.info(
            "Generated %d/%d %s tasks in %s",
            len(written),
            len(problems),
            self.dataset,
            self.output_dir,
        )
        return written
