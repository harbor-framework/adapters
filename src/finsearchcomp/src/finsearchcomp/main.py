"""Generate FinSearchComp (T1 + T2 + T3) tasks in Harbor format."""

import argparse
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from finsearchcomp.adapter import FinSearchCompAdapter
else:
    from .adapter import FinSearchCompAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate FinSearchComp tasks in Harbor format")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets/finsearchcomp"),
        help="Output directory for tasks (default: datasets/finsearchcomp)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Generate only the first N tasks")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing tasks")
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Only generate these tasks (sanitized id, e.g. t2-simple-historical-lookup-001, "
        "or upstream prompt_id)",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=None,
        help="Local copy of data/finsearchcomp_data.json at the pinned commit "
        "(default: download it)",
    )
    parser.add_argument(
        "--akshare-data-file",
        type=Path,
        default=None,
        help="Local copy of data/finsearchcomp_akshare_version.json at the pinned commit "
        "(T1 source; default: download it)",
    )
    parser.add_argument(
        "--tiers",
        nargs="+",
        choices=["t1", "t2", "t3"],
        default=["t1", "t2", "t3"],
        help="Tiers to generate (default: t1 t2 t3)",
    )
    parser.add_argument(
        "--t1-snapshot-dir",
        type=Path,
        default=None,
        help="Directory of upstream-format market snapshots (e.g. us_stock_20261121T020000Z.csv). "
        "Each T1 task embeds its ground truth from here, labelled with the snapshot date. "
        "Needs `uv run --extra t1`.",
    )
    parser.add_argument(
        "--fetch-t1-snapshot",
        action="store_true",
        help="Fetch a fresh snapshot from AkShare into --t1-snapshot-dir first (~15 min)",
    )
    args = parser.parse_args()

    adapter = FinSearchCompAdapter(
        output_dir=args.output_dir,
        limit=args.limit,
        overwrite=args.overwrite,
        task_ids=args.task_ids,
        data_file=args.data_file,
        akshare_data_file=args.akshare_data_file,
        tiers=args.tiers,
        t1_snapshot_dir=args.t1_snapshot_dir,
        fetch_t1_snapshot=args.fetch_t1_snapshot,
    )
    try:
        adapter.run()
    except Exception as e:
        logger.error("Failed to generate tasks: %s", e)
        sys.exit(1)
    logger.info("Generated %d tasks in %s", adapter.generated_count, args.output_dir)


if __name__ == "__main__":
    main()
