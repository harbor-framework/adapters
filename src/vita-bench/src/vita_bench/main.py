"""
Main entry point for the template adapter. Do not modify any of the existing flags.
You can add any additional flags you need.

Constructs the Adapter class defined in adapter.py and calls run() to generate tasks
in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import VitaBenchAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "vita-bench"

# Parity subset (5% of 400): 5 tasks per domain, drawn once with
# random.Random(20261120).sample over the sorted task ids of each domain.
PARITY_TASK_IDS = [
    "vita-delivery-80715001",
    "vita-delivery-90721002",
    "vita-delivery-d0716001",
    "vita-delivery-e0716001",
    "vita-delivery-e0721004",
    "vita-instore-10826018",
    "vita-instore-10826030",
    "vita-instore-10826073",
    "vita-instore-10826302",
    "vita-instore-10826306",
    "vita-ota-70807003",
    "vita-ota-70807006",
    "vita-ota-70807007",
    "vita-ota-70812008",
    "vita-ota-d0807003",
    "vita-cross-10807014",
    "vita-cross-10808007",
    "vita-cross-10811010",
    "vita-cross-10811015",
    "vita-cross-a0805002",
]


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
        help="Only generate these task IDs",
    )
    parser.add_argument(
        "--oracle-dir",
        type=Path,
        default=None,
        help="Read oracle trajectories from this dir instead of src/vita-bench/oracle "
        "(e.g. staged candidates from scripts/build_oracle.py --out)",
    )
    parser.add_argument(
        "--split",
        choices=("full", "parity"),
        default="full",
        help="'parity' generates only the parity subset (PARITY_TASK_IDS)",
    )
    args = parser.parse_args()
    if args.split == "parity":
        if args.task_ids:
            parser.error("--split parity cannot be combined with --task-ids")
        args.task_ids = PARITY_TASK_IDS

    adapter = VitaBenchAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        oracle_dir=args.oracle_dir,
    )

    adapter.run()


if __name__ == "__main__":
    main()
