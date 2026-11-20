"""Narrow compatibility boundary around the pinned ContextBench code."""

from __future__ import annotations

import os
from typing import Any

from tree_sitter_language_pack import PackConfig, configure, get_parser

from .vendor.contextbench_source.contextbench.agents.openhands import extract
from .vendor.contextbench_source.contextbench.evaluate import _resolve_repo_relpath
from .vendor.contextbench_source.contextbench.extractors import treesitter
from .vendor.contextbench_source.contextbench.parsers.gold import _normalize_rel_path

ContextStep = dict[str, Any]


def extract_openhands_trajectory(document: dict[str, Any]) -> dict[str, Any]:
    """Extract a full native OpenHands trajectory with the pinned oracle.

    This is the test oracle: the one upstream-authored extraction definition
    that exists for any agent. It is not a scoring path; calibration measures
    the adapter's single attribution rule against it (see ATTRIBUTION.md).
    """
    return extract.extract_trajectory(document)


def configure_tree_sitter() -> None:
    """Route the pinned symbol extractor's parser lookups through the pack."""
    # The verifier image bakes every grammar into this cache.
    if cache_dir := os.environ.get("CONTEXTBENCH_TREE_SITTER_CACHE"):
        configure(PackConfig(cache_dir=cache_dir))

    def get_pack_parser(name: str) -> Any:
        # LANG_MAP calls the C# grammar `c_sharp`; the pack calls it `csharp`.
        return get_parser("csharp" if name == "c_sharp" else name)

    treesitter._get_parser = get_pack_parser


def normalize_gold_path(raw_path: str) -> str:
    """Return the repository-relative path that ContextBench's `Gold` reads."""
    return _normalize_rel_path(raw_path)


def resolve_repo_relpath(repository: str, path: str) -> str:
    """Resolve a predicted path against a checkout as the pinned evaluator does."""
    return _resolve_repo_relpath(repository, path)


def aggregate_steps(
    steps: list[ContextStep],
) -> tuple[list[str], dict[str, list[dict[str, int]]]]:
    """Aggregate prediction steps with the pinned extractor."""
    return extract._aggregate_steps(steps)


__all__ = [
    "ContextStep",
    "aggregate_steps",
    "configure_tree_sitter",
    "extract_openhands_trajectory",
    "normalize_gold_path",
    "resolve_repo_relpath",
]
