"""
Main entry point for the Petri adapter. Do not modify any of the existing flags.
You can add any additional flags you need.

Constructs the PetriAdapter class defined in adapter.py and calls run() to generate
tasks in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import DEFAULT_DATASET_CACHE_DIR, DEFAULT_AUDITOR_MODEL, DEFAULT_JUDGE_MODEL, PetriAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "petri"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Petri seed instructions into Harbor task directories")
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
        "--dataset-cache-dir",
        type=Path,
        default=DEFAULT_DATASET_CACHE_DIR,
        help="Where to clone the inspect-petri GitHub repo",
    )
    parser.add_argument(
        "--auditor-model",
        default=DEFAULT_AUDITOR_MODEL,
        help="Model the auditor uses to run the audit",
    )
    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help="Model the verifier uses to judge the audit",
    )
    args = parser.parse_args()

    adapter = PetriAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        dataset_cache_dir=args.dataset_cache_dir,
        auditor_model=args.auditor_model,
        judge_model=args.judge_model,
    )

    adapter.run()


if __name__ == "__main__":
    main()
