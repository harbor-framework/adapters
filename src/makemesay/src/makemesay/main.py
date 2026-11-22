"""
Main entry point for the template adapter. Do not modify any of the existing flags.
You can add any additional flags you need.

Constructs the Adapter class defined in adapter.py and calls run() to generate tasks
in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import DEFAULT_SPLIT, SPLIT_MANIFEST, MakeMeSayAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "makemesay"


def main() -> None:
    parser = argparse.ArgumentParser()
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
        help=(
            "Only generate these local task IDs or generated task names, such as "
            "openai/make-me-say-medium-and-hard-00000"
        ),
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        choices=list(SPLIT_MANIFEST),
        default=list(SPLIT_MANIFEST),
        help=(
            "Upstream MakeMeSay splits to generate; defaults to all five registry "
            f"variants (the default upstream eval is {DEFAULT_SPLIT})"
        ),
    )
    args = parser.parse_args()

    adapter = MakeMeSayAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        splits=args.splits,
    )

    adapter.run()


if __name__ == "__main__":
    main()
