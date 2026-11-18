"""Generate frozen tasks for one or all six BALROG environments."""

import argparse
from pathlib import Path

from .adapter import BALROGAdapter, default_source_directory


DEFAULT_OUTPUT_DIR = Path("datasets") / "balrog"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate frozen BALROG tasks; defaults to BabyAI for compatibility.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory to write generated tasks")
    parser.add_argument("--limit", type=int, default=None, help="Generate only the first N selected tasks in manifest order")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing task after checking its path")
    parser.add_argument("--task-ids", nargs="+", default=None, help="Only generate these task IDs")
    parser.add_argument("--split", choices=("full", "sanity", "parity"), default="full", help="full/parity: every frozen case in selected environments; sanity: seed 0 for each task type")
    parser.add_argument("--benchmark-source", type=Path, default=default_source_directory("BALROG"), help="BALROG Git checkout at the required commit")
    parser.add_argument("--environments", nargs="+", choices=("all", "babyai", "babaisai", "textworld", "crafter", "nle", "minihack"), default=["babyai"], help="Environment selection; all includes the six original BALROG environments")
    parser.add_argument("--assets-dir", type=Path, help="Directory holding pinned source/asset archives listed in fixtures/runtime_sources.json")
    parser.add_argument("--minigrid-source", type=Path, default=default_source_directory("minigrid-source"), help="BartekCupial/Minigrid Git checkout at the required commit")
    args = parser.parse_args()
    try:
        adapter = BALROGAdapter(**vars(args))
        for path in adapter.run():
            print(f"Generated {path}")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
