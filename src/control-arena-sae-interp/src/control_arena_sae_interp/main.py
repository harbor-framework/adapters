import argparse
from pathlib import Path

from .adapter import ControlArenaSAEInterpAdapter


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ControlArena SAE interpretation tasks.")
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/control-arena-sae-interp"))
    parser.add_argument("--limit", type=int, help="Maximum number of selected tasks to export")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate existing tasks")
    parser.add_argument("--task-ids", nargs="+", help="One or more task names or registry IDs")
    args = parser.parse_args()
    try:
        paths = ControlArenaSAEInterpAdapter(**vars(args)).run()
    except ValueError as exc:
        parser.error(str(exc))
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
