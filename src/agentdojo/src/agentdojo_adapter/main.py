"""
Generate AgentDojo tasks in Harbor format.

Usage:
    uv run agentdojo --output-dir ../../datasets/agentdojo
"""

import argparse
import logging
from pathlib import Path

from .adapter import (
    DEFAULT_ATTACK,
    DEFAULT_ATTACK_TARGET_MODEL,
    DEFAULT_BENCHMARK_VERSION,
    AgentDojoAdapter,
)

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "agentdojo"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

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
        help="Only generate these tasks (directory names, e.g. workspace-user_task_0 "
        "or workspace-user_task_0-injection_task_1)",
    )
    parser.add_argument(
        "--split",
        choices=["user", "attack", "all"],
        default="all",
        help="user: user tasks without injections; attack: every user task x injection "
        "task pair under the attack; all: both",
    )
    parser.add_argument(
        "--suites",
        nargs="+",
        default=None,
        help="Only these suites (workspace, travel, banking, slack)",
    )
    parser.add_argument(
        "--benchmark-version",
        default=DEFAULT_BENCHMARK_VERSION,
        help="AgentDojo benchmark version",
    )
    parser.add_argument(
        "--attack",
        default=DEFAULT_ATTACK,
        help="Registered AgentDojo attack used for the attack split",
    )
    parser.add_argument(
        "--attack-target-model",
        default=DEFAULT_ATTACK_TARGET_MODEL,
        help="Model id whose prose name is used by attacks that address the model by "
        "name (e.g. important_instructions)",
    )
    args = parser.parse_args()

    adapter = AgentDojoAdapter(
        args.output_dir,
        limit=args.limit,
        overwrite=args.overwrite,
        task_ids=args.task_ids,
        split=args.split,
        suites=args.suites,
        benchmark_version=args.benchmark_version,
        attack=args.attack,
        attack_target_model=args.attack_target_model,
    )

    adapter.run()


if __name__ == "__main__":
    main()
