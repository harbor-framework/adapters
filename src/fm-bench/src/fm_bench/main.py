"""CLI entry point: uv run fm-bench --output-dir <path> [--limit N] [--overwrite]
[--task-ids ...] [--split full|parity]
[--fmbench-root <checkout> | --fmbench-repo <git url> [--fmbench-ref <commit>]]

Builds the adapter defined in adapter.py and calls run() to write the tasks.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .adapter import AdapterError, FMBenchAdapter


def main() -> None:
    parser = argparse.ArgumentParser(prog="fm-bench", description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="directory to write the generated tasks to")
    parser.add_argument("--limit", type=int, default=None,
                        help="generate only the first N tasks")
    parser.add_argument("--overwrite", action="store_true",
                        help="replace tasks that already exist")
    parser.add_argument("--task-ids", nargs="+", default=None,
                        help="generate only these task ids (the only one is "
                             "fm-bench-solo-20y)")
    parser.add_argument("--split", choices=["full", "parity"], default="full",
                        help="parity equals full: the one task")
    parser.add_argument("--fmbench-root", type=Path,
                        default=os.environ.get("FMBENCH_ROOT") or None,
                        help="a local FM-Bench checkout (or set FMBENCH_ROOT)")
    parser.add_argument("--fmbench-repo",
                        default=os.environ.get("FMBENCH_REPO") or None,
                        help="a git URL to clone FM-Bench from (or set FMBENCH_REPO)")
    parser.add_argument("--fmbench-ref",
                        default=os.environ.get("FMBENCH_REF") or None,
                        help="commit, tag or branch to check out after cloning "
                             "(or set FMBENCH_REF)")
    args = parser.parse_args()

    adapter = FMBenchAdapter(
        args.output_dir, limit=args.limit, overwrite=args.overwrite,
        task_ids=args.task_ids, split=args.split, fmbench_root=args.fmbench_root,
        fmbench_repo=args.fmbench_repo, fmbench_ref=args.fmbench_ref)
    try:
        written = adapter.run()
    except AdapterError as e:
        parser.error(str(e))
    for dest in written:
        print(f"wrote {dest}")
    print(f"{len(written)} task(s) in {args.output_dir}")


if __name__ == "__main__":
    main()
