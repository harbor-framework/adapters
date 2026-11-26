import argparse
from pathlib import Path

from .adapter import ControlArenaVllmHonestAdapter


def main():
    parser = argparse.ArgumentParser(description="Generate the honest vLLM rolling metrics maintenance task.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-cache", type=Path, default=Path(".cache/control-arena-vllm-honest"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--overwrite", action="store_true")
    try:
        args = parser.parse_args()
        paths = ControlArenaVllmHonestAdapter(**vars(args)).run()
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")
    print(f"Generated {len(paths)} vLLM metrics task(s) in {args.output_dir}")


if __name__ == "__main__":
    main()
