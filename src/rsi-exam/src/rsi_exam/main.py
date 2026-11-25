"""
CLI entry point for the RSI-Exam adapter.

Constructs RSIExamAdapter and calls run() to generate Harbor tasks at --output-dir.
"""

import argparse
import logging
from pathlib import Path

from .adapter import DEFAULT_REPO_ID, DEFAULT_REVISION, SPLITS, RSIExamAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "rsi-exam"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for noisy in ("httpx", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(
        description="Generate Harbor tasks for the RSI-Exam public task set."
    )
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
        help="Only generate these task IDs",
    )
    parser.add_argument(
        "--split",
        choices=SPLITS,
        default="full",
        help="full: all tasks (default); parity: the 22-task CPU-only, no-API-key "
        "parity subset",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Read tasks from a local copy of the dataset instead of downloading "
        "(e.g. the full 88-task suite provided by the RSI-Exam authors)",
    )
    parser.add_argument(
        "--repo-id",
        default=DEFAULT_REPO_ID,
        help=f"Hugging Face dataset repo (default: {DEFAULT_REPO_ID})",
    )
    parser.add_argument(
        "--revision",
        default=DEFAULT_REVISION,
        help="Hugging Face dataset revision to pin (default: the audited commit)",
    )
    args = parser.parse_args()

    adapter = RSIExamAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        split=args.split,
        source_dir=args.source_dir,
        repo_id=args.repo_id,
        revision=args.revision,
    )

    adapter.run()


if __name__ == "__main__":
    main()
