"""
Main entry point for the CAIBench adapter. Do not modify any of the existing flags.
You can add any additional flags you need.

Constructs the CAIBenchAdapter class defined in adapter.py and calls run() to generate
tasks in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import SUB_BENCHMARKS, CYBERMETRIC_SIZES, DEFAULT_CYBERMETRIC_SIZE, DEFAULT_DATASET_CACHE_DIR, CAIBenchAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "caibench"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert CAIBench's Security Knowledge and Privacy sub-benchmarks into Harbor task directories")
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
        "--sub-benchmarks",
        nargs="+",
        default=None,
        choices=SUB_BENCHMARKS,
        help="Only generate these sub-benchmarks (all by default)",
    )
    parser.add_argument(
        "--dataset-cache-dir",
        type=Path,
        default=DEFAULT_DATASET_CACHE_DIR,
        help="Where to download the datasets",
    )
    parser.add_argument(
        "--cybermetric-size",
        type=int,
        default=DEFAULT_CYBERMETRIC_SIZE,
        choices=CYBERMETRIC_SIZES,
        help="Which CyberMetric-{size}-v1.json variant to use",
    )
    args = parser.parse_args()

    adapter = CAIBenchAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        sub_benchmarks=args.sub_benchmarks,
        dataset_cache_dir=args.dataset_cache_dir,
        cybermetric_size=args.cybermetric_size,
    )

    adapter.run()


if __name__ == "__main__":
    main()
