"""
Main entry point for the template adapter. Do not modify any of the existing flags.
You can add any additional flags you need.

Constructs the Adapter class defined in adapter.py and calls run() to generate tasks
in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import GDMStealthAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "gdm-stealth"


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
        help="Only generate these task IDs",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help=(
            "Existing inspect_evals checkout at the pinned commit "
            "(default: $GDM_INSPECT_EVALS_DIR or a cache clone)"
        ),
    )
    parser.add_argument(
        "--cover-with-hint",
        action="store_true",
        help=(
            "Also generate cover_your_tracks:with_hint "
            "(upstream default is hard_only=True, i.e. no_hint only)"
        ),
    )
    args = parser.parse_args()

    adapter = GDMStealthAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        source_dir=args.source_dir,
        cover_with_hint=args.cover_with_hint,
    )

    adapter.run()


if __name__ == "__main__":
    main()
