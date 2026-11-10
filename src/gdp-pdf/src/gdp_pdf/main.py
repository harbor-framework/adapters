"""Command-line entry point: `uv run gdp-pdf --output-dir <path>`."""

import argparse
import logging
from pathlib import Path

from .adapter import GdpPdfAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "gdp-pdf"


def main() -> None:
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
        help="Only generate these tasks (Harbor names like hr-03, or upstream task ids)",
    )
    parser.add_argument(
        "--oracle-dir",
        type=Path,
        default=None,
        help="Directory of oracle answers named <upstream task_id>.md (see scripts/build_oracle.py)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    adapter = GdpPdfAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        oracle_dir=args.oracle_dir,
    )

    adapter.run()


if __name__ == "__main__":
    main()
