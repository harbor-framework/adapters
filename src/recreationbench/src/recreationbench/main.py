"""
Main entry point for the template adapter. Do not modify any of the existing flags.
You can add any additional flags you need.

Constructs the Adapter class defined in adapter.py and calls run() to generate tasks
in the Harbor format at the configured output directory.
"""

import argparse
from pathlib import Path

from .adapter import RecreationBenchAdapter

# Default output dir: <repo>/datasets/<adapter_id>
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "recreationbench"


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
        "--split",
        choices=["full", "parity"],
        default="full",
        help="full: all 50 Web tasks; parity: the difficulty-stratified parity subset",
    )
    parser.add_argument(
        "--rb-repo",
        type=Path,
        default=None,
        help="Existing RecreationWorld checkout at the pinned commit (cloned into the cache when omitted)",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=None,
        help="Existing Qwen/RecreationBench copy laid out as web/<task-id>/... (downloaded when omitted)",
    )
    parser.add_argument(
        "--open-network",
        action="store_true",
        help="Generate tasks without the network allowlist (for engines that cannot enforce one, "
        "such as Docker Desktop); not the benchmark's protocol",
    )
    parser.add_argument(
        "--allow-agent-host",
        action="append",
        default=[],
        metavar="HOST",
        help="Extra host the agent phase may reach (repeatable), e.g. the model gateway used with RB_MODEL_BASE_URL",
    )
    parser.add_argument(
        "--allow-verifier-host",
        action="append",
        default=[],
        metavar="HOST",
        help="Extra host the verifier may reach (repeatable), e.g. a judge endpoint not on the default list",
    )
    args = parser.parse_args()

    adapter = RecreationBenchAdapter(
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        task_ids=args.task_ids,
        rb_repo=args.rb_repo,
        dataset_dir=args.dataset_dir,
        open_network=args.open_network,
        split=args.split,
        agent_hosts=args.allow_agent_host,
        verifier_hosts=args.allow_verifier_host,
    )

    adapter.run()


if __name__ == "__main__":
    main()
