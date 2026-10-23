"""Generate AgentPersonaBench survey tasks in Harbor format."""

import argparse
import logging
import os
from pathlib import Path

from .adapter import AgentPersonaBenchAdapter

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "agentpersonabench"
PARITY_TASK_IDS = {
    "survey": [],
    "web": ["vaccines-opposed-web", "wellness-web"],
    "app": ["no-budget-apps-app"],
    "chat": ["vaccines-opposed-chat", "wellness-chat"],
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate AgentPersonaBench survey tasks in Harbor format"
    )
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
        help="Only generate these task slugs (survey directory names)",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=os.environ.get("APB_SOURCE"),
        help="AgentPersonaBench checkout (directory containing tasks/). "
        "Defaults to $APB_SOURCE.",
    )
    parser.add_argument(
        "--surface",
        choices=("survey", "web", "app", "chat"),
        default="survey",
        help="Task surface to generate.",
    )
    parser.add_argument(
        "--split",
        choices=("all", "parity"),
        default="all",
        help="Generate the full surface or its recorded parity subset.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    task_ids = args.task_ids
    if args.split == "parity" and task_ids is None:
        task_ids = PARITY_TASK_IDS[args.surface]
    adapter = AgentPersonaBenchAdapter(
        output_dir=args.output_dir,
        limit=args.limit,
        overwrite=args.overwrite,
        task_ids=task_ids,
        source=args.source,
        surface=args.surface,
    )
    adapter.run()


if __name__ == "__main__":
    main()
