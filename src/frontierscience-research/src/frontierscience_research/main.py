"""
CLI entry point for the FrontierScience-Research adapter.

Constructs the adapter defined in adapter.py and calls run() to generate Harbor
tasks in the configured output directory.
"""

import argparse
import logging
from pathlib import Path

from .adapter import DEFAULT_ORACLE_DIR, FrontierScienceResearchAdapter

# Default output dir: <adapters repo>/datasets/frontierscience-research (gitignored)
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[4] / "datasets" / "frontierscience-research"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Harbor tasks for FrontierScience-Research."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write generated tasks",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Generate only the first N tasks",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing tasks",
    )
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Only generate these task IDs (e.g. physics-222e24bf)",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=None,
        help="Local copy of research/test.jsonl (default: download the pinned HF revision)",
    )
    parser.add_argument(
        "--oracle-dir",
        type=Path,
        default=DEFAULT_ORACLE_DIR,
        help="Directory of oracle answers named <subject>-<task_group_id[:8]>.md",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    adapter = FrontierScienceResearchAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        data_file=args.data_file,
        oracle_dir=args.oracle_dir,
    )

    adapter.run()


if __name__ == "__main__":
    main()
