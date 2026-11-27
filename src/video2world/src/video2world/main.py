import argparse
import subprocess
from pathlib import Path

from .adapter import Video2WorldAdapter


def main():
    parser = argparse.ArgumentParser(
        description="Generate Video2World tasks from the pinned upstream release"
    )
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--runtime-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--task-ids", nargs="+", help="exact upstream family/sample keys"
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--split", choices=("full", "parity"), default="full")
    args = parser.parse_args()
    try:
        result = Video2WorldAdapter(**vars(args)).run()
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(1, f"video2world: {exc}\n")
    print(f"Generated {len(result)} tasks in {args.output_dir}")


if __name__ == "__main__":
    main()
