"""
Main entry point for the template adapter. Do not modify any of the existing flags.
You can add any additional flags you need.

Constructs the Adapter class defined in adapter.py and calls run() to generate tasks
in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import VARIANTS, KernelBenchAdapter

# Default output dir: <repo>/datasets/<variant>
DATASETS_DIR = Path(__file__).resolve().parents[4] / "datasets"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to write generated tasks (default: <repo>/datasets/<variant>)",
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
        help="Only generate these task IDs, e.g. kernelbench-l1-019",
    )
    parser.add_argument(
        "--variant",
        choices=VARIANTS,
        default="kernelbench",
        help="kernelbench (original grader) or kernelbench-verified (KBV grader)",
    )
    parser.add_argument(
        "--levels", type=int, nargs="+", choices=[1, 2, 3], default=[1, 2, 3]
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Where the pinned upstream repos are checked out (default: ~/.cache/harbor-kernelbench)",
    )
    args = parser.parse_args()

    adapter = KernelBenchAdapter(
        args.output_dir or DATASETS_DIR / args.variant,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        variant=args.variant,
        levels=args.levels,
        source_dir=args.source_dir,
    )

    adapter.run()


if __name__ == "__main__":
    main()
