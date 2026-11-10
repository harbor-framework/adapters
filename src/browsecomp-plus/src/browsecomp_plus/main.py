"""Generate BrowseComp-Plus tasks without requiring a Harbor source checkout."""

import argparse
import logging
import shutil
from collections.abc import Iterable, Sequence
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import snapshot_download

from .adapter import BrowseCompPlusAdapter

DEFAULT_OUTPUT_DIR = Path("datasets") / "browsecomp-plus"
INDEX_REPO_ID = "Tevatron/browsecomp-plus-indexes"
PARITY_TASK_COUNT = 30

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _has_bm25_index(indices_dir: Path) -> bool:
    bm25_dir = indices_dir / "bm25"
    return bm25_dir.is_dir() and any(bm25_dir.iterdir())


def _reuse_indices(source: Path, target: Path) -> None:
    if source.resolve() == target.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(source, target_is_directory=True)
    except OSError:
        # A partial indices/ directory from an interrupted run may already exist.
        shutil.copytree(source, target, dirs_exist_ok=True)


def prepare_data(
    output_dir: Path,
    *,
    indices_dir: Path | None = None,
    skip_download: bool = False,
) -> None:
    """Place the BM25 index at the path mounted by generated tasks.

    Historical model runs are separate parity evidence and are never needed for
    generation. ``skip_download`` permits generation-only smoke tests; it does
    not make the generated retrieval tasks runnable without a BM25 index.
    """
    target = output_dir / "indices"
    if indices_dir is not None:
        source = indices_dir.expanduser().resolve()
        if not _has_bm25_index(source):
            raise FileNotFoundError(
                f"--indices-dir must contain a non-empty bm25/ directory: {source}"
            )
        _reuse_indices(source, target)
        return
    if _has_bm25_index(target):
        logger.debug("Reusing BM25 index at %s", target)
        return
    if skip_download:
        logger.warning(
            "Skipping index download. Generated tasks require indices/bm25 before evaluation."
        )
        return

    logger.info("Downloading the BM25 index to %s", target)
    snapshot_download(
        repo_id=INDEX_REPO_ID,
        repo_type="dataset",
        allow_patterns=["bm25/*"],
        local_dir=target,
    )
    if not _has_bm25_index(target):
        raise FileNotFoundError(
            f"BM25 index download produced no index files: {target}"
        )


def _split_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BrowseComp-Plus Adapter")
    parser.add_argument(
        "--output-dir",
        "--output-path",
        dest="output_dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Target directory for generated tasks (default: ./{DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Explicit query_id values to generate (space-separated).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of tasks generated after filtering.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing task directories.",
    )
    parser.add_argument(
        "--split",
        choices=["full", "parity"],
        default="full",
        help="Full test set, or the first 30 test rows in historical dataset order.",
    )
    parser.add_argument(
        "--indices-dir",
        type=Path,
        default=None,
        help="Reuse an existing indices directory containing bm25/ without downloading.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip index download for generation-only checks; dataset loading still uses its cache or Hugging Face.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Randomly sample N tasks before generation. Use -1 for the full selected split.",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=42,
        help="Random seed used with --sample-size.",
    )
    parser.add_argument(
        "--indices",
        type=str,
        default=None,
        help="Legacy alias: comma-separated list of dataset indices to generate.",
    )
    parser.add_argument(
        "--query-ids",
        type=str,
        default=None,
        help="Legacy alias: comma-separated list of query_id values to generate.",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be non-negative")
    if (
        args.sample_size is not None
        and args.sample_size != -1
        and args.sample_size <= 0
    ):
        parser.error("--sample-size must be positive or -1")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve()

    logger.info("Loading BrowseComp-Plus dataset...")
    dataset = load_dataset("Tevatron/browsecomp-plus", split="test")
    if len(dataset) == 0:
        raise ValueError("The BrowseComp-Plus test dataset is empty")
    if args.split == "parity":
        dataset = dataset.select(range(min(PARITY_TASK_COUNT, len(dataset))))

    task_ids = _unique([*(args.task_ids or []), *_split_csv_values(args.query_ids)])
    if task_ids:
        target_ids = set(task_ids)
        dataset = dataset.filter(lambda example: str(example["query_id"]) in target_ids)
        matched_ids = {str(example["query_id"]) for example in dataset}
        missing_ids = target_ids - matched_ids
        if missing_ids:
            raise ValueError(
                f"Requested query_ids were not found in the {args.split} split: {sorted(missing_ids)}"
            )
    elif args.indices:
        selected_indices = [int(index) for index in _split_csv_values(args.indices)]
        if not selected_indices or any(
            index < 0 or index >= len(dataset) for index in selected_indices
        ):
            raise ValueError(
                "--indices must contain valid non-negative dataset indices"
            )
        dataset = dataset.select(selected_indices)
    elif args.sample_size is not None and args.sample_size > 0:
        sample_size = min(args.sample_size, len(dataset))
        dataset = dataset.shuffle(seed=args.sample_seed).select(range(sample_size))

    if args.limit is not None:
        dataset = dataset.select(range(min(args.limit, len(dataset))))

    output_dir.mkdir(parents=True, exist_ok=True)
    prepare_data(
        output_dir,
        indices_dir=args.indices_dir,
        skip_download=args.skip_download,
    )
    adapter = BrowseCompPlusAdapter(output_dir=output_dir, dataset=dataset)
    logger.info("Generating %s tasks...", len(dataset))
    generated, skipped_existing, total = adapter.run(overwrite=args.overwrite)
    # Legacy adapter.run logs individual failures and continues. Surface those
    # failures to shell callers instead of claiming a successful partial export.
    if generated + skipped_existing != total:
        raise RuntimeError(
            f"Task generation incomplete: {generated} generated, {skipped_existing} skipped, {total} expected"
        )

    logger.info(
        "BrowseComp-Plus generation complete: %s generated, %s skipped (existing), %s total. Output: %s",
        generated,
        skipped_existing,
        total,
        output_dir,
    )


if __name__ == "__main__":
    main()
