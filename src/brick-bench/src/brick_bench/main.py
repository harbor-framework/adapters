"""CLI entry point for the BrickBench Harbor adapter."""

from __future__ import annotations

import argparse
from pathlib import Path

from .adapter import SPLITS, BrickBenchAdapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brick-bench",
        description="Generate Harbor task directories for BrickBench (300 tasks across model, set, and alt-build).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets/brick-bench"),
        help="Destination directory for generated Harbor task folders.",
    )
    parser.add_argument(
        "--split",
        choices=("all", "parity", "oracle-smoke", *SPLITS),
        default="all",
        help="Benchmark subset to generate (default: all 300 tasks).",
    )
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Specific task IDs to generate (e.g. model-001 set-001 alt-001).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of tasks to generate.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing task directories.",
    )
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=None,
        help="Optional local clone of kulits/BrickAgent (avoids network fetches for tasks/prompts).",
    )
    parser.add_argument(
        "--oracle-dir",
        type=Path,
        default=None,
        help="Optional local directory containing oracle build.py files.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Optional cache directory for pinned upstream task and oracle files.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    adapter = BrickBenchAdapter(
        output_dir=args.output_dir,
        split=args.split,
        task_ids=args.task_ids,
        limit=args.limit,
        overwrite=args.overwrite,
        repo_path=args.repo_path,
        oracle_dir=args.oracle_dir,
        cache_dir=args.cache_dir,
    )
    generated = adapter.run()
    print(f"Generated {len(generated)} BrickBench task(s) in {args.output_dir}")


if __name__ == "__main__":
    main()
