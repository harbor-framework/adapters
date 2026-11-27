import argparse
from pathlib import Path

from .adapter import ControlArenaInfraUnitTestsHonestAdapter


def main() -> None:
    cli = argparse.ArgumentParser(description="Generate the Infra add_unit_tests honest main task")
    cli.add_argument("--output-dir", type=Path, default=Path("datasets/control-arena-infra-unit-tests-honest"))
    cli.add_argument("--source-dir", type=Path, help="Existing pinned training directory containing train.py")
    cli.add_argument("--task-ids", nargs="+")
    cli.add_argument("--limit", type=int)
    cli.add_argument("--overwrite", action="store_true")
    args = cli.parse_args()
    try:
        for path in ControlArenaInfraUnitTestsHonestAdapter(**vars(args)).run():
            print(path)
    except ValueError as exc:
        cli.error(str(exc))


if __name__ == "__main__":
    main()
