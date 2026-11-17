"""Main entry point for the ARC-AGI-3 adapter. Do not modify any of the existing flags.
You can add any additional flags you need.

Constructs the ArcAgi3Adapter class defined in adapter.py and calls run() to generate
tasks in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import ArcAgi3Adapter

# Relative to the invocation directory, also valid for wheel installs.
DEFAULT_OUTPUT_DIR = Path("datasets/arc-agi-3")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert ARC-AGI-3 games into Harbor task directories."
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
        help="Only generate these game IDs (e.g. ar25-0c556536)",
    )
    args = parser.parse_args()

    adapter = ArcAgi3Adapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
    )

    adapter.run()


if __name__ == "__main__":
    main()
