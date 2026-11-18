"""CLI entry point: generate Harbor tasks for CAVA (pipeline/transcript variant)."""

import argparse
import logging
from pathlib import Path

from .adapter import CavaAdapter
from .subtasks import SUBTASKS

# Default output dir: <repo>/datasets/cava
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "cava"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Directory to write generated tasks")
    parser.add_argument("--limit", type=int, default=None,
                        help="Generate only the first N tasks")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing tasks")
    parser.add_argument("--task-ids", nargs="+", default=None,
                        help="Only generate these task IDs")
    parser.add_argument("--subtasks", nargs="+", choices=sorted(SUBTASKS), default=None,
                        help="CAVA subtasks to generate (default: all shipped subtasks)")
    parser.add_argument("--split", choices=["full", "parity"], default="full",
                        help="'parity' generates only the parity subset")
    parser.add_argument("--manifest-dir", type=Path, default=None,
                        help="Directory with <subtask>.jsonl manifests "
                        "(default: the manifests shipped with the adapter)")
    args = parser.parse_args()

    adapter = CavaAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        manifest_dir=args.manifest_dir,
        subtasks=args.subtasks,
        split=args.split,
    )
    adapter.run()


if __name__ == "__main__":
    main()
