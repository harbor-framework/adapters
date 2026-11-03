"""Generate Harbor tasks from the EvoEval benchmark.

EvoEval (Xia, Deng, Zhang, 2024) evolves HumanEval problems into new Python
function-completion problems. Each upstream problem is a JSON row with
``task_id``, ``prompt`` (imports + signature + docstring), ``canonical_solution``
(the function body), ``entry_point`` and the test ``inputs`` (Python expressions;
``base_input`` / ``plus_input`` for the verbose/concise variants).

Every problem becomes one Harbor task:

* ``instruction.md``   the upstream API-model prompt
                       ("Please complete the following code snippet. ...")
                       plus where to save the answer (``/workspace/solution.py``)
* ``tests/``           the upstream problem row and the upstream evaluator
                       (evoeval 0.1.0 / evalplus 0.2.0, vendored), which computes
                       the expected outputs from the canonical solution and runs
                       the candidate with the upstream time limits and oracles
* ``solution/``        ``prompt + "\\n" + canonical_solution`` (the exact program
                       the upstream evaluator uses as ground truth)
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# Upstream data release (evoeval/data.py: EVOEVAL_VERSION and get_dataset_metadata).
EVOEVAL_VERSION = "v0.1.0"
RELEASE_URL = (
    "https://github.com/evo-eval/evoeval_release/releases/download/"
    "{version}/{name}.jsonl.gz"
)

# md5 of the unpacked ``<name>.jsonl`` of the v0.1.0 release. The upstream
# evaluator uses the same digest as its ground-truth cache key
# (evoeval.data.get_evo_eval_plus_hash), so a match means the same data.
DATASET_MD5 = {
    "EvoEval_difficult": "5888868439a2392c01bbcf078c7ee810",
    "EvoEval_creative": "90d893e36f0394828dbc9e25e2fbd6b5",
    "EvoEval_subtle": "e19fe547d76cb2e2d590198f61c9af08",
    "EvoEval_combine": "0136ba257467478eab47e317105c67a9",
    "EvoEval_tool_use": "f391a4d8acd67353fb1187047892a3a6",
    "EvoEval_verbose": "3053e0b07d6d511856b2bee6c9fdea9d",
    "EvoEval_concise": "0f4ac48f140b270a9160da84ec951002",
}
DATASETS = tuple(DATASET_MD5)
DEFAULT_DATASET = "EvoEval_difficult"

# Registry naming: <org>/<adapter>__<variant>-<upstream index>.
TASK_ORG = "evo-eval"
ADAPTER_NAME = "evoeval-auto"

TEMPLATE_DIR = Path(__file__).parent / "task-template"


def variant_slug(dataset: str) -> str:
    """``EvoEval_tool_use`` -> ``tool-use``."""
    if not dataset.startswith("EvoEval_"):
        raise ValueError(f"Unknown EvoEval dataset: {dataset}")
    return dataset[len("EvoEval_") :].replace("_", "-").lower()


def local_task_id(dataset: str, upstream_task_id: str) -> str:
    """``("EvoEval_difficult", "EvoEval/7")`` -> ``difficult-7``.

    Upstream IDs are ``EvoEval/<n>`` (``HumanEval/<n>`` for verbose/concise);
    the number is unique and stable within one dataset file.
    """
    match = re.fullmatch(r"[A-Za-z]+/(\d+)", upstream_task_id)
    if match is None:
        raise ValueError(f"Unexpected upstream task id: {upstream_task_id!r}")
    return f"{variant_slug(dataset)}-{int(match.group(1))}"


class EvoEvalAdapterError(RuntimeError):
    """An expected failure that the CLI reports as a one-line error."""


class EvoEvalDataError(EvoEvalAdapterError):
    """The EvoEval release file could not be obtained or is not the pinned one."""


def _download(dataset: str) -> bytes:
    url = RELEASE_URL.format(version=EVOEVAL_VERSION, name=dataset)
    logger.info("Downloading %s", url)
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            payload = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EvoEvalDataError(
            f"Could not download {url}: {exc}. Check network access, or pass a local "
            "copy with --data-file."
        ) from exc
    try:
        return gzip.decompress(payload)
    except (OSError, EOFError) as exc:
        raise EvoEvalDataError(f"{url} is not a valid .gz file: {exc}") from exc


def load_problems(
    dataset: str,
    data_file: Path | None = None,
    cache_dir: Path | None = None,
) -> list[dict]:
    """Load the upstream problems in file order (EvoEval/0, EvoEval/1, ...).

    Source, in order of preference: ``data_file`` (a local ``.jsonl`` or
    ``.jsonl.gz`` copy of the release file), ``cache_dir`` (download once and
    reuse), or a fresh in-memory download of the pinned release.
    """
    if dataset not in DATASETS:
        raise ValueError(f"Unknown dataset {dataset!r}; choose one of {DATASETS}")

    if data_file is not None:
        try:
            raw = Path(data_file).read_bytes()
            if str(data_file).endswith(".gz"):
                raw = gzip.decompress(raw)
        except (OSError, EOFError) as exc:
            raise EvoEvalDataError(f"Could not read {data_file}: {exc}") from exc
        source = str(data_file)
    elif cache_dir is not None:
        cached = Path(cache_dir) / f"{dataset}-{EVOEVAL_VERSION}.jsonl"
        try:
            if not cached.exists():
                cached.parent.mkdir(parents=True, exist_ok=True)
                tmp = cached.with_suffix(".tmp")
                tmp.write_bytes(_download(dataset))
                tmp.replace(cached)
            raw = cached.read_bytes()
        except OSError as exc:
            raise EvoEvalDataError(f"Cache error in {cache_dir}: {exc}") from exc
        source = str(cached)
    else:
        raw = _download(dataset)
        source = RELEASE_URL.format(version=EVOEVAL_VERSION, name=dataset)

    digest = hashlib.md5(raw).hexdigest()
    if digest != DATASET_MD5[dataset]:
        raise EvoEvalDataError(
            f"{source} has md5 {digest}, expected {DATASET_MD5[dataset]} "
            f"({dataset} {EVOEVAL_VERSION})."
        )
    try:
        problems = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvoEvalDataError(f"{source} is not valid JSON Lines: {exc}") from exc
    ids = [p["task_id"] for p in problems]
    if len(set(ids)) != len(ids):
        raise EvoEvalDataError(f"Duplicate task ids in {source}")
    return problems


class EvoevalAutoAdapter:
    """Write one Harbor task directory per EvoEval problem."""

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        dataset: str = DEFAULT_DATASET,
        data_file: Path | None = None,
        cache_dir: Path | None = None,
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.dataset = dataset
        self.data_file = data_file
        self.cache_dir = cache_dir
        if dataset not in DATASETS:
            raise EvoEvalAdapterError(f"Unknown dataset {dataset!r}; choose one of {DATASETS}")

    # ------------------------------------------------------------------ helpers
    def _select(self, problems: list[dict]) -> list[dict]:
        selected = problems
        if self.task_ids:
            wanted = set(self.task_ids)
            selected = [
                p
                for p in problems
                if p["task_id"] in wanted
                or local_task_id(self.dataset, p["task_id"]) in wanted
            ]
            found = {p["task_id"] for p in selected} | {
                local_task_id(self.dataset, p["task_id"]) for p in selected
            }
            missing = sorted(wanted - found)
            if missing:
                raise EvoEvalAdapterError(f"Unknown task ids for {self.dataset}: {missing}")
        if self.limit is not None:
            selected = selected[: max(self.limit, 0)]
        return selected

    @staticmethod
    def _render(text: str, values: dict[str, str]) -> str:
        # Plain replacement (prompts contain braces, so no str.format).
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        return text

    def _write_task(self, problem: dict) -> Path:
        local_id = local_task_id(self.dataset, problem["task_id"])
        final_dir = self.output_dir / local_id
        if final_dir.exists() and not self.overwrite:
            logger.info("Skipping %s (exists; use --overwrite)", local_id)
            return final_dir

        # Build the task in a temporary sibling directory and move it into place
        # only when complete, so a failed run never leaves a partial task behind.
        staging = Path(tempfile.mkdtemp(prefix=f".{local_id}.", dir=self.output_dir))
        task_dir = staging / local_id
        try:
            self._render_task(problem, local_id, task_dir)
            if final_dir.exists():
                shutil.rmtree(final_dir)
            task_dir.rename(final_dir)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return final_dir

    def _render_task(self, problem: dict, local_id: str, task_dir: Path) -> None:
        shutil.copytree(
            TEMPLATE_DIR,
            task_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )

        # task.toml
        toml_path = task_dir / "task.toml"
        toml_path.write_text(
            self._render(
                toml_path.read_text(),
                {
                    "TASK_NAME": f"{TASK_ORG}/{ADAPTER_NAME}__{local_id}",
                    "VARIANT": variant_slug(self.dataset),
                    "DIFFICULTY": "hard" if self.dataset == "EvoEval_difficult" else "medium",
                    "SOURCE_DATASET": self.dataset,
                    "SOURCE_TASK_ID": problem["task_id"],
                    "PARENT": str(problem.get("parent") or ""),
                },
            )
        )

        # instruction.md: upstream API-model prompt, prompt.strip() as upstream.
        instr_path = task_dir / "instruction.md"
        instr_path.write_text(
            self._render(
                instr_path.read_text(),
                {
                    "ENTRY_POINT": problem["entry_point"],
                    "PROMPT": problem["prompt"].strip(),
                },
            )
        )

        # Oracle: the exact ground-truth program of the upstream evaluator.
        (task_dir / "solution" / "solution.py").write_text(
            problem["prompt"] + "\n" + problem["canonical_solution"]
        )

        # Hidden test data: only in the separate verifier image (tests/Dockerfile).
        (task_dir / "tests" / "problem.json").write_text(
            json.dumps({"dataset": self.dataset, "problem": problem}, indent=1)
        )
        for script in (task_dir / "solution" / "solve.sh", task_dir / "tests" / "test.sh"):
            script.chmod(0o755)

    # --------------------------------------------------------------------- run
    def run(self) -> None:
        problems = load_problems(self.dataset, self.data_file, self.cache_dir)
        selected = self._select(problems)
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for problem in selected:
                self._write_task(problem)
        except OSError as exc:
            raise EvoEvalAdapterError(f"Cannot write tasks to {self.output_dir}: {exc}") from exc
        logger.info(
            "Wrote %d %s task(s) to %s", len(selected), self.dataset, self.output_dir
        )
