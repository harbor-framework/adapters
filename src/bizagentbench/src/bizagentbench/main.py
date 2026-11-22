from __future__ import annotations

import argparse
from pathlib import Path
from .adapter import BizAgentBenchAdapter


def main():
    parser = argparse.ArgumentParser(description="Generate native BizAgentBench Harbor tasks")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True, help="Clean pinned upstream checkout")
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--model-config", type=Path)
    parser.add_argument("--oracle-dir", type=Path)
    args = parser.parse_args()
    generated = BizAgentBenchAdapter(**vars(args)).run()
    print(f"Generated {len(generated)} tasks in {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
