"""CPU-only task generation CLI (upstream CUDA dependencies live in the task image)."""

import argparse
from pathlib import Path

from .adapter import FlashInferBenchAdapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--source",
        type=Path,
        help="Local trace Git repository containing the pinned revision",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--target-gpu", default="B200")
    args = parser.parse_args()
    report = FlashInferBenchAdapter(**vars(args)).run()
    print(
        f"Generated {len(report['selected'])} tasks; {len(report['excluded'])} definitions excluded. See scope.json."
    )


if __name__ == "__main__":
    main()
