"""`uv run 4dcodebench`: generate Harbor tasks from a local 4DCodeBench checkout and its data."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .adapter import (
    DEFAULT_AGENT_IMAGE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SCORER_IMAGE,
    SPLITS,
    AdapterError,
    Harbor4DCodeBenchAdapter,
    configure_logging,
)

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="4dcodebench", description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help=f"directory to write generated tasks (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--limit", type=int, default=None, help="generate only the first N selected tasks")
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing tasks")
    parser.add_argument("--task-ids", nargs="+", default=None,
                        help="only these cases: task names (synthetic-b-01), <kind>/<case> or bare case names")
    parser.add_argument("--repo", type=Path, required=True,
                        help="a 4DCodeBench checkout (read-only), for the agent context and the commit")
    parser.add_argument("--cases-root", type=Path, default=None,
                        help="<kind>/<case>/reference.mp4 (default: <repo>/cases, where the upstream "
                             "scripts/download_data.py writes them)")
    parser.add_argument("--data-root", type=Path, default=None,
                        help="<kind>/<case>/{world,annotation,estimates}/ (default: <repo>/data)")
    parser.add_argument("--split", choices=SPLITS, default="all", help="which cases to generate")
    parser.add_argument("--agent-image", default=DEFAULT_AGENT_IMAGE,
                        help=f"upstream agent image the environment builds FROM (default: {DEFAULT_AGENT_IMAGE})")
    parser.add_argument("--scorer-image", default=DEFAULT_SCORER_IMAGE,
                        help="upstream scorer image with /checkpoints that the verifier builds FROM "
                             f"(default: {DEFAULT_SCORER_IMAGE})")
    parser.add_argument("--agent-network", choices=("public", "allowlist"), default="public",
                        help="agent-phase network: public, as upstream, or an allowlist")
    parser.add_argument("--agent-allowed-host", action="append", default=[], dest="agent_allowed_hosts",
                        help="a host the agent may reach under --agent-network allowlist; repeatable "
                             "(Harbor adds the agent's inference host itself)")
    parser.add_argument("--skip-incomplete", action="store_true",
                        help="skip cases whose reference data is missing instead of failing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    configure_logging()
    args = parse_args(argv)
    try:
        adapter = Harbor4DCodeBenchAdapter(
            args.output_dir,
            limit=args.limit,
            overwrite=args.overwrite,
            task_ids=args.task_ids,
            repo=args.repo,
            cases_root=args.cases_root,
            data_root=args.data_root,
            split=args.split,
            agent_image=args.agent_image,
            scorer_image=args.scorer_image,
            agent_network=args.agent_network,
            agent_allowed_hosts=args.agent_allowed_hosts,
            skip_incomplete=args.skip_incomplete,
        )
        adapter.run()
    except AdapterError as error:
        logger.error("%s", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
