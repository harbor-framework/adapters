import argparse
from pathlib import Path

from .adapter import generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reviewed ControlArena APPS honest tasks.")
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/control-arena-apps-honest"))
    parser.add_argument("--task-ids", nargs="+", help="Task names or control-arena/ registry IDs")
    parser.add_argument("--limit", type=int, help="Maximum number of selected tasks")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing generated tasks")
    args = parser.parse_args()
    try:
        for path in generate(**vars(args)):
            print(path)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
