"""
CLI entry point. Do not modify any of the existing flags.

Constructs the Adapter class defined in adapter.py and calls run() to generate tasks
in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import JUDGE_CHOICES, SPLITS, SUBSETS, OrBenchAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "or-bench"


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
        help="Only generate these task IDs (e.g. hard-1k-00007 or or-bench-hard-1k-00007)",
    )
    parser.add_argument(
        "--subsets",
        nargs="+",
        choices=SUBSETS,
        default=None,
        help="OR-Bench subsets to include (default: all three)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory with local or-bench-<subset>.csv files (default: download from HF)",
    )
    parser.add_argument(
        "--prebuilt-image",
        action="store_true",
        help="Set [environment].docker_image to the Dockerfile's base image so "
        "Harbor skips the per-task build (for fast full oracle runs; off by default)",
    )
    parser.add_argument(
        "--judge",
        choices=JUDGE_CHOICES,
        default="auto",
        help="Refusal judge written into each task. auto (default, as in the paper): "
        "keyword for 80k, LLM for hard-1k and toxic. keyword / llm: use that judge "
        "for every subset",
    )
    parser.add_argument(
        "--split",
        choices=SPLITS,
        default="full",
        help="full (default): all tasks. parity: 100 tasks per subset (300 in total), "
        "stratified by prompt category, seed 42",
    )
    args = parser.parse_args()

    adapter = OrBenchAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        data_dir=args.data_dir,
        subsets=args.subsets,
        prebuilt_image=args.prebuilt_image,
        judge=args.judge,
        split=args.split,
    )

    adapter.run()


if __name__ == "__main__":
    main()
