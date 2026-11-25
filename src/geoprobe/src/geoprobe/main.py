"""Canonical task-generation entry point."""
import argparse
from pathlib import Path

from .adapter import GeoProbeAdapter
from .sources import download


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the pinned 168-task GeoProbe dataset")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--data-root", type=Path, default=Path(".cache/geoprobe/5f729375"))
    parser.add_argument("--download", action="store_true", help="Fetch pinned GeoProbe assets first")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--task-ids", nargs="+", help="Upstream sample IDs or generated directory names")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    try:
        if args.download:
            download(args.data_root)
        generated = GeoProbeAdapter(args.output_dir, args.data_root, args.limit, args.overwrite, args.task_ids).run()
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
    print(f"Generated {len(generated)} GeoProbe tasks in {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
