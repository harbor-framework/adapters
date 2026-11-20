"""Report every known upstream data defect in the pinned ContextBench datasets.

For each defect class, the report lists the affected instances of every pinned
dataset and says how the adapter handles them. It needs the network: it fetches
each base commit's tree and gold files from GitHub with a shallow blobless
fetch, and the source benchmarks' datasets from Hugging Face at pinned
revisions. It fails rather than guess when a fetch fails.

Usage (from src/contextbench):
    uv run python scripts/upstream_defects.py
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import dataclasses
import functools
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pyarrow import parquet

from contextbench.adapter import (
    CONTEXTBENCH_COMMIT,
    DATASETS,
    PreparedRow,
    decoded_json_string,
    download_dataset,
    load_corrections,
    load_prepared,
    oracle_trajectory,
    prepare_row,
    sha256_file,
    task_directory_name,
)
from contextbench.attribution.receipts import split_lines
from contextbench.attribution.trajectory import project_atif
from contextbench.vendor.contextbench_source.contextbench.parsers.gold import Gold
from contextbench.vendor_api import normalize_gold_path

OUTPUT = Path(__file__).resolve().parent / "output/upstream-defects.json"
SOURCE_CACHE = Path.home() / ".cache/harbor/contextbench/sources"
REFERENCE = "verified"


@dataclasses.dataclass(frozen=True)
class SourceFile:
    """A source benchmark's dataset file on Hugging Face at a pinned revision."""

    dataset: str
    revision: str
    file: str
    sha256: str


SWE_BENCH_VERIFIED = SourceFile(
    "princeton-nlp/SWE-bench_Verified",
    "c104f840cc67f8b6eec6f759ebc8b2693d585d4a",
    "data/test-00000-of-00001.parquet",
    "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd",
)
SWE_POLYBENCH = SourceFile(
    "AmazonScience/SWE-PolyBench",
    "d56445f9940eae4e9d2974ec66820c2f1d7754e6",
    "test.csv",
    "17ad661b20e9af1e2067fbbc2e2658a21137d56693570d1d07f966d8bc0408b7",
)
# The 731-task release ContextBench draws from, kept unchanged as the `v1`
# configuration of SWE-bench Pro V2.
SWE_BENCH_PRO_V1 = SourceFile(
    "ScaleAI/SWE-bench_Pro",
    "2d52cb3df914a3fcf80c7f66738b3a88ae37fc50",
    "data/v1/test-00000-of-00001.parquet",
    "c8cd7115496ad4e9a8b21d088cef576a65bf821bb542b24336f13f714cef13f8",
)
SWE_BENCH_PRO_V2 = SourceFile(
    "ScaleAI/SWE-bench_Pro",
    "2d52cb3df914a3fcf80c7f66738b3a88ae37fc50",
    "data/default/test-00000-of-00001.parquet",
    "1067f72c1f43bbc578276888625db3b836cebb535546c9eaf824c5d5dd104a7f",
)
SOURCE_FILES = (SWE_BENCH_VERIFIED, SWE_POLYBENCH, SWE_BENCH_PRO_V1, SWE_BENCH_PRO_V2)
# The release whose statements each family's rows copy. Multi-SWE-bench rows
# copy the pull request title and body; its dataset is 1.5 GB of JSONL, so this
# report does not check them.
STATEMENT_SOURCES = {
    "Verified": SWE_BENCH_VERIFIED,
    "Poly": SWE_POLYBENCH,
    "Pro": SWE_BENCH_PRO_V1,
}
# Statements the Pro check flags that belong to their instance on review.
REVIEWED_STATEMENTS = {
    "SWE-Bench-Pro__python__maintenance__bugfix__450d75e0": (
        "kept: the statement is the BSD uptime issue that the patch fixes, and "
        "SWE-bench Pro v1's requirements ask for an uptime_seconds fact on BSD "
        "hosts"
    ),
}
# A base commit's entry types (blob, tree or commit) and its gold file bytes.
Snapshot = tuple[dict[str, str], dict[str, bytes]]


@dataclasses.dataclass(frozen=True)
class Dataset:
    rows: dict[str, dict[str, Any]]
    columns: frozenset[str]
    # Rows as generation prepares them, after the checked-in corrections.
    prepared: dict[str, PreparedRow]
    corrections: list[dict[str, Any]]
    # Rows that are malformed as ContextBench publishes them, with the reason.
    upstream_failures: dict[str, str]


@functools.cache
def _source_rows(source: SourceFile) -> dict[str, dict[str, Any]]:
    """Return a source file's rows by instance_id, downloading it once."""
    path = SOURCE_CACHE / source.dataset / source.revision / source.file
    if not path.is_file() or sha256_file(path) != source.sha256:
        url = (
            f"https://huggingface.co/datasets/{source.dataset}/resolve/"
            f"{source.revision}/{source.file}"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=300) as response:
            path.write_bytes(response.read())
        if sha256_file(path) != source.sha256:
            path.unlink()
            raise RuntimeError(f"{url} does not have SHA-256 {source.sha256}")
    if path.suffix == ".csv":
        csv.field_size_limit(sys.maxsize)
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
    else:
        rows = parquet.read_table(path).to_pylist()
    return {str(row["instance_id"]): row for row in rows}


def _load(name: str) -> Dataset:
    loaded = load_prepared(download_dataset(DATASETS[name]))
    upstream_failures = {}
    for key, row in loaded.rows.items():
        try:
            prepare_row(row)
        except (TypeError, ValueError) as error:
            upstream_failures[key] = str(error)
    # Every row holds every column of the parquet.
    columns = frozenset(next(iter(loaded.rows.values())))
    return Dataset(
        loaded.rows, columns, loaded.prepared, loaded.corrections, upstream_failures
    )


def _defect(
    description: str,
    handling: str,
    instances: dict[str, list[Any]],
    **details: Any,
) -> dict[str, Any]:
    return {
        "description": description,
        "adapter_handling": handling,
        "counts": {name: len(items) for name, items in instances.items()},
        **details,
        "instances": instances,
    }


def _statement(row: dict[str, Any]) -> str:
    text = str(row.get("problem_statement") or "")
    decoded = decoded_json_string(text)
    return text if decoded is None else decoded


# Problem statements


def statement_provenance(
    rows: dict[str, dict[str, Any]], source_statements: dict[str, str]
) -> dict[str, Any]:
    """Compare each row's statement with its source's for the same instance.

    `rows` maps ContextBench instance IDs to rows; `source_statements` maps the
    source benchmark's instance IDs (`original_inst_id`) to their statements.
    Statements must be equal as stored.
    """
    identical = 0
    different: list[str] = []
    missing: list[str] = []
    for instance_id, row in sorted(rows.items()):
        expected = source_statements.get(row["original_inst_id"])
        if expected is None:
            missing.append(instance_id)
        elif row["problem_statement"] == expected:
            identical += 1
        else:
            different.append(instance_id)
    return {
        "rows": len(rows),
        "identical": identical,
        "different": different,
        "missing_from_source": missing,
    }


def _terms(text: str) -> Counter[str]:
    return Counter(re.findall(r"[a-z][a-z0-9_]{2,}", text.lower()))


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    return sum(left.get(term, 0) * weight for term, weight in right.items())


def misplaced_statements(
    statements: dict[str, str],
    references: dict[str, str],
    repositories: dict[str, str],
) -> list[dict[str, Any]]:
    """Return the statements that read like another instance's.

    `references` describes each instance independently of its statement, and
    `repositories` names each instance's repository; all three are keyed by
    instance. Texts are compared by TF-IDF cosine similarity over the
    references. A statement is flagged when its own reference is less than half
    as similar to it as the most similar reference of another instance from the
    same repository.
    """
    terms = {key: _terms(text) for key, text in references.items()}
    frequency = Counter(term for counts in terms.values() for term in counts)

    def vector(counts: Counter[str]) -> dict[str, float]:
        weights = {
            term: (1 + math.log(count))
            * math.log(1 + len(terms) / (1 + frequency[term]))
            for term, count in counts.items()
        }
        norm = math.sqrt(sum(weight * weight for weight in weights.values())) or 1
        return {term: weight / norm for term, weight in weights.items()}

    vectors = {key: vector(counts) for key, counts in terms.items()}
    flagged = []
    for key, statement in sorted(statements.items()):
        if key not in vectors:
            continue
        query = vector(_terms(statement))
        others = [
            (_cosine(query, vectors[other]), other)
            for other in vectors
            if other != key and repositories[other] == repositories[key]
        ]
        if not others:
            continue
        own = _cosine(query, vectors[key])
        best, best_match = max(others)
        if own < best / 2:
            flagged.append(
                {
                    "instance": key,
                    "own_similarity": round(own, 3),
                    "best_similarity": round(best, 3),
                    "best_match": best_match,
                }
            )
    return flagged


def _checked_corrections(
    datasets: dict[str, Dataset], rows: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Check each correction against the dataset rows and its named source."""
    sources = {(item.dataset, item.revision, item.file): item for item in SOURCE_FILES}
    checks = {}
    for correction in load_corrections():
        named = correction.source
        source = sources[(named["dataset"], named["revision"], named["file"])]
        value = _source_rows(source)[named["instance_id"]][correction.field]
        checks[correction.instance_id] = {
            "instance_id": correction.instance_id,
            "field": correction.field,
            "applied_in": sorted(
                name
                for name, data in datasets.items()
                for item in data.corrections
                if item["instance_id"] == correction.instance_id
            ),
            "source_instance_is_original_inst_id": (
                rows[correction.instance_id]["original_inst_id"] == named["instance_id"]
            ),
            "value_matches_source": value == correction.value,
        }
    return checks


def _wrong_statements(
    datasets: dict[str, Dataset],
    union: dict[str, dict[str, Any]],
    checks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    provenance = {
        family: {
            "source": dataclasses.asdict(source),
            **statement_provenance(
                {key: row for key, row in union.items() if row["source"] == family},
                {
                    key: row["problem_statement"]
                    for key, row in _source_rows(source).items()
                },
            ),
        }
        for family, source in STATEMENT_SOURCES.items()
    }

    # SWE-bench Pro v1 also describes each instance by its requirements and
    # interface, written independently of the statement.
    pro_v1 = _source_rows(SWE_BENCH_PRO_V1)
    pro_rows = {
        row["original_inst_id"]: key
        for key, row in union.items()
        if row["source"] == "Pro"
    }
    candidates = []
    for item in misplaced_statements(
        {original: _statement(union[key]) for original, key in pro_rows.items()},
        {
            key: f"{row['requirements'] or ''}\n{row['interface'] or ''}"
            for key, row in pro_v1.items()
        },
        {key: str(row["repo"]) for key, row in pro_v1.items()},
    ):
        instance_id = pro_rows[item["instance"]]
        candidates.append(
            {
                "instance_id": instance_id,
                "original_inst_id": item["instance"],
                "own_similarity": item["own_similarity"],
                "best_similarity": item["best_similarity"],
                "best_match": item["best_match"],
                "verdict": (
                    "corrected"
                    if instance_id in checks
                    else REVIEWED_STATEMENTS.get(instance_id, "unreviewed")
                ),
            }
        )

    return _defect(
        "Rows whose problem statement describes a different change than the "
        "instance's gold patch. Each family's statements were compared with the "
        "source release they copy, and SWE-bench Pro statements also with the "
        "requirements and interface that release gives for the same instance.",
        "Corrected at generation from corrections.json, which names the source "
        "and revision of each corrected value; the generation report lists every "
        "applied correction.",
        {
            name: sorted(
                item["instance_id"]
                for item in data.corrections
                if item["instance_id"] in union
            )
            for name, data in datasets.items()
        },
        provenance=provenance,
        not_checked={
            "Multi": "Multi-SWE-bench's dataset is 1.5 GB of JSONL",
        },
        pro_requirements_check=candidates,
        corrections=[check for key, check in checks.items() if key in union],
    )


def _json_quoted(
    datasets: dict[str, Dataset], union: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    instances = {
        name: sorted(
            key
            for key in data.prepared
            if decoded_json_string(str(data.rows[key]["problem_statement"] or ""))
            is not None
        )
        for name, data in datasets.items()
    }
    quoted_ids = sorted({key for keys in instances.values() for key in keys})
    quoted = [union[key] for key in quoted_ids]
    sources = {}
    for family, source in STATEMENT_SOURCES.items():
        rows = [row for row in quoted if row["source"] == family]
        if rows:
            statements = _source_rows(source)
            sources[family] = {
                "rows": len(rows),
                "stored_identically": sum(
                    statements[row["original_inst_id"]]["problem_statement"]
                    == row["problem_statement"]
                    for row in rows
                ),
            }
    pro_v2 = _source_rows(SWE_BENCH_PRO_V2)
    in_v2 = [
        (_statement(row), pro_v2[row["original_inst_id"]]["problem_statement"])
        for row in quoted
        if row["source"] == "Pro" and row["original_inst_id"] in pro_v2
    ]
    return _defect(
        "Problem statements stored as a JSON string literal, so the text shows "
        "its quotes and \\n escapes. The source release stores them the same "
        "way; SWE-bench Pro V2 stores none of them quoted.",
        "Decoded at generation when the whole value is one JSON string literal "
        "(adapter.decoded_json_string); the generation report lists the decoded "
        "rows. A corrected statement is replaced instead.",
        instances,
        source_release=sources,
        swe_bench_pro_v2={
            "rows": len(in_v2),
            "equal_to_the_decoded_text": sum(ours == v2 for ours, v2 in in_v2),
            "json_quoted": sum(decoded_json_string(v2) is not None for _, v2 in in_v2),
        },
    )


# Rows and dataset agreement


def _malformed(
    datasets: dict[str, Dataset], checks: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    instances = {
        name: [
            {"instance_id": key, "error": error, "restored": key in data.prepared}
            for key, error in data.upstream_failures.items()
        ]
        for name, data in datasets.items()
    }
    malformed = {key for data in datasets.values() for key in data.upstream_failures}
    return _defect(
        "Rows without a problem statement or gold context.",
        "corrections.json restores a missing problem statement from the source "
        "release the row copies, and the generation report lists the "
        "restoration. A row that cannot be restored aborts generation when it "
        "is selected; with --skip-invalid-source-rows it is skipped, and the "
        "generation report lists it either way.",
        instances,
        restored=[check for key, check in checks.items() if key in malformed],
        not_restorable=(
            "Gold context is ContextBench's own annotation, and no source "
            "benchmark has it. These rows' gold context is empty in every "
            "published ContextBench revision: the pinned commit, which is still "
            "the latest on GitHub, and every revision of the Hugging Face "
            "dataset Contextbench/ContextBench."
        ),
    )


def _truncated_repo(datasets: dict[str, Dataset]) -> dict[str, Any]:
    instances: dict[str, list[Any]] = {}
    repositories: dict[str, set[str]] = defaultdict(set)
    for name, data in datasets.items():
        instances[name] = []
        for key, prepared in sorted(data.prepared.items()):
            repo = str(data.rows[key].get("repo") or "")
            # The splits' `repo` holds the name alone.
            expected = (
                prepared.repository
                if "/" in repo
                else prepared.repository.split("/", 1)[1]
            )
            if repo != expected:
                instances[name].append(key)
                repositories[repo].add(prepared.repository)
    return _defect(
        "Multi-SWE-bench rows whose `repo` column is cut at the first hyphen of "
        "the repository name, for example fasterxml/jackson for "
        "fasterxml/jackson-core.",
        "The adapter ignores `repo`. It takes the repository from `repo_url`, "
        "else from `original_inst_id`, and rejects rows where the two disagree.",
        instances,
        repositories={
            repo: sorted(names) for repo, names in sorted(repositories.items())
        },
    )


def _value(column: str, value: Any) -> Any:
    # Gold context is JSON text; formatting differences are not disagreements.
    return json.loads(value) if column == "gold_context" and value else value


def _scored_gold(row: dict[str, Any]) -> tuple[Any, Any]:
    """Return the gold files and line spans the evaluator scores against."""
    gold = Gold({"gold_ctx": _value("gold_context", row["gold_context"])})
    return gold.files(), gold.line_spans_init()


def _differing_columns(reference: Dataset, other: Dataset) -> dict[str, list[str]]:
    """Return the columns that differ for each instance whose rows differ."""
    columns = sorted((reference.columns & other.columns) - {"instance_id"})
    differences = {}
    for key in sorted(reference.rows.keys() & other.rows.keys()):
        left, right = reference.rows[key], other.rows[key]
        if fields := [
            column
            for column in columns
            if _value(column, left[column]) != _value(column, right[column])
        ]:
            differences[key] = fields
    return differences


def _split_disagreements(datasets: dict[str, Dataset]) -> dict[str, Any]:
    reference = datasets[REFERENCE]
    split_ids = set(datasets["verified-test"].rows) | set(
        datasets["verified-train"].rows
    )
    differences = {
        name: _differing_columns(reference, data)
        for name, data in datasets.items()
        if name != REFERENCE
    }
    return _defect(
        f"`verified` is the union of the two splits and a subset of `full`, but "
        f"the rows for one instance are not always equal. Rows are compared with "
        f"`{REFERENCE}` on their shared columns.",
        "Each dataset keeps its own content, and every task name includes the "
        "dataset, so one task name never maps to two contents.",
        {name: sorted(rows) for name, rows in differences.items()},
        verified_is_the_union_of_the_splits=split_ids == set(reference.rows),
        verified_is_a_subset_of_full=set(reference.rows) <= set(datasets["full"].rows),
        differences_by_column={
            name: dict(sorted(Counter(f for v in rows.values() for f in v).items()))
            for name, rows in differences.items()
        },
        # Rows whose gold differs even after `Gold` normalizes the paths.
        different_scored_gold={
            name: [
                key
                for key, fields in rows.items()
                if "gold_context" in fields
                and _scored_gold(reference.rows[key])
                != _scored_gold(datasets[name].rows[key])
            ]
            for name, rows in differences.items()
        },
    )


# Gold context against the base commit


def _git(directory: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(directory), *arguments], check=True, capture_output=True
    ).stdout


def _snapshot(repository: str, commit: str, paths: set[str]) -> Snapshot:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _git(root, "init", "-q")
        _git(root, "remote", "add", "origin", f"https://github.com/{repository}.git")
        _git(root, "config", "remote.origin.promisor", "true")
        _git(root, "config", "remote.origin.partialclonefilter", "blob:none")
        for attempt in range(4):
            try:
                _git(
                    root,
                    "fetch",
                    "-q",
                    "--depth=1",
                    "--filter=blob:none",
                    "origin",
                    commit,
                )
                break
            except subprocess.CalledProcessError:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        types = {}
        for entry in _git(root, "ls-tree", "-r", "-t", "-z", commit).split(b"\0"):
            if entry:
                metadata, path = entry.split(b"\t", 1)
                types[os.fsdecode(path)] = metadata.split()[1].decode()
        contents = {
            path: _git(root, "cat-file", "blob", f"{commit}:{path}")
            for path in sorted(paths)
            if types.get(path) == "blob"
        }
    return types, contents


def _snapshots(
    datasets: dict[str, Dataset], workers: int
) -> dict[tuple[str, str], Snapshot]:
    paths: dict[tuple[str, str], set[str]] = defaultdict(set)
    for data in datasets.values():
        for prepared in data.prepared.values():
            key = (prepared.repository, prepared.commit)
            paths[key].update(read.path for read in prepared.oracle_reads)
    keys = sorted(paths)
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        return dict(
            zip(
                keys,
                pool.map(lambda key: _snapshot(*key, paths[key]), keys),
                strict=True,
            )
        )


def _uncredited_gold_files(
    instance_id: str, prepared: PreparedRow, snapshot: Snapshot
) -> list[str]:
    """Return the gold files the oracle trajectory earns no credit for.

    The verifier rewards file coverage against `Gold(gold.json).files()`, and
    the oracle reads every gold range. Every missed file must be absent at the
    base commit; any other miss is an adapter defect, so it raises.
    """
    types, contents = snapshot
    trajectory = oracle_trajectory(instance_id, prepared.oracle_reads)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        # The verifier resolves `/workspace/a/b` to exactly `a/b`
        # (attribution.receipts), so that entry decides credit.
        for read in prepared.oracle_reads:
            kind = types.get(read.path)
            if kind in {"tree", "commit"}:
                (root / read.path).mkdir(parents=True, exist_ok=True)
            elif kind == "blob":
                (root / read.path).parent.mkdir(parents=True, exist_ok=True)
                (root / read.path).write_bytes(contents.get(read.path, b""))
        prediction, _ = project_atif(trajectory, root, roots=("/workspace",))
    credited = set(prediction["pred_files"])
    uncredited = [
        path
        for path in Gold({"gold_ctx": prepared.gold_context}).files()
        if path not in credited
    ]
    if present := [path for path in uncredited if types.get(path) == "blob"]:
        raise RuntimeError(f"{instance_id}: the oracle earns no credit for {present}")
    return uncredited


def _dotted_path(raw_path: str) -> str | None:
    """Return the dotfile a repository-relative gold path names, if the gold
    parser strips its dot, else None."""
    value = raw_path.replace("\\", "/")
    if value.startswith("/"):
        return None
    while value.startswith("./"):
        value = value[2:]
    return None if normalize_gold_path(raw_path) == value else value


def _unmatchable_files(
    instance_id: str, prepared: PreparedRow, snapshot: Snapshot
) -> list[dict[str, Any]]:
    types, _ = snapshot
    raw_files: dict[str, set[str]] = defaultdict(set)
    for read, annotation in zip(
        prepared.oracle_reads, prepared.gold_context, strict=True
    ):
        raw_files[read.path].add(annotation["file"])
    files = []
    for path in _uncredited_gold_files(instance_id, prepared, snapshot):
        raw = sorted(raw_files[path])
        dotted = {_dotted_path(item) for item in raw}
        mangled = any(types.get(item) == "blob" for item in dotted if item)
        reason = "gold_path_mangled_upstream" if mangled else "absent_at_base_commit"
        files.append({"file": path, "raw_files": raw, "reason": reason})
    return files


def _unmatchable_gold(
    datasets: dict[str, Dataset], snapshots: dict[tuple[str, str], Snapshot]
) -> dict[str, Any]:
    instances: dict[str, list[Any]] = {}
    for name, data in datasets.items():
        instances[name] = []
        for key, prepared in sorted(data.prepared.items()):
            snapshot = snapshots[(prepared.repository, prepared.commit)]
            if files := _unmatchable_files(key, prepared, snapshot):
                gold_files = len(Gold({"gold_ctx": prepared.gold_context}).files())
                instances[name].append(
                    {
                        "instance_id": key,
                        "task_name": f"contextbench/{task_directory_name(name, key)}",
                        "oracle_maximum": round(1 - len(files) / gold_files, 6),
                        "files": files,
                    }
                )
    return _defect(
        "Gold files, as the verifier scores them, that no prediction can match, "
        "so they cap the oracle's file coverage at `oracle_maximum`. "
        "`gold_path_mangled_upstream`: the annotation names an existing dotfile "
        "by a repository-relative path, and ContextBench's gold parser strips "
        'the dot with `lstrip("./")`, so `.github/x.yml` is scored as '
        "`github/x.yml`. `absent_at_base_commit`: the file does not exist at the "
        "base commit, such as a reproduction script the annotator wrote.",
        "Kept, as in native scoring: gold.json keeps the raw paths, and the "
        "verifier normalizes them once with ContextBench's parser, so these "
        "tasks cannot reach a reward of 1.0.",
        instances,
        files_by_reason={
            name: dict(
                sorted(
                    Counter(
                        file["reason"] for item in items for file in item["files"]
                    ).items()
                )
            )
            for name, items in instances.items()
        },
    )


def _past_eof(
    datasets: dict[str, Dataset], snapshots: dict[tuple[str, str], Snapshot]
) -> dict[str, Any]:
    instances: dict[str, list[Any]] = {}
    ranges: dict[str, Counter[str]] = {}
    starting_past_eof: dict[str, list[dict[str, Any]]] = {}
    for name, data in datasets.items():
        instances[name], ranges[name], starting_past_eof[name] = [], Counter(), []
        for key, prepared in sorted(data.prepared.items()):
            types, contents = snapshots[(prepared.repository, prepared.commit)]
            found = False
            for read in prepared.oracle_reads:
                if types.get(read.path) != "blob":
                    continue
                text = contents[read.path].decode("utf-8", errors="replace")
                lines = len(split_lines(text))
                if read.end_line <= lines:
                    continue
                found = True
                ranges[name]["ending_past_eof"] += 1
                ranges[name]["ending_one_line_past_eof"] += read.end_line == lines + 1
                if read.start_line > lines:
                    entry = {"instance_id": key, **dataclasses.asdict(read)}
                    starting_past_eof[name].append(entry | {"file_lines": lines})
            if found:
                instances[name].append(key)
    return _defect(
        "Gold ranges that end past the end of the file at the base commit, most "
        "by one line.",
        "The verifier clamps a read's declared range to the base file and drops "
        "a range that starts past its end (ATTRIBUTION.md), so the oracle's reads "
        "of these files are credited.",
        instances,
        ranges={name: dict(counts) for name, counts in ranges.items()},
        ranges_starting_past_eof=starting_past_eof,
    )


def _copies_context_into_testbed(dockerfile: str) -> bool:
    flags = re.MULTILINE | re.IGNORECASE
    return bool(
        re.search(r"^\s*WORKDIR\s+/testbed\s*$", dockerfile, flags)
        and re.search(r"^\s*COPY\s+\.\s+\.\s*$", dockerfile, flags)
    )


def _polybench_dockerfile(
    datasets: dict[str, Dataset], snapshots: dict[tuple[str, str], Snapshot]
) -> dict[str, Any]:
    dockerfiles = _source_rows(SWE_POLYBENCH)
    untracked: dict[str, list[Any]] = {}
    tracked: dict[str, list[str]] = {}
    for name, data in datasets.items():
        untracked[name], tracked[name] = [], []
        for key, prepared in sorted(data.prepared.items()):
            if prepared.source != "Poly" or not _copies_context_into_testbed(
                dockerfiles[prepared.original_instance_id]["Dockerfile"]
            ):
                continue
            types, _ = snapshots[(prepared.repository, prepared.commit)]
            found = tracked if types.get("Dockerfile") == "blob" else untracked
            found[name].append(key)
    return _defect(
        "SWE-PolyBench builds each image by copying the build context into "
        "/testbed (`WORKDIR /testbed`, `COPY . .`), so the checkout holds the "
        "Dockerfile the image was built from as an untracked /testbed/Dockerfile.",
        "Left out of the model patch. ContextBench's OpenHands runner exports "
        "with `git add -A` and `git diff --cached <base>`, so its patches add "
        "Dockerfile; the agent image lists the image's untracked files in "
        ".git/info/exclude, so the adapter's patches do not. Edit localization "
        "counts only deleted lines, so the added file changes no metric. Where "
        "the repository tracks a root Dockerfile "
        "(`tracked_dockerfile_overwritten`), the image overwrote it. The agent "
        "image keeps the overwritten file, as native agents see it, and records "
        "it in the model patch's baseline. Upstream's patch would then modify "
        "Dockerfile, and its deleted lines would count as edits outside the "
        "gold context; the adapter's does not.",
        untracked,
        tracked_dockerfile_overwritten=tracked,
    )


def build_report(workers: int) -> dict[str, Any]:
    datasets = {name: _load(name) for name in sorted(DATASETS)}
    rows = {key: row for data in datasets.values() for key, row in data.rows.items()}
    checks = _checked_corrections(datasets, rows)
    # The well-formed rows, as ContextBench publishes them.
    union: dict[str, dict[str, Any]] = {}
    for data in datasets.values():
        for key in data.prepared.keys() - data.upstream_failures.keys():
            statement = union.setdefault(key, data.rows[key])["problem_statement"]
            if statement != data.rows[key]["problem_statement"]:
                raise RuntimeError(f"datasets disagree on the statement of {key}")
    snapshots = _snapshots(datasets, workers)
    return {
        "contextbench_commit": CONTEXTBENCH_COMMIT,
        "datasets": {
            name: {"file": spec.filename, "sha256": spec.sha256, "rows": spec.rows}
            for name, spec in sorted(DATASETS.items())
        },
        "defects": {
            "malformed_rows": _malformed(datasets, checks),
            "truncated_repo_column": _truncated_repo(datasets),
            "split_disagrees_with_verified": _split_disagreements(datasets),
            "unmatchable_gold_files": _unmatchable_gold(datasets, snapshots),
            "gold_ranges_past_eof": _past_eof(datasets, snapshots),
            "wrong_problem_statements": _wrong_statements(datasets, union, checks),
            "json_quoted_problem_statements": _json_quoted(datasets, union),
            "polybench_untracked_dockerfile": _polybench_dockerfile(
                datasets, snapshots
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    report = build_report(args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, defect in report["defects"].items():
        print(f"{name}: {defect['counts']}")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
