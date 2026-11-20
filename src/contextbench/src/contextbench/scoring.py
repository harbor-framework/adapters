"""Invoke the pinned ContextBench scorer for a Harbor task."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from .attribution import ATTRIBUTION_VERSION, load_trajectory_chain, project_atif
from .vendor.contextbench_source.contextbench.core import checkout
from .vendor.contextbench_source.contextbench.evaluate import evaluate_instance
from .vendor.contextbench_source.contextbench.parsers.gold import Gold
from .vendor_api import configure_tree_sitter

_GRANULARITIES = ("file", "symbol", "span", "line")
_COUNTS = ("intersection", "gold_size", "pred_size")

# Each published metric and its path in ContextBench's per-instance result.
_METRIC_PATHS: dict[str, tuple[str, ...]] = {
    **{
        f"contextbench_{granularity}_{statistic}": ("final", granularity, statistic)
        for granularity in _GRANULARITIES
        for statistic in ("coverage", "precision")
    },
    **{
        f"contextbench_final_{granularity}_{count}": ("final", granularity, count)
        for granularity in _GRANULARITIES
        for count in _COUNTS
    },
    **{
        f"contextbench_trajectory_{name}_{granularity}": (
            "trajectory",
            section,
            granularity,
        )
        for granularity in _GRANULARITIES
        for name, section in (("auc", "auc_coverage"), ("redundancy", "redundancy"))
    },
    **{
        f"contextbench_editloc_{statistic}": ("editloc", statistic)
        for statistic in ("recall", "precision", *_COUNTS)
    },
}
# Each presence flag and the result section whose presence it records.
_PRESENCE_PATHS: dict[str, tuple[str, ...]] = {
    **{
        f"contextbench_final_{granularity}_present": ("final", granularity)
        for granularity in _GRANULARITIES
    },
    **{
        f"contextbench_trajectory_{granularity}_present": (
            "trajectory",
            "auc_coverage",
            granularity,
        )
        for granularity in _GRANULARITIES
    },
    "contextbench_editloc_present": ("editloc",),
}


class InputError(Exception):
    """The trial's trajectory is missing or unusable."""


def _verify_repository(repo_dir: Path, expected_commit: str) -> None:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required to verify the scoring repository")
    result = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("verifier repository is not a Git checkout")
    actual = result.stdout.strip()
    if actual != expected_commit:
        raise RuntimeError(
            f"verifier repository commit mismatch: expected {expected_commit}, got {actual}"
        )


def _lookup(result: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = result
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _flatten_metrics(result: dict[str, Any]) -> dict[str, float]:
    """Flatten one ContextBench result into reward keys; absent values are 0."""
    metrics = {
        key: float(_lookup(result, path) is not None)
        for key, path in _PRESENCE_PATHS.items()
    }
    metrics.update(
        {key: float(_lookup(result, path) or 0) for key, path in _METRIC_PATHS.items()}
    )
    metrics["reward"] = metrics["contextbench_file_coverage"]
    return metrics


def _patch_collection(
    model_patch_path: Path,
    collection_error_path: Path,
) -> dict[str, str]:
    """Report whether the collect step exported a complete model patch.

    The collect step writes `collect_incomplete` to its error file first and
    empties the file only after the patch is complete, so a missing or
    non-empty error file means the patch, if any, cannot be trusted.
    """
    if not collection_error_path.is_file():
        return {"status": "failed", "reason": "collection_status_missing"}
    reason = collection_error_path.read_text(encoding="utf-8", errors="replace")
    if reason.strip():
        return {"status": "failed", "reason": reason.strip()}
    if not model_patch_path.is_file():
        return {"status": "failed", "reason": "model_patch_missing"}
    return {"status": "collected"}


def read_repository_roots(path: Path) -> tuple[str, ...]:
    """Read the paths at which the task's agent environment mounts the repository.

    The adapter writes them to the task's `tests/attribution.json`; attribution
    resolves an absolute path exactly when it lies under one of them.
    """
    configuration = json.loads(path.read_text(encoding="utf-8"))
    roots = (
        configuration.get("repository_roots")
        if isinstance(configuration, dict)
        else None
    )
    if (
        not isinstance(roots, list)
        or not roots
        or not all(
            isinstance(root, str) and root.startswith("/") and root.strip("/")
            for root in roots
        )
    ):
        raise ValueError(f"{path} does not list absolute repository_roots")
    return tuple(str(root) for root in roots)


def _load_gold_payload(gold_path: Path) -> tuple[dict[str, Any], str, str, list[Any]]:
    gold_payload = json.loads(gold_path.read_text(encoding="utf-8"))
    if not isinstance(gold_payload, dict):
        raise TypeError("ContextBench gold payload must be an object")
    instance_id = str(gold_payload.get("instance_id") or "")
    base_commit = str(gold_payload.get("base_commit") or "")
    gold_context = gold_payload.get("gold_context")
    if not instance_id or len(base_commit) != 40 or not isinstance(gold_context, list):
        raise ValueError("ContextBench gold payload is incomplete")
    if not all(isinstance(annotation, dict) for annotation in gold_context):
        raise TypeError("ContextBench gold annotation must be an object")
    return gold_payload, instance_id, base_commit, gold_context


def _diagnostics(
    instance_id: str,
    contextbench_commit: Any,
    repository_roots: tuple[str, ...],
    prediction: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    classification_counts = Counter(item["classification"] for item in evidence)
    heuristic_counts = Counter(item["heuristic"] for item in evidence)
    credited_family_counts = Counter(
        item["family"] for item in evidence if item["result"] == "credit"
    )
    return {
        "status": "ok",
        "instance_id": instance_id,
        "contextbench_commit": contextbench_commit,
        # The single attribution rule is defined in ATTRIBUTION.md. Scores
        # produced under different versions are not comparable.
        "attribution_version": ATTRIBUTION_VERSION,
        "repository_roots": list(repository_roots),
        "projection": prediction,
        "classification_counts": dict(sorted(classification_counts.items())),
        "heuristic_counts": dict(sorted(heuristic_counts.items())),
        "credited_step_counts_by_family": dict(sorted(credited_family_counts.items())),
        # The unmapped and malformed records themselves stay in `evidence`.
        "unmapped_tool_call_count": sum(
            item["result"] in {"no_match", "malformed"}
            or item["classification"] == "unmapped"
            for item in evidence
        ),
        "evidence": evidence,
    }


def score_contextbench(  # noqa: PLR0913 - one argument per verifier input.
    *,
    trajectory_path: Path,
    gold_path: Path,
    repo_dir: Path,
    repository_roots: tuple[str, ...],
    model_patch_path: Path,
    collection_error_path: Path,
) -> tuple[dict[str, float], dict[str, Any]]:
    """Extract agent context and score it with ContextBench's pinned evaluator.

    `repository_roots` are the paths at which the agent saw the repository.
    The model patch feeds only edit localization, so a trial whose patch
    collection failed is scored without it.
    """
    patch_collection = _patch_collection(model_patch_path, collection_error_path)
    gold_payload, instance_id, base_commit, gold_context = _load_gold_payload(gold_path)
    _verify_repository(repo_dir, base_commit)

    # ContextBench creates scoring worktrees under CONTEXTBENCH_TMP_ROOT. For a
    # linked checkout, the worktree points into a clone in this cache, so the
    # cache sits beside the worktrees and lasts as long as they do.
    tmp_root = os.environ.get("CONTEXTBENCH_TMP_ROOT") or tempfile.gettempdir()
    cache_dir = str(Path(tmp_root) / "contextbench-cache")
    scoring_repo = checkout(str(repo_dir), base_commit, cache_dir, verbose=False)
    if not scoring_repo:
        raise RuntimeError("ContextBench could not create a clean scoring worktree")

    trajectory_root = trajectory_path.parent.resolve()
    try:
        trajectory = load_trajectory_chain(
            trajectory_path, allowed_root=trajectory_root
        )
        prediction, evidence = project_atif(
            trajectory,
            Path(scoring_repo),
            roots=repository_roots,
            trajectory_dir=trajectory_root,
        )
    except (TypeError, ValueError) as error:
        # Attribution raises these for a missing, malformed, or
        # structurally invalid ATIF trajectory.
        raise InputError(str(error)) from error
    diagnostics = _diagnostics(
        instance_id,
        gold_payload.get("contextbench_commit"),
        repository_roots,
        prediction,
        evidence,
    )
    diagnostics["patch_collection"] = patch_collection
    if not prediction["pred_files"]:
        metrics = _flatten_metrics({})
        diagnostics["status"] = "no_context_extracted"
        diagnostics["metrics"] = metrics
        return metrics, diagnostics

    # An empty patch becomes a placeholder, so a trial without edits scores
    # edit location as 0 instead of omitting it. It also keeps the
    # evaluator off its gold-patch fallback. A trial without a collected patch
    # passes none. The gold payload below holds no `patch`, so the fallback
    # finds nothing and the result has no edit localization.
    model_patch = (
        (
            model_patch_path.read_text(encoding="utf-8", errors="replace")
            or "# no model patch\n"
        )
        if patch_collection["status"] == "collected"
        else ""
    )
    # Gold annotation paths are passed through unchanged so that
    # ContextBench's own `Gold` parser normalizes them. It recognizes more
    # shapes than a single container prefix: `/testbed/<path>`,
    # `/workspace/<repo-dir>/<path>`, other absolute paths, and `./<path>`.
    # Rewriting them here would force every annotation down the `/testbed/`
    # branch.
    gold = Gold(
        {
            "original_inst_id": instance_id,
            "repo_url": str(repo_dir),
            "commit": base_commit,
            "gold_ctx": gold_context,
        }
    )
    configure_tree_sitter()
    canonical_result = evaluate_instance(
        instance_id,
        gold,
        {
            "instance_id": instance_id,
            "repo_url": str(repo_dir),
            "commit": base_commit,
            "traj_data": prediction,
            "model_patch": model_patch,
        },
        cache_dir,
    )
    diagnostics["canonical_result"] = canonical_result
    if canonical_result.get("error"):
        raise RuntimeError(
            f"ContextBench evaluator failed: {canonical_result.get('error')}"
        )

    metrics = _flatten_metrics(canonical_result)
    diagnostics["metrics"] = metrics
    return metrics, diagnostics


__all__ = ["InputError", "read_repository_roots", "score_contextbench"]
