"""Build GSM8K for the Harbor adapter CLI."""

import argparse
from pathlib import Path

from .adapter import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--split", choices=("test", "train", "parity"), default="test")
    parser.add_argument("--source", type=Path, help="Local copy of the pinned upstream JSONL")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--task-ids", nargs="+", default=[])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    task_ids = [task for value in args.task_ids for task in value.split(",")]
    manifest = build(args.output_dir, args.split, args.source, task_ids, args.limit, args.overwrite)
    print(f"Generated {manifest['task_count']} {args.split} tasks in {args.output_dir}")


if __name__ == "__main__":
    main()
