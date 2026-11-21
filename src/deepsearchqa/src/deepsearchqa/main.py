"""CLI entry point: generate Harbor tasks for DeepSearchQA."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from deepsearchqa.adapter import DATASET_URL, DeepSearchQAAdapter
else:
    from .adapter import DATASET_URL, DeepSearchQAAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Harbor tasks for the DeepSearchQA benchmark",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets") / "deepsearchqa",
        help="Directory to write generated tasks (default: datasets/deepsearchqa)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Generate only the first N tasks"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing task directories"
    )
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Only generate these tasks (e.g. deepsearchqa-007, 007 or 7)",
    )
    parser.add_argument(
        "--split",
        choices=["full", "parity"],
        default="full",
        help="'full' = all 900 prompts; 'parity' = stratified parity subset",
    )
    parser.add_argument(
        "--parity-size",
        type=int,
        default=100,
        help="Size of the parity subset (default: 100)",
    )
    parser.add_argument(
        "--parity-seed", type=int, default=42, help="Seed for the parity subset"
    )
    parser.add_argument(
        "--source-csv",
        type=Path,
        default=None,
        help="Use a local copy of DSQA-full.csv instead of downloading it",
    )
    parser.add_argument(
        "--dataset-url",
        default=DATASET_URL,
        help="Override the DSQA-full.csv download URL",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    adapter = DeepSearchQAAdapter(
        output_dir=args.output_dir,
        limit=args.limit,
        overwrite=args.overwrite,
        task_ids=args.task_ids,
        split=args.split,
        parity_size=args.parity_size,
        parity_seed=args.parity_seed,
        source_csv=args.source_csv,
        dataset_url=args.dataset_url,
    )
    written = adapter.run()
    logger.info(f"Done: {len(written)} tasks in {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
