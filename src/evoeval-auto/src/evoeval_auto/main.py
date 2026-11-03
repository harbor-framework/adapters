"""CLI entry point: ``uv run evoeval-auto --output-dir <path> [--dataset EvoEval_difficult]``."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .adapter import DEFAULT_DATASET, EVOEVAL_DATASETS, EvoEvalAdapter

# Default output dir: <repo>/datasets/evoeval-auto
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "evoeval-auto"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Harbor tasks from the EvoEval benchmark (release v0.1.0)."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write generated tasks (default: <repo>/datasets/evoeval-auto)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Generate only the first N tasks (after --task-ids filtering)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing task directories",
    )
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help=(
            "Only generate these tasks. Accepts upstream ids (EvoEval/7), Harbor task "
            "names (evoeval-difficult-7) or bare numbers (7)"
        ),
    )
    parser.add_argument(
        "--dataset",
        choices=EVOEVAL_DATASETS,
        default=DEFAULT_DATASET,
        help=f"EvoEval dataset to convert (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=None,
        help="Use a local <dataset>.jsonl or .jsonl.gz instead of downloading the release",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Optional directory to cache the downloaded release file",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    adapter = EvoEvalAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        dataset=args.dataset,
        data_path=args.data_path,
        cache_dir=args.cache_dir,
    )
    adapter.run()


if __name__ == "__main__":
    main()
