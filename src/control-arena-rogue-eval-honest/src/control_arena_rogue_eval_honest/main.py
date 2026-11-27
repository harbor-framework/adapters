import argparse
from pathlib import Path

from .adapter import ControlArenaRogueEvalHonestAdapter


def main() -> None:
    cli = argparse.ArgumentParser(description="Generate ControlArena's honest two-digit addition task")
    cli.add_argument("--output-dir", type=Path)
    cli.add_argument("--limit", type=int)
    cli.add_argument("--task-ids", nargs="+")
    cli.add_argument("--overwrite", action="store_true")
    cli.add_argument("--fixture", action="store_true", help="Generate a separate, model-free transport fixture")
    try:
        args = cli.parse_args()
        if args.output_dir is None:
            folder = "control-arena-rogue-eval-transport" if args.fixture else "control-arena-rogue-eval-honest"
            args.output_dir = Path("datasets") / folder
        paths = ControlArenaRogueEvalHonestAdapter(**vars(args)).run()
    except ValueError as error:
        cli.error(str(error))
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
