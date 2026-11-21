"""CLI entry point for the Harbor TraceTrial-Bench adapter."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .adapter import VALID_SPLITS, TraceTrialBenchAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate Harbor task directories for TraceTrial-Bench."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets/tracetrial-bench"),
        help="Output directory for generated Harbor tasks.",
    )
    parser.add_argument(
        "--task-ids",
        type=str,
        default=None,
        help="Comma-separated TraceTrial-Bench task IDs (defaults to all tasks in split).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of tasks to generate.",
    )
    parser.add_argument(
        "--split",
        choices=list(VALID_SPLITS),
        default="standalone",
        help="Task split to adapt ('standalone' = 18 standalone single-turn tasks; 'parity' = parity set; 'all' = all 96 tasks).",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Optional local TraceTrial-Bench checkout directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing generated task directories.",
    )
    args = parser.parse_args(argv)

    task_ids = (
        [x.strip() for x in args.task_ids.split(",") if x.strip()]
        if args.task_ids
        else None
    )
    try:
        adapter = TraceTrialBenchAdapter(
            args.output_dir,
            source_dir=args.source_dir,
            split=args.split,
        )
        written = adapter.run(
            task_ids=task_ids,
            limit=args.limit,
            overwrite=args.overwrite,
        )
        logger.info("Generated %d TraceTrial-Bench Harbor task(s) in %s", len(written), args.output_dir)
    except Exception as exc:
        logger.error("Failed to generate TraceTrial-Bench tasks: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
