import argparse
from pathlib import Path

from .adapter import ControlArenaIaCHonestAdapter


def main() -> None:
    cli = argparse.ArgumentParser(description="Generate five offline ControlArena IaC tasks")
    cli.add_argument("--output-dir", type=Path)
    cli.add_argument("--setting", choices=["iac", "iac_fast"], default="iac")
    cli.add_argument("--limit", type=int)
    cli.add_argument("--overwrite", action="store_true")
    cli.add_argument("--task-ids", nargs="+", help="Native objective IDs, task names or registry IDs")
    try:
        args = cli.parse_args()
        args.output_dir = args.output_dir or Path("datasets") / ("control-arena-" + args.setting.replace("_", "-") + "-honest")
        paths = ControlArenaIaCHonestAdapter(**vars(args)).run()
    except ValueError as error:
        cli.error(str(error))
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
