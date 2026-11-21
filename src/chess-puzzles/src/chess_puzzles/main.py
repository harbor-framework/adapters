"""Generate the Chess Puzzles v2 dataset in Harbor task format.

Does not call any model and incurs no API cost.
"""

import argparse
from pathlib import Path

from .adapter import UPSTREAM_COMMIT, ChessPuzzlesAdapter

# Run from the adapter package directory, matching run_chess-puzzles.yaml.
DEFAULT_OUTPUT_DIR = Path("datasets") / "chess-puzzles-separate"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
        help="Only generate these task IDs (e.g. chess-puzzles-007, 007 or 7)",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=None,
        help=f"Local puzzles.csv from upstream commit {UPSTREAM_COMMIT[:12]} "
        "(downloaded and checksum-verified when omitted)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".cache/chess-puzzles"),
        help="Where the downloaded puzzles.csv is cached",
    )
    parser.add_argument("--variant", choices=("cli", "original"), default=None,
                        help="Defaults to original for --split parity, cli otherwise")
    parser.add_argument("--split", choices=("full", "parity"), default="full",
                        help="parity selects the ten predeclared row IDs")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    adapter = ChessPuzzlesAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        data_path=args.data_path,
        cache_dir=args.cache_dir,
        variant=args.variant,
        split=args.split,
    )
    tasks = adapter.run()
    print(f"Generated {len(tasks)} tasks in {args.output_dir}")


if __name__ == "__main__":
    main()
