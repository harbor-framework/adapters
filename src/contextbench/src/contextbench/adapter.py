"""Convert pinned ContextBench datasets into Harbor tasks."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import shutil
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pyarrow import parquet

from .vendor_api import normalize_gold_path

CONTEXTBENCH_COMMIT = "1436c28a8eb95496da4ea69ad458b9f8a8eb7d61"
CONTEXTBENCH_REPOSITORY = "https://github.com/EuniAI/ContextBench"


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    filename: str
    sha256: str
    rows: int

    @property
    def url(self) -> str:
        return (
            f"{CONTEXTBENCH_REPOSITORY}/raw/{CONTEXTBENCH_COMMIT}/data/{self.filename}"
        )

    @property
    def cache_path(self) -> Path:
        return (
            Path.home()
            / ".cache"
            / "harbor"
            / "contextbench"
            / CONTEXTBENCH_COMMIT
            / self.filename
        )


@dataclass(frozen=True)
class NativeEnvironment:
    """A source benchmark's task image and how the agent image adapts it."""

    image: str
    repository_path: str
    # Files the source benchmark ships for grading, such as its reference patch.
    grading_files: tuple[str, ...] = ()
    # Dockerfile lines that activate the project environment upstream runners use.
    project_environment: str = ""


@dataclass(frozen=True)
class OracleRead:
    path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class PreparedRow:
    repository: str
    commit: str
    problem: str
    # Whether `problem` was decoded from a JSON string literal.
    problem_decoded: bool
    # Upstream annotations with raw `file` values, for the verifier's `Gold`.
    gold_context: list[dict[str, Any]]
    # The same annotations with repository-relative paths, for the oracle.
    oracle_reads: list[OracleRead]
    patch: str
    source: str
    original_instance_id: str
    language: str
    native: NativeEnvironment


@dataclass(frozen=True)
class Correction:
    """A checked-in replacement for one upstream value (`corrections.json`)."""

    instance_id: str
    field: str
    # SHA-256 of the exact upstream value the correction replaces; a missing
    # value counts as the empty string.
    replaces_sha256: str
    value: str
    # Where the corrected value comes from: dataset, revision, file, instance_id.
    source: dict[str, str]
    reason: str


class InvalidDatasetRowsError(ValueError):
    """Selected ContextBench rows are incomplete or malformed."""

    def __init__(self, failures: list[dict[str, str]]) -> None:
        details = "; ".join(
            f"{item['instance_id']}: {item['error']}" for item in failures
        )
        super().__init__(
            f"{len(failures)} selected ContextBench row(s) are invalid: {details}"
        )
        self.failures = failures


DATASETS = {
    spec.name: spec
    for spec in (
        DatasetSpec(
            name="full",
            filename="full.parquet",
            sha256="2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8",
            rows=1136,
        ),
        DatasetSpec(
            name="verified",
            filename="contextbench_verified.parquet",
            sha256="e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791",
            rows=500,
        ),
        DatasetSpec(
            name="verified-train",
            filename="contextbench_verified_train.parquet",
            sha256="cd1bc4ddefa69271d4f073f31d54bf33a1c5671800211d9db7e6a3c24435a75d",
            rows=450,
        ),
        DatasetSpec(
            name="verified-test",
            filename="contextbench_verified_test.parquet",
            sha256="4b560777bc8ba4061c7afa5f98ca2b5c793d0a32f085f25c5c817db0708b3629",
            rows=50,
        ),
    )
}
DEFAULT_DATASET_NAME = "verified"
PARITY_DATASET_NAME = "verified-test"
PARITY_TASK_IDS = (
    "SWE-Bench-Verified__python__maintenance__bugfix__90532e38",
    "SWE-Bench-Verified__python__maintenance__bugfix__607f6b9e",
    "SWE-Bench-Verified__python__maintenance__bugfix__220feee3",
    "SWE-Bench-Verified__python__maintenance__bugfix__27320d49",
    "SWE-Bench-Verified__python__maintenance__bugfix__67699b64",
    "SWE-Bench-Verified__python__maintenance__bugfix__16c72e4c",
    "SWE-Bench-Verified__python__maintenance__bugfix__bdde6d9c",
    "SWE-Bench-Verified__python__maintenance__bugfix__61a7a81e",
    "SWE-Bench-Verified__python__maintenance__bugfix__0b74a2c7",
    "SWE-Bench-Verified__python__maintenance__bugfix__765e5e14",
)

PACKAGE_DIR = Path(__file__).parent
TEMPLATE_DIR = PACKAGE_DIR / "task-template"
VENDOR_DIR = PACKAGE_DIR / "vendor"
CORRECTIONS_PATH = PACKAGE_DIR / "corrections.json"
# The linux/amd64 manifest digest of every image that the generated
# Dockerfiles start from. scripts/image_digests.py refreshes it.
IMAGE_DIGESTS_PATH = PACKAGE_DIR / "image-digests.json"
REPORT_FILENAME = "contextbench-generation-report.json"
# The other base images of the generated Dockerfiles, for the stage that
# fetches the base commit and for the verifier.
GIT_IMAGE = "alpine/git:2.49.1"
VERIFIER_IMAGE = "python:3.12-slim-bookworm"

_VERIFIER_MODULES = (
    "attribution/__init__.py",
    "attribution/receipts.py",
    "attribution/rules.py",
    "attribution/trajectory.py",
    "attribution/types.py",
    "scoring.py",
    "vendor_api.py",
)

_REQUIRED_COLUMNS = {
    "instance_id",
    "original_inst_id",
    "base_commit",
    "problem_statement",
    "gold_context",
    "patch",
    "language",
    "source",
}
_FULL_COMMIT = re.compile(r"[0-9a-f]{40}")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_GITHUB_URL = re.compile(r"https://github\.com/(?P<slug>[^/]+/[^/]+?)(?:\.git)?/?")
# SWE-bench Pro: instance_<owner>__<name>-<base commit>[-v<suffix>].
_PRO_INSTANCE = re.compile(
    r"instance_(?P<owner>[^_]+)__(?P<name>.+)-[0-9a-f]{40}(?:-v[0-9a-z]+)?"
)
# SWE-bench, SWE-PolyBench and Multi-SWE-bench: <owner>__<name>-<number>.
_NUMBERED_INSTANCE = re.compile(r"(?P<owner>[^_]+)__(?P<name>.+)-[0-9]+")
_NATIVE_SOURCES = frozenset({"Verified", "Pro", "Poly", "Multi"})
_ELEMENT_WEB_FULL_TAG_INSTANCE = (
    "instance_element-hq__element-web-ec0f940ef0e8e3b61078f145f34dc40d1938e6c5-vnan"
)
# Multi-SWE-bench images keep their harness next to the repository: the
# reference and test patches plus the scripts that apply them and run tests.
_MULTI_SWE_BENCH_HARNESS = tuple(
    f"/home/{name}"
    for name in (
        "fix.patch",
        "test.patch",
        "fix-run.sh",
        "test-run.sh",
        "run.sh",
        "prepare.sh",
        "check_git_changes.sh",
    )
)
# SWE-bench runners activate the image's conda `testbed` environment.
_SWE_BENCH_ENVIRONMENT = """\
ENV CONDA_DEFAULT_ENV=testbed \\
    CONDA_PREFIX=/opt/miniconda3/envs/testbed \\
    PATH=/opt/miniconda3/envs/testbed/bin:$PATH
RUN test "$(command -v python)" = /opt/miniconda3/envs/testbed/bin/python
"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text(path: Path, text: str) -> None:
    """Write UTF-8 text without translating newlines, the same on every host."""
    path.write_text(text, encoding="utf-8", newline="\n")


@lru_cache(maxsize=1)
def _image_digests() -> dict[str, str]:
    pinned = json.loads(IMAGE_DIGESTS_PATH.read_text(encoding="utf-8"))
    return {str(image): str(digest) for image, digest in pinned.items()}


def _require_image_digests(images: set[str]) -> None:
    """Fail before any task is written if an image has no pinned digest."""
    digests = _image_digests()
    missing = sorted(image for image in images if image not in digests)
    if missing:
        raise RuntimeError(
            f"{IMAGE_DIGESTS_PATH.name} has no digest for {len(missing)} "
            f"image(s): {', '.join(missing)}; add them with scripts/image_digests.py"
        )


def pinned_image(reference: str) -> str:
    """Return `name:tag@sha256:...`, keeping the tag for readability.

    The source benchmarks can republish an image under the same tag, so only
    the digest fixes the image a task was generated for.
    """
    _require_image_digests({reference})
    return f"{reference}@{_image_digests()[reference]}"


def download_dataset(spec: DatasetSpec, destination: Path | None = None) -> Path:
    """Download and verify one pinned ContextBench parquet."""
    destination = (destination or spec.cache_path).expanduser()
    if destination.is_file() and sha256_file(destination) == spec.sha256:
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    try:
        with urllib.request.urlopen(spec.url, timeout=120) as response:
            temporary.write_bytes(response.read())
    except (OSError, urllib.error.URLError) as error:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"could not download pinned ContextBench dataset: {error}"
        ) from error

    actual = sha256_file(temporary)
    if actual != spec.sha256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "downloaded ContextBench dataset checksum mismatch: "
            f"expected {spec.sha256}, got {actual}"
        )
    temporary.replace(destination)
    return destination


def _json_value(value: Any, *, field: str) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {field}: {error}") from error


def decoded_json_string(value: str) -> str | None:
    """Return the text a JSON-quoted problem statement encodes, else None.

    Some SWE-bench Pro statements are stored as JSON string literals, so agents
    would see their quotes and `\\n` escapes. A value is decoded only when the
    whole value, with nothing before or after it, is one JSON string literal.
    Text that merely starts with a quote, or parses as another JSON type, is not
    decoded, and a decoded value is not decoded again.
    """
    if len(value) < 2 or value[0] != '"' or value[-1] != '"':
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, str) else None


def load_corrections() -> tuple[Correction, ...]:
    entries = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))["corrections"]
    return tuple(Correction(**entry) for entry in entries)


def _corrected(row: dict[str, Any], corrections: list[Correction]) -> dict[str, Any]:
    """Apply a row's corrections, rejecting any whose upstream value differs.

    A missing or null upstream value is hashed as the empty string.
    """
    for correction in corrections:
        value = row.get(correction.field)
        value = "" if value is None else value
        if (
            not isinstance(value, str)
            or hashlib.sha256(value.encode()).hexdigest() != correction.replaces_sha256
        ):
            raise ValueError(
                f"{correction.field} is not the value its correction replaces "
                f"(SHA-256 {correction.replaces_sha256})"
            )
        row = {**row, correction.field: correction.value}
    return row


def _repository_from_instance(source: str, original_instance_id: str) -> str:
    pattern = _PRO_INSTANCE if source == "Pro" else _NUMBERED_INSTANCE
    match = pattern.fullmatch(original_instance_id)
    if match is None:
        raise ValueError(
            f"cannot infer a repository from original_inst_id {original_instance_id!r}"
        )
    return f"{match['owner']}/{match['name']}"


def _repository(row: dict[str, Any], source: str, original_instance_id: str) -> str:
    """Return the task's GitHub repository.

    `repo_url` is authoritative when present. The `repo` column is not used: for
    some Multi-SWE-bench rows it is truncated at the first hyphen of the name
    (`fasterxml/jackson` for `fasterxml/jackson-core`).
    """
    inferred = _repository_from_instance(source, original_instance_id)
    repo_url = str(row.get("repo_url") or "").strip()
    if not repo_url:
        repository = inferred
    elif (match := _GITHUB_URL.fullmatch(repo_url)) is None:
        raise ValueError(f"repo_url is not a GitHub repository URL: {repo_url!r}")
    else:
        repository = str(match["slug"])
        if repository != inferred:
            raise ValueError(
                f"repo_url names {repository} but original_inst_id names {inferred}"
            )
    if _REPOSITORY.fullmatch(repository) is None:
        raise ValueError(f"invalid ContextBench repository identifier: {repository!r}")
    return repository


def _normalize_gold_path(raw_path: str) -> str:
    """Return the path the oracle reads for a gold annotation.

    ContextBench's normalizer is not idempotent (`/workspace/x/.github/a`
    becomes `.github/a`, then `github/a`), so only the oracle uses its output:
    `gold.json` keeps the raw values for the verifier's `Gold` to normalize.
    """
    value = normalize_gold_path(raw_path)
    if not value or any(part == ".." for part in Path(value).parts):
        raise ValueError(f"invalid gold context path: {raw_path!r}")
    return value


def _dataset_label(dataset_sha256: str) -> str:
    """Name a dataset by its content: the pinned name, else `custom-<digest>`."""
    for spec in DATASETS.values():
        if spec.sha256 == dataset_sha256:
            return spec.name
    return f"custom-{dataset_sha256[:8]}"


def task_directory_name(dataset_label: str, instance_id: str) -> str:
    """Return the task directory name; the task name adds `contextbench/`."""
    digest = hashlib.sha256(instance_id.encode()).hexdigest()[:16]
    return f"{dataset_label}-{digest}"


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _render(template: Path, replacements: dict[str, str]) -> str:
    content = template.read_text(encoding="utf-8")
    placeholders = set(re.findall(r"__[A-Z][A-Z0-9_]*__", content))
    missing = sorted(placeholders - replacements.keys())
    if missing:
        raise ValueError(
            f"unrendered placeholders in {template.name}: {', '.join(missing)}"
        )
    for marker, replacement in replacements.items():
        content = content.replace(marker, replacement)
    return content


def _verifier_dockerfile(template: Path, repository: str, commit: str) -> str:
    return _render(
        template,
        {
            "__GIT_IMAGE__": pinned_image(GIT_IMAGE),
            "__VERIFIER_IMAGE__": pinned_image(VERIFIER_IMAGE),
            "__REPOSITORY_URL__": f"https://github.com/{repository}.git",
            "__BASE_COMMIT__": commit,
        },
    )


def _swebench_pro_image(original_instance_id: str, repository: str) -> str:
    owner, repo_name = repository.lower().split("/", 1)
    suffix = original_instance_id.removeprefix("instance_")
    # SWE-bench Pro's published tags drop `-vnan` and name element-web's
    # images `element`, except for one element-web task.
    if original_instance_id != _ELEMENT_WEB_FULL_TAG_INSTANCE:
        suffix = suffix.removesuffix("-vnan")
        if (owner, repo_name) == ("element-hq", "element-web"):
            repo_name = "element"
    tag = f"{owner}.{repo_name}-{suffix}"[:128]
    return f"docker.io/jefzda/sweap-images:{tag}"


def native_environment(
    source: str,
    original_instance_id: str,
    repository: str,
) -> NativeEnvironment:
    """Return ContextBench's native task environment for one row.

    `original_instance_id` has already been matched against `repository`.
    """
    if source == "Verified":
        image_id = original_instance_id.replace("__", "_1776_").lower()
        return NativeEnvironment(
            image=f"docker.io/swebench/sweb.eval.x86_64.{image_id}:latest",
            repository_path="/testbed",
            project_environment=_SWE_BENCH_ENVIRONMENT,
        )
    if source == "Pro":
        return NativeEnvironment(
            image=_swebench_pro_image(original_instance_id, repository),
            repository_path="/app",
        )
    if source == "Poly":
        return NativeEnvironment(
            image=(
                "ghcr.io/timesler/"
                f"swe-polybench.eval.x86_64.{original_instance_id.lower()}:latest"
            ),
            repository_path="/testbed",
        )

    pull_request = original_instance_id.rsplit("-", 1)[1]
    owner, repo_name = repository.lower().split("/", 1)
    image_owner = owner.replace(".", "_")
    image_repo = repo_name.replace(".", "_")
    return NativeEnvironment(
        image=f"docker.io/mswebench/{image_owner}_m_{image_repo}:pr-{pull_request}",
        repository_path=f"/home/{repository.split('/', 1)[1]}",
        grading_files=_MULTI_SWE_BENCH_HARNESS,
    )


def _agent_environment_dockerfile(
    template: Path,
    prepared: PreparedRow,
) -> str:
    native = prepared.native
    removed = ("/workspace", f"{native.repository_path}/.git", *native.grading_files)
    return _render(
        template,
        {
            "__GIT_IMAGE__": pinned_image(GIT_IMAGE),
            "__REPOSITORY_URL__": f"https://github.com/{prepared.repository}.git",
            "__BASE_COMMIT__": prepared.commit,
            "__NATIVE_IMAGE__": pinned_image(native.image),
            "__NATIVE_REPOSITORY_PATH__": native.repository_path,
            "__REMOVED_PATHS__": " ".join(shlex.quote(path) for path in removed),
            "__RECORD_BASELINE__": RECORD_BASELINE,
            "__PROJECT_ENVIRONMENT__": native.project_environment,
        },
    )


def oracle_trajectory(
    instance_id: str, oracle_reads: list[OracleRead]
) -> dict[str, Any]:
    """Return the oracle's ATIF trajectory: one structured read per gold range."""
    call_ids = [f"oracle-read-{index}" for index in range(1, len(oracle_reads) + 1)]
    return {
        "schema_version": "ATIF-v1.7",
        "session_id": f"oracle-{hashlib.sha256(instance_id.encode()).hexdigest()[:16]}",
        "agent": {"name": "oracle", "version": "1.0.0"},
        "steps": [
            {
                "step_id": 1,
                "source": "agent",
                "message": "",
                "tool_calls": [
                    {
                        "tool_call_id": call_id,
                        "function_name": "Read",
                        "arguments": {
                            "file_path": f"/workspace/{read.path}",
                            "offset": read.start_line,
                            "limit": read.end_line - read.start_line + 1,
                        },
                    }
                    for call_id, read in zip(call_ids, oracle_reads, strict=True)
                ],
                "observation": {
                    "results": [{"source_call_id": call_id} for call_id in call_ids]
                },
                "llm_call_count": 0,
            }
        ],
    }


def prepare_row(row: dict[str, Any]) -> PreparedRow:
    source = str(row.get("source") or "").strip()
    if source not in _NATIVE_SOURCES:
        raise ValueError(
            f"unsupported ContextBench source {source!r}; "
            f"expected one of {', '.join(sorted(_NATIVE_SOURCES))}"
        )
    original_instance_id = str(row.get("original_inst_id") or "").strip()
    repository = _repository(row, source, original_instance_id)
    commit = str(row.get("base_commit") or "").strip().lower()
    if _FULL_COMMIT.fullmatch(commit) is None:
        raise ValueError("base_commit must be a full SHA-1")

    problem = str(row.get("problem_statement") or "")
    decoded = decoded_json_string(problem)
    problem = (problem if decoded is None else decoded).strip()
    if not problem:
        raise ValueError("problem_statement is empty")
    language = str(row.get("language") or "").strip().lower()
    if not language:
        raise ValueError("language is empty")
    raw_gold = _json_value(row.get("gold_context"), field="gold_context")
    if not isinstance(raw_gold, list) or not raw_gold:
        raise ValueError("gold_context must be a non-empty list")

    gold_context: list[dict[str, Any]] = []
    oracle_reads: list[OracleRead] = []
    for annotation in raw_gold:
        if not isinstance(annotation, dict):
            raise TypeError("gold annotation must be an object")
        # Defaults apply only to absent values: `or` would silently
        # rewrite a malformed 0 into a valid coordinate before the range
        # validation below could reject it.
        raw_start = annotation.get("start_line")
        raw_end = annotation.get("end_line")
        start = 1 if raw_start is None else int(raw_start)
        end = start if raw_end is None else int(raw_end)
        if start < 1 or end < start:
            raise ValueError(f"invalid gold line range {start}-{end}")
        raw_file = str(annotation.get("file") or "")
        oracle_reads.append(OracleRead(_normalize_gold_path(raw_file), start, end))
        gold_context.append(
            {
                **{key: value for key, value in annotation.items() if key != "content"},
                "file": raw_file,
                "start_line": start,
                "end_line": end,
            }
        )
    return PreparedRow(
        repository=repository,
        commit=commit,
        problem=problem,
        problem_decoded=decoded is not None,
        gold_context=gold_context,
        oracle_reads=oracle_reads,
        patch=str(row.get("patch") or ""),
        source=source,
        original_instance_id=original_instance_id,
        language=language,
        native=native_environment(source, original_instance_id, repository),
    )


@dataclass(frozen=True)
class PreparedDataset:
    """A ContextBench parquet's rows and the tasks generation prepares from them."""

    # Rows by instance ID, in file order.
    rows: dict[str, dict[str, Any]]
    prepared: dict[str, PreparedRow]
    # The rows that cannot become tasks, with the reason.
    failures: list[dict[str, str]]
    # The corrections applied to prepared rows.
    corrections: list[dict[str, Any]]


def load_prepared(path: Path) -> PreparedDataset:
    """Read a ContextBench parquet and prepare every row, after its corrections."""
    try:
        table = parquet.read_table(path)
    except (OSError, ValueError) as error:
        raise RuntimeError(
            f"could not read ContextBench parquet {path}: {error}"
        ) from error
    missing = sorted(_REQUIRED_COLUMNS - set(table.column_names))
    if missing:
        raise ValueError(
            "ContextBench parquet is missing required columns: " + ", ".join(missing)
        )
    rows: dict[str, dict[str, Any]] = {}
    for row in table.to_pylist():
        instance_id = str(row.get("instance_id") or "").strip()
        if not instance_id:
            raise ValueError("ContextBench row has no instance ID")
        if instance_id in rows:
            raise ValueError(f"duplicate ContextBench instance ID: {instance_id}")
        rows[instance_id] = row

    corrections = load_corrections()
    prepared: dict[str, PreparedRow] = {}
    failures: list[dict[str, str]] = []
    applied: list[dict[str, Any]] = []
    for instance_id, row in rows.items():
        own = [item for item in corrections if item.instance_id == instance_id]
        try:
            prepared[instance_id] = prepare_row(_corrected(row, own))
        except (TypeError, ValueError) as error:
            failures.append({"instance_id": instance_id, "error": str(error)})
            continue
        applied.extend(
            {
                "instance_id": item.instance_id,
                "field": item.field,
                "source": item.source,
                "reason": item.reason,
            }
            for item in own
        )
    return PreparedDataset(rows, prepared, failures, applied)


def write_attribution_config(
    tests_dir: Path, repository_roots: tuple[str, ...]
) -> None:
    """Write the verifier's attribution input: where the agent saw the repository."""
    _write_text(
        tests_dir / "attribution.json",
        json.dumps({"repository_roots": list(repository_roots)}, indent=2) + "\n",
    )


def _gold_payload(instance_id: str, prepared: PreparedRow) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "base_commit": prepared.commit,
        "repository": prepared.repository,
        "gold_context": prepared.gold_context,
        "contextbench_commit": CONTEXTBENCH_COMMIT,
    }


_BASELINE_INDEX = ".git/contextbench-baseline-index"
_BASELINE_TREE = ".git/contextbench-baseline-tree"
# Dockerfile RUN continuation lines, run in the repository, that record the tree
# the image leaves and an index holding it: the baseline of `collect_command`.
RECORD_BASELINE = f"""\
    && cp .git/index {_BASELINE_INDEX} \\
    && GIT_INDEX_FILE={_BASELINE_INDEX} git add -A \\
    && GIT_INDEX_FILE={_BASELINE_INDEX} git write-tree \\
        > {_BASELINE_TREE}"""


def collect_command(commit: str, repository: str = "/workspace") -> str:
    """Export the agent's changes against the tree the agent image started from.

    That baseline is the base commit plus the native image's build-time edits
    to tracked files (environment/Dockerfile). The changes are staged in a copy
    of the image's baseline index under the image's stat checks, so neither
    the agent's index nor a change to those settings affects the patch. The
    parity tasks (parity/prepare.py) run the same command in their own
    workspace, whose image records the same baseline files.

    The error file holds `collect_incomplete` until the patch is complete. A
    collection that Harbor's timeout interrupts therefore reads as failed: the
    command keeps running in the container while Harbor copies the artifacts.
    """
    artifacts = "/logs/artifacts"
    error = f"{artifacts}/contextbench-collect-error.txt"
    patch = f"{artifacts}/contextbench-model.patch"
    index = ".git/contextbench-collect-index"
    git = f"GIT_INDEX_FILE={index} git"
    return (
        f"mkdir -p {artifacts}; "
        f"printf '%s\\n' collect_incomplete > {error}; "
        f"rm -f {patch}; "
        f"cd {shlex.quote(repository)}; "
        f"baseline=$(cat {_BASELINE_TREE} 2>/dev/null); "
        f"if git cat-file -e {commit}^{{commit}} "
        '&& git cat-file -e "$baseline^{tree}" '
        f"&& cp {_BASELINE_INDEX} {index} "
        f"&& {git} -c core.checkStat=minimal -c core.trustctime=false add -A "
        f'&& {git} diff --cached --binary "$baseline" -- . > {patch}.partial '
        f"&& mv {patch}.partial {patch}; "
        f"then : > {error}; "
        f"else rm -f {patch}.partial; printf '%s\\n' git_state_invalid > {error}; "
        f"fi; rm -f {index}"
    )


class ContextBenchAdapter:
    """Generate self-contained Harbor tasks from ContextBench parquet rows."""

    def __init__(self, dataset_path: Path | str, output_dir: Path | str) -> None:
        self.dataset_path = Path(dataset_path).expanduser().resolve()
        self.output_dir = Path(output_dir).expanduser().resolve()
        if not self.dataset_path.is_file():
            raise ValueError(f"dataset does not exist: {self.dataset_path}")
        self.dataset_sha256 = sha256_file(self.dataset_path)
        self.dataset_name = _dataset_label(self.dataset_sha256)

    @staticmethod
    def _select_ids(
        rows: dict[str, dict[str, Any]],
        task_ids: list[str] | None,
        limit: int | None,
    ) -> list[str]:
        if task_ids is not None:
            if len(task_ids) != len(set(task_ids)):
                raise ValueError("--task-ids contains duplicate IDs")
            missing = [task_id for task_id in task_ids if task_id not in rows]
            if missing:
                raise ValueError(
                    "requested ContextBench IDs were not found: " + ", ".join(missing)
                )
            selected_ids = task_ids
        else:
            selected_ids = list(rows)
        if limit is not None:
            selected_ids = selected_ids[:limit]
        if not selected_ids:
            raise ValueError("no ContextBench tasks selected")
        return selected_ids

    def _validate_task_destinations(
        self,
        task_names: list[str],
        *,
        overwrite: bool,
    ) -> None:
        for task_name in task_names:
            task_dir = self.output_dir / task_name
            if (task_dir.exists() or task_dir.is_symlink()) and not overwrite:
                raise RuntimeError(
                    f"selected ContextBench task already exists: {task_dir}; "
                    "regenerate it with --overwrite"
                )

    def _report(
        self, dataset: PreparedDataset, task_names: dict[str, str]
    ) -> dict[str, Any]:
        """Describe every dataset with tasks in the output directory.

        Each dataset's entry covers the whole dataset. Its `tasks` lists the
        task directories present in the output, so regenerating a subset keeps
        the others, and a task deleted from disk drops out.
        """
        path = self.output_dir / REPORT_FILENAME
        datasets: dict[str, Any] = {}
        if path.is_file():
            try:
                datasets = json.loads(path.read_text(encoding="utf-8"))["datasets"]
                for entry in datasets.values():
                    entry["tasks"] = {
                        instance_id: task_name
                        for instance_id, task_name in entry["tasks"].items()
                        if (self.output_dir / task_name).is_dir()
                    }
            except (AttributeError, KeyError, TypeError, ValueError) as error:
                raise RuntimeError(
                    f"existing generation report is not valid: {path}"
                ) from error
        previous_tasks = datasets.get(self.dataset_name, {}).get("tasks", {})
        datasets[self.dataset_name] = {
            "dataset_file": self.dataset_path.name,
            "dataset_sha256": self.dataset_sha256,
            "rows": len(dataset.rows),
            "invalid_rows": dataset.failures,
            "corrections": dataset.corrections,
            "decoded_problem_statements": sorted(
                instance_id
                for instance_id, prepared in dataset.prepared.items()
                if prepared.problem_decoded
            ),
            "tasks": dict(sorted({**previous_tasks, **task_names}.items())),
        }
        return {
            "contextbench_commit": CONTEXTBENCH_COMMIT,
            "datasets": {
                name: entry
                for name, entry in sorted(datasets.items())
                if entry["tasks"]
            },
        }

    def _publish(self, staging: Path, entries: list[Path]) -> None:
        """Move staged entries into place, restoring the originals on any failure."""
        replaced_dir = staging / "replaced"
        replaced_dir.mkdir()
        replaced: list[str] = []
        published: list[Path] = []
        try:
            for entry in entries:
                destination = self.output_dir / entry.name
                if destination.exists() or destination.is_symlink():
                    destination.rename(replaced_dir / entry.name)
                    replaced.append(entry.name)
                entry.rename(destination)
                published.append(entry)
        except BaseException:
            for entry in reversed(published):
                (self.output_dir / entry.name).rename(entry)
            for name in reversed(replaced):
                (replaced_dir / name).rename(self.output_dir / name)
            raise

    def run(
        self,
        *,
        task_ids: list[str] | None = None,
        limit: int | None = None,
        overwrite: bool = False,
        skip_invalid_source_rows: bool = False,
    ) -> list[Path]:
        dataset = load_prepared(self.dataset_path)
        selected_ids = self._select_ids(dataset.rows, task_ids, limit)
        selected_failures = [
            failure
            for failure in dataset.failures
            if failure["instance_id"] in selected_ids
        ]
        if selected_failures and not skip_invalid_source_rows:
            raise InvalidDatasetRowsError(selected_failures)
        task_names = {
            instance_id: task_directory_name(self.dataset_name, instance_id)
            for instance_id in selected_ids
            if instance_id in dataset.prepared
        }
        if not task_names:
            raise InvalidDatasetRowsError(selected_failures)
        _require_image_digests(
            {GIT_IMAGE, VERIFIER_IMAGE}
            | {dataset.prepared[instance_id].native.image for instance_id in task_names}
        )
        self._validate_task_destinations(list(task_names.values()), overwrite=overwrite)
        report = self._report(dataset, task_names)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=".contextbench-staging-", dir=self.output_dir)
        )
        try:
            (staging / "tasks").mkdir()
            for instance_id, task_name in task_names.items():
                self._write_task(
                    staging / "tasks" / task_name,
                    instance_id,
                    dataset.prepared[instance_id],
                )
            shutil.copy2(PACKAGE_DIR / "aggregation.py", staging / "metric.py")
            _write_text(
                staging / REPORT_FILENAME,
                json.dumps(report, indent=2, sort_keys=True) + "\n",
            )
            self._publish(
                staging,
                [
                    *(staging / "tasks" / name for name in task_names.values()),
                    staging / "metric.py",
                    staging / REPORT_FILENAME,
                ],
            )
        finally:
            shutil.rmtree(staging)
        return [self.output_dir / task_name for task_name in task_names.values()]

    def _write_task(
        self,
        task_dir: Path,
        instance_id: str,
        prepared: PreparedRow,
    ) -> None:
        environment_dir = task_dir / "environment"
        solution_dir = task_dir / "solution"
        tests_dir = task_dir / "tests"
        verifier_package = tests_dir / "harbor_contextbench"
        environment_dir.mkdir(parents=True)
        solution_dir.mkdir()
        verifier_package.mkdir(parents=True)

        replacements = {
            "__TASK_NAME__": f"contextbench/{task_dir.name}",
            "__INSTANCE_ID__": _toml_string(instance_id),
            "__ORIGINAL_INSTANCE_ID__": _toml_string(prepared.original_instance_id),
            "__REPOSITORY__": _toml_string(prepared.repository),
            "__BASE_COMMIT__": _toml_string(prepared.commit),
            "__SOURCE__": _toml_string(prepared.source),
            "__LANGUAGE__": _toml_string(prepared.language),
            "__NATIVE_IMAGE__": _toml_string(prepared.native.image),
            "__NATIVE_REPOSITORY_PATH__": _toml_string(prepared.native.repository_path),
            "__DATASET_NAME__": _toml_string(self.dataset_name),
            "__DATASET_SHA256__": _toml_string(self.dataset_sha256),
            "__CONTEXTBENCH_COMMIT__": _toml_string(CONTEXTBENCH_COMMIT),
            "__COLLECT_COMMAND__": _toml_string(collect_command(prepared.commit)),
        }
        _write_text(
            task_dir / "task.toml",
            _render(TEMPLATE_DIR / "task.toml", replacements),
        )
        _write_text(
            task_dir / "instruction.md",
            _render(
                TEMPLATE_DIR / "instruction.md",
                {"__PROBLEM_STATEMENT__": prepared.problem},
            ),
        )
        _write_text(
            environment_dir / "Dockerfile",
            _agent_environment_dockerfile(
                TEMPLATE_DIR / "environment/Dockerfile",
                prepared,
            ),
        )
        _write_text(
            tests_dir / "Dockerfile",
            _verifier_dockerfile(
                TEMPLATE_DIR / "tests/Dockerfile", prepared.repository, prepared.commit
            ),
        )

        for filename in ("test.sh", "score.py"):
            shutil.copy2(TEMPLATE_DIR / "tests" / filename, tests_dir / filename)
        for filename in _VERIFIER_MODULES:
            destination = verifier_package / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PACKAGE_DIR / filename, destination)
        _write_text(
            verifier_package / "__init__.py",
            '"""ContextBench verifier code embedded in a Harbor task."""\n',
        )
        shutil.copytree(
            VENDOR_DIR,
            verifier_package / "vendor",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        _write_text(
            tests_dir / "gold.json",
            json.dumps(_gold_payload(instance_id, prepared), indent=2, sort_keys=True)
            + "\n",
        )
        # The agent sees the repository at both paths: /workspace links to
        # the native one (environment/Dockerfile).
        write_attribution_config(
            tests_dir, ("/workspace", prepared.native.repository_path)
        )
        shutil.copy2(TEMPLATE_DIR / "solution/solve.sh", solution_dir / "solve.sh")
        _write_text(
            solution_dir / "oracle-trajectory.json",
            json.dumps(
                oracle_trajectory(instance_id, prepared.oracle_reads),
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        _write_text(solution_dir / "solution.patch", prepared.patch)
