"""Generate ARE v1.1 Harbor tasks from the AutoResearchExam v1.0 release.

    uv run autoresearch-exam --output-dir datasets/autoresearch-exam
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import tempfile
from pathlib import Path

from autoresearch_exam.adapter import AutoResearchExamAdapter

SOURCE_REPO = "https://github.com/bespokelabsai/AutoResearchExam.git"
SOURCE_TAG = "v1.0"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output-dir", type=Path, default=Path("datasets/autoresearch-exam"))
    p.add_argument("--task-ids", nargs="+", help="convert only these tasks")
    p.add_argument("--limit", type=int, help="convert only the first N tasks")
    p.add_argument("--overwrite", action="store_true", help="replace existing task directories")
    p.add_argument("--source-dir", type=Path,
                   help=f"local checkout of AutoResearchExam {SOURCE_TAG} (default: clone it)")
    a = p.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        source = a.source_dir
        if source is None:
            source = Path(tmp) / "AutoResearchExam"
            logger.info("cloning %s at %s", SOURCE_REPO, SOURCE_TAG)
            subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--branch", SOURCE_TAG,
                            SOURCE_REPO, str(source)], check=True)
        adapter = AutoResearchExamAdapter(source.resolve(), a.output_dir.resolve())
        ids = a.task_ids or adapter.task_ids()
        if a.limit is not None:
            ids = ids[: a.limit]
        a.output_dir.mkdir(parents=True, exist_ok=True)
        n = adapter.run(ids, overwrite=a.overwrite)
    logger.info("wrote %d task(s) to %s", n, a.output_dir)


if __name__ == "__main__":
    main()
