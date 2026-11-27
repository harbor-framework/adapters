"""
Main CLI entrypoint for the AxionLimitBench adapter.

Usage:
    cd src/axionlimitbench
    uv run axionlimitbench --output-dir ../../datasets/axionlimitbench

CLI arguments:
- --output-dir: destination for generated Harbor task directories;
  defaults to datasets/axionlimitbench
- --limit: optional cap on how many tasks to generate
- --overwrite: replace existing task directories
- --task-ids: generate only the specified tasks (accepts the generated task
  name like `2208-07293` or the arXiv id like `2208.07293`)
- --split: `full` (default, every gradable paper) or `parity` (the parity
  subset listed in parity_task_ids.txt)
- --repo-dir: path to an existing checkout of the benchmark at the pinned
  commit. Without it the adapter clones the benchmark once into
  ~/.cache/axionlimitbench-adapter
"""

import argparse
import logging
from pathlib import Path

from .adapter import SPLITS, AxionLimitBenchAdapter

DEFAULT_OUTPUT_DIR = Path("datasets") / "axionlimitbench"


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
        help="Only generate these tasks (task name or arXiv id)",
    )
    parser.add_argument(
        "--split",
        choices=SPLITS,
        default="full",
        help="Which task set to generate: full or parity",
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=None,
        help="Path to a checkout of the benchmark at the pinned commit",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    adapter = AxionLimitBenchAdapter(
        output_dir=args.output_dir,
        limit=args.limit,
        overwrite=args.overwrite,
        task_ids=args.task_ids,
        split=args.split,
        repo_dir=args.repo_dir,
    )
    adapter.run()


if __name__ == "__main__":
    main()
