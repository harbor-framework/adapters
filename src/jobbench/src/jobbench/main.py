"""CLI entry point: generate JobBench tasks in Harbor format."""

import argparse
from pathlib import Path

from .adapter import HF_REVISION, JobBenchAdapter

# Default output dir: <repo>/datasets/jobbench
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "jobbench"


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
        help="Only generate these task IDs, e.g. main--lawyers--task1",
    )
    parser.add_argument(
        "--split",
        choices=["main", "easy", "all"],
        default="all",
        help="main = 65 leaderboard tasks, easy = 63 simplified tasks (default: all)",
    )
    parser.add_argument(
        "--revision",
        default=HF_REVISION,
        help="Hugging Face dataset revision (default: the pinned commit)",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Local copy of the JobBench dataset to use instead of downloading",
    )
    args = parser.parse_args()

    adapter = JobBenchAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        split=args.split,
        revision=args.revision,
        source_dir=args.source_dir,
    )

    adapter.run()


if __name__ == "__main__":
    main()
