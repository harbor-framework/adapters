"""Task-generation entry point; does not invoke models or incur API costs."""

import argparse
import json
from pathlib import Path

from supergpqa.adapter import (
    ANSWER_HANDOFF,
    DATA_SHA256,
    PACKAGE_DIR,
    UPSTREAM_COMMIT,
    SuperGPQAAdapter,
    load_records,
    parity_subset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/supergpqa"))
    parser.add_argument(
        "--data-path", type=Path, help="Pinned upstream data/SuperGPQA-all.jsonl"
    )
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/supergpqa"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--task-ids", nargs="+", help="Upstream UUIDs or supergpqa-UUID names"
    )
    parser.add_argument("--split", choices=("full", "parity"), default="full")
    parser.add_argument(
        "--parity-size",
        type=int,
        help="Required for parity split; agree with team first",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.split == "parity" and args.parity_size is None:
        parser.error("--split parity requires an explicit --parity-size")
    if args.split == "full" and args.parity_size is not None:
        parser.error("--parity-size requires --split parity")
    rows = load_records(args.data_path, args.cache_dir)
    original_count = len(rows)
    if args.split == "parity":
        rows = parity_subset(rows, args.parity_size, args.seed)
    if args.task_ids:
        wanted = {x.removeprefix("supergpqa-") for x in args.task_ids}
        known = {row["uuid"] for row in rows}
        if wanted - known:
            parser.error(f"Unknown IDs in selected split: {sorted(wanted - known)}")
        rows = [row for row in rows if row["uuid"] in wanted]
    rows.sort(key=lambda row: row["uuid"])
    if args.limit:
        rows = rows[: args.limit]
    # Never leave unselected old tasks in a directory advertised as a subset.
    if args.output_dir.exists():
        selected = {SuperGPQAAdapter.task_id(row) for row in rows}
        stale = {p.name for p in args.output_dir.iterdir() if p.is_dir()} - selected
        if stale:
            parser.error(
                "Output contains tasks outside this selection; use a fresh output directory"
            )
    tasks = SuperGPQAAdapter(args.output_dir, rows, overwrite=args.overwrite).run()
    manifest = {
        "benchmark": "SuperGPQA",
        "upstream_commit": UPSTREAM_COMMIT,
        "data_sha256": DATA_SHA256,
        "original_count": original_count,
        "generated_count": len(tasks),
        "split": args.split,
        "parity_size": args.parity_size,
        "seed": args.seed,
        "mode": "zero-shot",
        "task_ids": [row["uuid"] for row in rows],
        "prompt_suffix": ANSWER_HANDOFF,
    }
    (args.output_dir / "generation_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    (args.output_dir / "UPSTREAM_LICENSE").write_bytes(
        (PACKAGE_DIR / "UPSTREAM_LICENSE").read_bytes()
    )
    (args.output_dir / "SOURCE_NOTICE.txt").write_text(
        "Contains information from SuperGPQA (M-A-P Team and coauthors), "
        "available under ODC-BY: https://opendatacommons.org/licenses/by/1-0/.\n"
        f"Source: https://github.com/SuperGPQA/SuperGPQA/tree/{UPSTREAM_COMMIT}\n"
        "Upstream third-party content notices also apply; see the source README.\n"
    )
    print(f"Generated {len(tasks)} tasks in {args.output_dir}")


if __name__ == "__main__":
    main()
