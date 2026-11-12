from __future__ import annotations

import argparse
from pathlib import Path

from .adapter import DEFAULT_CACHE_DIR, MODES, CharXivAdapter

DEFAULT_OUTPUT_DIR = Path("datasets/charxiv")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Harbor tasks for CharXiv (validation split)."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Directory to write generated tasks (default: datasets/charxiv)")
    parser.add_argument("--limit", type=int, default=None, help="Generate only the first N tasks")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing task dirs")
    parser.add_argument("--task-ids", nargs="+", default=None,
                        help="Only generate these task ids (e.g. charxiv-reasoning-12)")
    parser.add_argument("--modes", nargs="+", choices=list(MODES), default=list(MODES),
                        help="Question types to generate (default: both)")
    parser.add_argument("--split", choices=["full", "parity"], default="full",
                        help="full: all 1000 validation charts (5000 tasks); parity: 200 charts "
                             "sampled with seed 42 (1000 tasks)")
    parser.add_argument("--source-dir", type=Path, default=None,
                        help="Optional local CharXiv checkout containing data/ and images/ "
                             "(default: download pinned sources)")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR,
                        help="Download cache for pinned sources")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")

    CharXivAdapter(
        output_dir=args.output_dir,
        limit=args.limit,
        overwrite=args.overwrite,
        task_ids=args.task_ids,
        modes=tuple(args.modes),
        source_dir=args.source_dir,
        cache_dir=args.cache_dir,
        split=args.split,
    ).run()


if __name__ == "__main__":
    main()
