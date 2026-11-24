#!/usr/bin/env python3
"""Download this task's frozen reference from the pinned dataset revision.

Runs at image build time. Only ``web/<task>/reference`` and ``instance.json`` are
fetched; the hidden tests are not part of the image (Harbor uploads them for the
verifier). The Hub throttles anonymous clients on many small files, so the download
is retried and resumes where it stopped.
"""

import os
import shutil
import sys
import tarfile
import time
from pathlib import Path

from huggingface_hub import snapshot_download

TASK_ID = os.environ["RB_TASK_ID"]
DATASET = os.environ["RB_DATASET"]
REVISION = os.environ["RB_DATASET_REVISION"]
INPUT_ROOT = Path("/opt/rb-input")


def download() -> Path:
    patterns = [f"web/{TASK_ID}/reference/**", f"web/{TASK_ID}/instance.json", f"web/{TASK_ID}/LICENSE"]
    for attempt in range(1, 31):
        try:
            snapshot_download(
                DATASET,
                repo_type="dataset",
                revision=REVISION,
                local_dir=str(INPUT_ROOT),
                allow_patterns=patterns,
                max_workers=8,
            )
            return INPUT_ROOT / "web" / TASK_ID
        except Exception as error:  # noqa: BLE001 - resume on any transport failure
            print(f"download attempt {attempt} failed: {error!r}"[:400], file=sys.stderr)
            time.sleep(min(60, 5 * attempt))
    raise SystemExit("reference download did not complete")


def pack_site(instance: Path) -> None:
    """The runner reads reference/reference.tar.gz; the dataset ships site/ unpacked."""
    reference = instance / "reference"
    site = reference / "site"
    archive = reference / "reference.tar.gz"
    if archive.is_file():
        return
    if not (site / "index.html").is_file():
        raise SystemExit(f"reference site is incomplete: {site}")
    with tarfile.open(archive, "w:gz", compresslevel=1) as tar:
        tar.add(site, arcname="site")
    # The served copy is extracted from the archive; keep one packed copy as input.
    shutil.rmtree(site)


def main() -> None:
    instance = download()
    for name in ("task.json", "site_meta.json"):
        if not (instance / "reference" / name).is_file():
            raise SystemExit(f"reference/{name} missing for {TASK_ID}")
    pack_site(instance)
    shutil.rmtree(INPUT_ROOT / ".cache", ignore_errors=True)
    print(f"reference ready for {TASK_ID}")


if __name__ == "__main__":
    main()
