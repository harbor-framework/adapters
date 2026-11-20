"""Calibrate the attribution rule against the vendored native oracle.

There is no external ground truth for trajectory attribution, so the one agent
for which an upstream-authored extraction definition exists, OpenHands,
supplies the calibration corpora. Every retained Harbor ATIF trajectory is
projected under the adapter's attribution rule, and the raw OpenHands log of
the same trial is extracted by the vendored pinned ContextBench extractor (the
test oracle). Two corpora are pinned: the 2026-08-21 single-run corpus in
``calibration-summary.json`` and the 30 trajectories of the three-run parity
experiment in ``calibration-summary-parity-runs.json``. Any change to the rule
surfaces as a difference from these summaries; ``parity/calibrate.py`` fetches
the inputs and checks them. See ``ATTRIBUTION.md``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyarrow import parquet

from contextbench.attribution import ATTRIBUTION_VERSION, project_atif
from contextbench.vendor.contextbench_source.contextbench.parsers.gold import Gold
from contextbench.vendor_api import extract_openhands_trajectory, resolve_repo_relpath
from parity.files import json_sha256, load_json
from parity.prepare import repository_roots

RETAINED_CORPUS = "2026-08-21-bedrock-sonnet-4-5"
SUMMARY_PATH = Path(__file__).with_name("calibration-summary.json")
PARITY_RUNS_SUMMARY_PATH = Path(__file__).with_name(
    "calibration-summary-parity-runs.json"
)


@dataclass(frozen=True)
class Trajectory:
    """One Harbor trial: its ATIF trajectory and its raw OpenHands log."""

    label: str
    instance_id: str
    atif: Path
    native: Path
    # The parity task: repository, base_commit, directory and workspace.
    task: dict[str, Any]


@dataclass(frozen=True)
class Corpus:
    name: str
    trajectories: list[Trajectory]
    gold_files: dict[str, frozenset[str]]


def _gold_files(subset: Path) -> dict[str, frozenset[str]]:
    """Read each task's gold files, normalized by ContextBench's own parser."""
    return {
        str(row["instance_id"]): frozenset(
            Gold({"gold_ctx": json.loads(row["gold_context"])}).files()
        )
        for row in parquet.read_table(subset).to_pylist()
    }


def worktree(
    repository_cache: Path,
    worktree_root: Path,
    repository: str,
    commit: str,
    directory: str,
) -> Path:
    """Return a detached worktree of `owner/repo` at `commit` under `worktree_root`.

    `repository_cache` holds one clone per repository, as `calibrate.py`
    fetches them: `github.com__<owner>__<repo>`.
    """
    cached = repository_cache / f"github.com__{repository.replace('/', '__')}"
    if not (cached / ".git").exists():
        raise ValueError(f"cached repository is missing: {cached}")
    subprocess.run(
        ["git", "-C", str(cached), "cat-file", "-e", f"{commit}^{{commit}}"],
        check=True,
        capture_output=True,
    )
    target = worktree_root / directory
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(cached),
                "worktree",
                "add",
                "--detach",
                str(target),
                commit,
            ],
            check=True,
            capture_output=True,
        )
    actual = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual != commit:
        raise ValueError(f"{target} is at {actual}, expected {commit}")
    return target


def retained_corpus(result_dir: Path) -> Corpus:
    """The 2026-08-21 corpus: one run of the ten parity tasks."""
    scorer = result_dir / "harbor-scorer"
    return Corpus(
        result_dir.name,
        [
            Trajectory(
                instance_id,
                instance_id,
                scorer / task["directory"] / "atif-trajectory.json",
                scorer / task["directory"] / "openhands-trajectory.json",
                task,
            )
            for instance_id, task in sorted(
                load_json(result_dir / "task-map.json").items()
            )
        ],
        _gold_files(result_dir / "contextbench-subset.parquet"),
    )


def parity_run_corpus(bundle_dir: Path) -> Corpus:
    """The Harbor side of the three-run parity experiment: 30 trajectories."""
    by_task_name = {
        task["task_name"]: (instance_id, task)
        for instance_id, task in load_json(
            bundle_dir / "experiment" / "task-map.json"
        ).items()
    }
    trajectories = []
    for run_dir in sorted((bundle_dir / "harbor_parity").iterdir()):
        for trial in sorted(path for path in run_dir.iterdir() if path.is_dir()):
            task_name = load_json(trial / "result.json")["task_name"]
            instance_id, task = by_task_name[task_name]
            trajectories.append(
                Trajectory(
                    f"{run_dir.name}/{instance_id}",
                    instance_id,
                    trial / "agent" / "trajectory.json",
                    trial / "agent" / "openhands.trajectory.json",
                    task,
                )
            )
    return Corpus(
        "harbor_parity",
        sorted(trajectories, key=lambda trajectory: trajectory.label),
        _gold_files(bundle_dir / "experiment" / "contextbench-subset.parquet"),
    )


def oracle_prediction(native_path: Path) -> dict[str, Any]:
    document = json.loads(native_path.read_text(encoding="utf-8"))
    if isinstance(document, list):
        document = {"history": document}
    prediction = extract_openhands_trajectory(document)
    if not isinstance(prediction, dict):
        raise TypeError(f"{native_path} produced a non-object oracle projection")
    return prediction


def _side(
    prediction: dict[str, Any],
    repository: Path,
    gold_files: frozenset[str],
) -> dict[str, Any]:
    """Size a prediction at every granularity, after the evaluator's path filter.

    Both sides emit container-prefixed paths, so they are comparable only after
    the vendored evaluator's own resolution against the checkout.
    """

    def resolved(path: object) -> str:
        return resolve_repo_relpath(str(repository), str(path))

    files = sorted(
        {path for raw in prediction.get("pred_files") or [] if (path := resolved(raw))}
    )
    spans = [
        interval
        for path, intervals in (prediction.get("pred_spans") or {}).items()
        if resolved(path)
        for interval in intervals
    ]
    symbols = prediction.get("pred_symbols") or {}
    return {
        "files": files,
        "file_count": len(files),
        "span_count": len(spans),
        "line_count": sum(
            max(int(span.get("end", 0)) - int(span.get("start", 0)) + 1, 0)
            for span in spans
        ),
        "symbol_count": sum(
            len(names)
            for path, names in symbols.items()
            if resolved(path) and isinstance(names, list)
        ),
        "step_count": len(prediction.get("pred_steps") or []),
        "gold_file_hits": len(set(files) & gold_files),
        "projection_sha256": json_sha256(prediction),
    }


def calibrate(
    corpus: Corpus,
    repository_cache: Path,
    worktree_root: Path,
) -> dict[str, Any]:
    """Project every trajectory of a corpus and compare it with the oracle."""
    records: list[dict[str, Any]] = []
    for trajectory in corpus.trajectories:
        task = trajectory.task
        repository = worktree(
            repository_cache,
            worktree_root,
            str(task["repository"]),
            str(task["base_commit"]),
            str(task["directory"]),
        )
        rule_prediction, _ = project_atif(
            load_json(trajectory.atif),
            repository,
            roots=repository_roots(str(task["workspace"])),
            trajectory_dir=trajectory.atif.parent,
        )
        gold_files = corpus.gold_files[trajectory.instance_id]
        rule = _side(rule_prediction, repository, gold_files)
        oracle = _side(oracle_prediction(trajectory.native), repository, gold_files)
        rule_files = set(rule.pop("files"))
        oracle_files = set(oracle.pop("files"))
        records.append(
            {
                "label": trajectory.label,
                "instance_id": trajectory.instance_id,
                "gold_file_count": len(gold_files),
                "rule": rule,
                "oracle": oracle,
                "rule_only_files": sorted(rule_files - oracle_files),
                "oracle_only_files": sorted(oracle_files - rule_files),
            }
        )

    def total(side: str) -> dict[str, int]:
        return {
            field: sum(int(record[side][field]) for record in records)
            for field in ("file_count", "span_count", "line_count", "gold_file_hits")
        }

    return {
        "attribution_version": ATTRIBUTION_VERSION,
        "corpus": {"name": corpus.name, "trajectories": len(records)},
        "totals": {
            "gold_file_count": sum(record["gold_file_count"] for record in records),
            "rule": total("rule"),
            "oracle": total("oracle"),
            "trajectories_with_identical_files": sum(
                not record["rule_only_files"] and not record["oracle_only_files"]
                for record in records
            ),
            "rule_only_file_total": sum(
                len(record["rule_only_files"]) for record in records
            ),
            "oracle_only_file_total": sum(
                len(record["oracle_only_files"]) for record in records
            ),
        },
        "trajectories": records,
    }
