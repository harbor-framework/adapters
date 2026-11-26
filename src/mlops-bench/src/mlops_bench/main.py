"""
Main entry point for the template adapter. Do not modify any of the existing flags.
You can add any additional flags you need.

Constructs the Adapter class defined in adapter.py and calls run() to generate tasks
in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import UPSTREAM_COMMIT, MLOpsBenchAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "mlops-bench"


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
        help=(
            "Only generate these task IDs. Accepts upstream instance ids "
            "(MLO-...), generated slugs (mlo-...), or full task names."
        ),
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help=(
            "Path to a local clone of oracle-samples/mlops-bench. If omitted, "
            "the upstream repository is cloned at --source-ref."
        ),
    )
    parser.add_argument(
        "--source-ref",
        default=UPSTREAM_COMMIT,
        help="Upstream git ref to clone when --source-dir is not given (default: pinned commit)",
    )
    parser.add_argument(
        "--stage",
        nargs="+",
        default=None,
        help=(
            "Only generate tasks for these MLOps stages, e.g. MODEL_SERVING "
            "DATA_PIPELINE"
        ),
    )
    parser.add_argument(
        "--split",
        choices=["full", "parity"],
        default="full",
        help=(
            "full: all 212 tasks (default). parity: the 49-task parity subset "
            "(7 tasks per MLOps stage, fixed seed; see README)"
        ),
    )
    args = parser.parse_args()

    adapter = MLOpsBenchAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        source_dir=args.source_dir,
        source_ref=args.source_ref,
        stages=args.stage,
        split=args.split,
    )

    adapter.run()


if __name__ == "__main__":
    main()
