"""CLI entry point: ``uv run evoeval-auto --output-dir <dir> [--dataset EvoEval_difficult]``.

Generates one Harbor task directory per EvoEval problem of the selected dataset.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .adapter import DATASETS, DEFAULT_DATASET, EvoEvalAdapterError, EvoevalAutoAdapter

# Default output dir: <repo>/datasets/evoeval-auto
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "evoeval-auto"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Harbor tasks from EvoEval (default: EvoEval_difficult)."
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
        help="Generate only the first N tasks (in upstream order)",
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
        help="Only generate these tasks; accepts upstream IDs (EvoEval/7) "
        "or local IDs (difficult-7)",
    )
    parser.add_argument(
        "--dataset",
        choices=DATASETS,
        default=DEFAULT_DATASET,
        help=f"EvoEval dataset to convert (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=None,
        help="Use a local copy of the release file (<dataset>.jsonl or .jsonl.gz) "
        "instead of downloading it; its md5 must match the v0.1.0 release",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Cache the downloaded release file in this directory "
        "(default: download into memory, no cache)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        adapter = EvoevalAutoAdapter(
            args.output_dir,
            limit=args.limit,
            overwrite=args.overwrite,
            task_ids=args.task_ids,
            dataset=args.dataset,
            data_file=args.data_file,
            cache_dir=args.cache_dir,
        )
        adapter.run()
    except EvoEvalAdapterError as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
