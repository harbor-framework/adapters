"""CLI entry point: generate Auditing Sabotage Bench tasks in Harbor format."""

import argparse
from pathlib import Path

from .adapter import SUBSETS, AuditingSabotageBenchAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[4] / "datasets" / "auditing-sabotage-bench"
)


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
        help="Only generate these task IDs (upstream ids such as negative_mute, or task slugs)",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Existing checkout of ejcgan/auditing-sabotage-bench (default: clone the pinned commit)",
    )
    parser.add_argument(
        "--subset",
        choices=SUBSETS,
        default="normal",
        help="normal = the paper's 20 core samples (default); persuasion, red_team, fixed or all",
    )
    args = parser.parse_args()

    adapter = AuditingSabotageBenchAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        source_dir=args.source_dir,
        subset=args.subset,
    )

    adapter.run()


if __name__ == "__main__":
    main()
