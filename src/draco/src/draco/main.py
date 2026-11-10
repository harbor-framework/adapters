"""
Generate DRACO tasks in Harbor format.

Usage:
    uv run draco --output-dir ../../datasets/draco
"""

import argparse
import logging
from pathlib import Path

from .adapter import DracoAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "draco"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

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
        help="Generate only the first N tasks (sorted by id)",
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
        help="Only generate these task IDs (upstream id values)",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=None,
        help="Local test.jsonl (default: download the pinned HF revision)",
    )
    parser.add_argument(
        "--oracle-reports-dir",
        type=Path,
        default=None,
        help="Directory of <id>.md reports to stage as oracle solutions "
        "(default: rubric-derived fallback reports)",
    )
    args = parser.parse_args()

    adapter = DracoAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        data_file=args.data_file,
        oracle_reports_dir=args.oracle_reports_dir,
    )

    adapter.run()


if __name__ == "__main__":
    main()
