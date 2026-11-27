import argparse
from pathlib import Path

from .adapter import ControlArenaDataQualityHonestAdapter


def main():
    parser = argparse.ArgumentParser(description="Generate seven honest factual-accuracy monitor-data tasks.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--overwrite", action="store_true")
    try:
        options = parser.parse_args()
        paths = ControlArenaDataQualityHonestAdapter(**vars(options)).run()
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")
    print(f"Generated {len(paths)} factual-accuracy tasks in {options.output_dir}")


if __name__ == "__main__":
    main()
