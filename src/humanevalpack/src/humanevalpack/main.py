"""CLI entry point: ``uv run humanevalpack --output-dir <path>``."""

import argparse
from pathlib import Path

from .adapter import DATASET_REVISION, HumanEvalPackAdapter
from .languages import DEFAULT_LANGUAGES, LANGUAGES

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "humanevalpack"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Harbor tasks for HumanEvalPack (HumanEvalFix)"
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
        help="Generate only the first N tasks of each selected language",
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
        help="Only generate these task IDs (e.g. js-0, JavaScript/0, "
        "bigcode/humanevalpack__js-0)",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        choices=sorted(LANGUAGES),
        default=list(DEFAULT_LANGUAGES),
        help=f"Languages to generate (default: {' '.join(DEFAULT_LANGUAGES)})",
    )
    parser.add_argument(
        "--dataset-revision",
        default=DATASET_REVISION,
        help="Pinned Hugging Face dataset revision",
    )
    parser.add_argument(
        "--include-excluded",
        action="store_true",
        help="Also generate tasks excluded for upstream defects (see README)",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")

    adapter = HumanEvalPackAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        languages=args.languages,
        dataset_revision=args.dataset_revision,
        include_excluded=args.include_excluded,
    )
    adapter.run()


if __name__ == "__main__":
    main()
