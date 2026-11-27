import argparse
from pathlib import Path

from .adapter import generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the honest Django enum migration task.")
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/control-arena-swe-django-honest"))
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        for path in generate(**vars(args)):
            print(path)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
