import argparse
from pathlib import Path

from .adapter import ControlArenaShadeAccountingHonestAdapter


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the local-only SHADE accounting review.")
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/control-arena-shade-accounting-honest"))
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--fixture", action="store_true", help="Generate the separate scripted transport check")
    args = parser.parse_args()
    try:
        for path in ControlArenaShadeAccountingHonestAdapter(**vars(args)).run():
            print(path)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
