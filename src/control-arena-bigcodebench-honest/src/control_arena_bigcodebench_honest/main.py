import argparse
from pathlib import Path

from .adapter import ControlArenaBigCodeBenchHonestAdapter


def main() -> None:
    cli = argparse.ArgumentParser(description="Generate the three reviewed BigCodeBench HONEST tasks")
    cli.add_argument("--output-dir", type=Path, default=Path("datasets/control-arena-bigcodebench-honest"))
    cli.add_argument("--limit", type=int)
    cli.add_argument("--overwrite", action="store_true")
    cli.add_argument("--task-ids", nargs="+", help="Upstream IDs, local names or registry IDs")
    cli.add_argument("--source-parquet", type=Path, help="Use a local copy of the pinned public Parquet")
    try:
        paths = ControlArenaBigCodeBenchHonestAdapter(**vars(cli.parse_args())).run()
    except ValueError as error:
        cli.error(str(error))
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
