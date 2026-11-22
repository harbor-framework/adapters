import argparse
from pathlib import Path

from .adapter import AgentClinicAdapter

DATASETS_DIR = Path(__file__).resolve().parents[4] / "datasets"


def default_output_dir(split: str) -> Path:
    return DATASETS_DIR / ("agentclinic-parity" if split == "parity" else "agentclinic")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to write generated tasks (default: datasets/agentclinic, or datasets/agentclinic-parity for --split parity)",
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
        "--split",
        choices=["full", "parity"],
        default="full",
        help="full: all 215 MedQA extended cases; parity: the fixed 22-case parity subset",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Local agentclinic_medqa_extended.jsonl; downloaded from the pinned upstream commit when omitted",
    )
    args = parser.parse_args(argv)

    adapter = AgentClinicAdapter(
        args.output_dir or default_output_dir(args.split),
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        split=args.split,
        source=args.source,
    )

    adapter.run()


if __name__ == "__main__":
    main()
