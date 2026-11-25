from __future__ import annotations

import argparse
from pathlib import Path

from .adapter import SWEBenchProMaxAdapter

DEFAULT_OUTPUT_DIR = Path.cwd() / "datasets" / "swebench_promax"


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert SWE-Bench-ProMax instances to Harbor task directories")
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Where task directories are written")
    ap.add_argument("--task-ids", nargs="+", default=None, help="Only these instance ids")
    ap.add_argument("--limit", type=int, default=None, help="Generate at most N tasks")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing task directories")
    ap.add_argument("--languages", nargs="+", default=None,
                    help="Only these languages (c, c++, go, java, python, rust, typescript)")
    ap.add_argument("--split", choices=["full", "parity"], default="full",
                    help="'parity' generates only the ids listed in parity_task_ids.txt")
    ap.add_argument("--data-dir", type=Path, default=None,
                    help="Local folder with swe-bench-promax.json and eval.json (default: download pinned HF revision)")
    ap.add_argument("--agent-timeout", type=float, default=7200.0)
    ap.add_argument("--verifier-timeout", type=float, default=7800.0,
                    help="Whole verifier phase: up to 3 eval runs of 2400 s each (as upstream) plus patch apply")
    a = ap.parse_args()

    task_ids = a.task_ids
    if a.split == "parity":
        if task_ids:
            ap.error("--split parity and --task-ids cannot be combined")
        f = Path(__file__).parent / "parity_task_ids.txt"  # shipped inside the package
        task_ids = [l.strip() for l in f.read_text().splitlines() if l.strip()]

    SWEBenchProMaxAdapter(
        output_dir=a.output_dir,
        task_ids=task_ids,
        limit=a.limit,
        overwrite=a.overwrite,
        data_dir=a.data_dir,
        languages=a.languages,
        agent_timeout=a.agent_timeout,
        verifier_timeout=a.verifier_timeout,
    ).run()


if __name__ == "__main__":
    main()
