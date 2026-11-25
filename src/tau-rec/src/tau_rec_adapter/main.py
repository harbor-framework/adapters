"""Generate tau-Rec movies-v1 Harbor tasks (writes datasets/tau-rec by default)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adapter import TAU_REC_TAG, TauRecAdapter

# Default output dir: <adapters repository root>/datasets/tau-rec
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "tau-rec"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write generated tasks (default: datasets/tau-rec)",
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
        help="Only generate these task IDs (e.g. task_001 task_002)",
    )
    parser.add_argument(
        "--tau-rec-root",
        type=Path,
        default=None,
        help=(
            f"tau-Rec {TAU_REC_TAG} checkout to read the tasks from (default: "
            f"$TAU_REC_ROOT, else a clone of {TAU_REC_TAG} under "
            "src/tau-rec/.cache/tau-rec)"
        ),
    )
    args = parser.parse_args(argv)

    try:
        adapter = TauRecAdapter(
            args.output_dir,
            overwrite=args.overwrite,
            limit=args.limit,
            task_ids=args.task_ids,
            tau_rec_root=args.tau_rec_root,
        )
        paths = adapter.run()
    except (FileExistsError, ValueError, RuntimeError, OSError) as exc:
        sys.exit(f"error: {exc}")
    print(f"Generated {len(paths)} tasks in {args.output_dir}")


if __name__ == "__main__":
    main()
