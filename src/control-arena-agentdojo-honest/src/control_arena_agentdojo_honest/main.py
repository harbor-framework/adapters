import argparse
from pathlib import Path

from .adapter import ControlArenaAgentdojoHonestAdapter


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the read-only AgentDojo travel tasks.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--task-ids", nargs="+")
    args = parser.parse_args()
    try:
        paths = ControlArenaAgentdojoHonestAdapter(**vars(args)).run()
    except (ValueError, FileExistsError) as exc:
        parser.exit(2, f"{exc}\n")
    print(f"Generated {len(paths)} travel tasks in {args.output_dir}")


if __name__ == "__main__":
    main()
