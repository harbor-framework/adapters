"""CLI entry point: ``uv run threedcodebench --output-dir <path>``."""

import argparse
from pathlib import Path

from .adapter import ThreeDCodeBenchAdapter
from .parity import PARITY_TASK_IDS

# Default output dir: <repo>/datasets/threedcodebench
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "threedcodebench"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Harbor tasks for 3DCodeBench (text-to-3D, coding-agent setting)."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write generated tasks",
    )
    parser.add_argument(
        "--split",
        choices=["full", "parity"],
        default="full",
        help="full: all 212 tasks. parity: the 50-task subset used for the parity "
        "experiment (see parity.py)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Generate only the first N tasks (sorted by upstream instance name)",
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
        help="Only generate these tasks (Harbor ids like armchair-seed0 or upstream ids like ArmChair_seed0)",
    )
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        default=None,
        help="Local copy of the HF 3DCodeBench/ folder (<Category>_seed0/ subdirs). "
        "Default: download the pinned revision from huggingface.co/datasets/YipengGao/3DCode",
    )
    parser.add_argument(
        "--upstream-dir",
        type=Path,
        default=None,
        help="Local checkout of github.com/gaoypeng/3dcodebench at the pinned commit. "
        "Default: shallow-fetch the pinned commit",
    )
    args = parser.parse_args()
    task_ids = args.task_ids
    if args.split == "parity":
        if task_ids:
            parser.error("--task-ids cannot be combined with --split parity")
        task_ids = list(PARITY_TASK_IDS)

    adapter = ThreeDCodeBenchAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=task_ids,
        benchmark_dir=args.benchmark_dir,
        upstream_dir=args.upstream_dir,
    )

    adapter.run()


if __name__ == "__main__":
    main()
