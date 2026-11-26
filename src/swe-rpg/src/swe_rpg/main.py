"""
Main CLI entrypoint for the SWE-RPG adapter.

Usage:
    cd src/swe-rpg
    uv run swe-rpg --output-dir ../../datasets/swe-rpg

CLI arguments:
- --output-dir: destination for generated Harbor task directories;
  defaults to datasets/swe-rpg
- --limit: optional cap on how many tasks to generate
- --overwrite: replace existing task directories
- --task-ids: generate only the specified tasks (the instance id, any case,
  like `pypa__pip-13124`)
- --split: `full` (default, all 163 tasks) or `parity` (the parity subset
  listed in parity_task_ids.txt)
- --data-file: path to a local copy of data/benchmark.jsonl; its SHA256 is
  verified. Without it the file is downloaded once from the pinned commit
  into ~/.cache/swe-rpg-adapter
"""

import argparse
import logging
from pathlib import Path

from .adapter import SPLITS, SweRpgAdapter

DEFAULT_OUTPUT_DIR = Path("datasets") / "swe-rpg"


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
        help="Only generate these tasks (instance ids)",
    )
    parser.add_argument(
        "--split",
        choices=SPLITS,
        default="full",
        help="Which task set to generate: full (163 tasks) or parity",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=None,
        help="Path to a local benchmark.jsonl (SHA256-verified)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    adapter = SweRpgAdapter(
        output_dir=args.output_dir,
        limit=args.limit,
        overwrite=args.overwrite,
        task_ids=args.task_ids,
        split=args.split,
        data_file=args.data_file,
    )
    adapter.run()


if __name__ == "__main__":
    main()
