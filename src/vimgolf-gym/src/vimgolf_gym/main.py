"""CLI entry point: generate Harbor tasks for VimGolf-Gym."""

import argparse
import logging
from pathlib import Path

from .adapter import VimGolfGymAdapter

# Default output dir: <repo>/datasets/vimgolf-gym
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "vimgolf-gym"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
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
        help="Only generate these task IDs (Harbor task ids or vimgolf challenge ids)",
    )
    parser.add_argument(
        "--zip-path",
        type=Path,
        default=None,
        help="Local copy of challenges.zip (checked against the pinned sha256); "
        "downloaded from Hugging Face when omitted",
    )
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Also emit challenges without a replay-verified oracle solution "
        "(their solve.sh writes an empty solution)",
    )
    args = parser.parse_args()

    adapter = VimGolfGymAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        zip_path=args.zip_path,
        include_unverified=args.include_unverified,
    )

    adapter.run()


if __name__ == "__main__":
    main()
