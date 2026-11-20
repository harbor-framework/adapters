"""Reproduce the attribution calibration from published inputs.

Usage (from src/contextbench):

    uv run python -m parity.calibrate [--work-dir DIR] [--update]

The script

1. fetches the parity bundle files that calibration reads from the Hugging Face
   dataset harborframework/parity-experiments at a pinned revision, and checks
   every file against the bundle's checksum manifest, whose own SHA-256 is
   pinned here;
2. fetches each task repository at its base commit from GitHub;
3. calibrates the 2026-08-21 corpus and the 30 trajectories of the three-run
   parity experiment, and compares the results with the pinned summaries in
   this directory.

It exits non-zero when a checksum or a summary differs. `--update` rewrites the
pinned summaries instead; use it only together with an `attribution_version`
bump. Passing this script is the required check before any change to the
attribution code is merged (see ATTRIBUTION.md).

The work directory keeps the downloads between runs. Pointing
CONTEXTBENCH_CALIBRATION_DIR at it enables the retained-corpus tests.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from contextbench.adapter import sha256_file
from parity.calibration import (
    PARITY_RUNS_SUMMARY_PATH,
    RETAINED_CORPUS,
    SUMMARY_PATH,
    calibrate,
    parity_run_corpus,
    retained_corpus,
)
from parity.files import write_json

REPOSITORY = "harborframework/parity-experiments"
# The head of refs/pr/269 when calibration was pinned.
REVISION = "8d887bf0ff1ee04a8a6307d85dd187994375e0d8"
BUNDLE_PATH = "adapters/contextbench"
MANIFEST_SHA256 = "b962617a9929a6b9a6ea28fd188979846f8f7e0092d2a0a9bca1c79b7bc4ba45"
_BASE_URL = (
    f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/{BUNDLE_PATH}"
)


def _needed(path: str) -> bool:
    """Return whether calibration or the retained-corpus tests read a bundle file."""
    parts = path.split("/")
    if parts[0] == "provenance":
        if parts[1] != RETAINED_CORPUS:
            return False
        if len(parts) == 3:
            return parts[2] in {"task-map.json", "contextbench-subset.parquet"}
        # The production-scorer test also reads each trial's scorer inputs.
        return parts[2] == "harbor-scorer" and parts[-1] in {
            "atif-trajectory.json",
            "openhands-trajectory.json",
            "gold.json",
            "model.patch",
            "collection-error.txt",
        }
    if parts[0] == "experiment":
        return parts[1] in {"task-map.json", "contextbench-subset.parquet"}
    if parts[0] == "harbor_parity" and len(parts) >= 4:
        return parts[3:] in (
            ["result.json"],
            ["agent", "trajectory.json"],
            ["agent", "openhands.trajectory.json"],
        )
    return False


def _download(relative: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        partial = Path(handle.name)
        with urllib.request.urlopen(f"{_BASE_URL}/{relative}", timeout=120) as response:
            while chunk := response.read(1 << 20):
                handle.write(chunk)
    partial.replace(destination)


def fetch_bundle(bundle_dir: Path) -> None:
    """Download the needed bundle files and verify each against the manifest."""
    manifest = bundle_dir / "checksums.sha256"
    if not manifest.is_file() or sha256_file(manifest) != MANIFEST_SHA256:
        _download("checksums.sha256", manifest)
    if sha256_file(manifest) != MANIFEST_SHA256:
        raise SystemExit(f"bundle manifest checksum mismatch: {manifest}")
    expected: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        relative = relative.removeprefix("./")
        if _needed(relative):
            expected[relative] = digest

    def fetch(relative: str) -> None:
        destination = bundle_dir / relative
        if not destination.is_file() or sha256_file(destination) != expected[relative]:
            _download(relative, destination)

    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        list(pool.map(fetch, sorted(expected)))
    mismatched = [
        relative
        for relative, digest in sorted(expected.items())
        if sha256_file(bundle_dir / relative) != digest
    ]
    if mismatched:
        raise SystemExit(f"bundle checksum mismatch: {', '.join(mismatched)}")


def _git(*arguments: str) -> None:
    subprocess.run(["git", *arguments], check=True, capture_output=True)


def fetch_repositories(repository_cache: Path, commits: set[tuple[str, str]]) -> None:
    """Fetch each `owner/repo` base commit into a shallow per-repository cache."""
    for repository, commit in sorted(commits):
        cache = repository_cache / f"github.com__{repository.replace('/', '__')}"
        if not (cache / ".git").exists():
            _git("init", "-q", str(cache))
        present = subprocess.run(
            ["git", "-C", str(cache), "cat-file", "-e", f"{commit}^{{commit}}"],
            check=False,
            capture_output=True,
        )
        if present.returncode != 0:
            _git(
                "-C",
                str(cache),
                "fetch",
                "-q",
                "--depth=1",
                f"https://github.com/{repository}.git",
                commit,
            )


def fetch_inputs(work_dir: Path) -> None:
    """Fetch the bundle files and every task repository into `work_dir`."""
    bundle = work_dir / "bundle"
    fetch_bundle(bundle)
    commits = {
        (str(task["repository"]), str(task["base_commit"]))
        for task_map in (
            bundle / "provenance" / RETAINED_CORPUS / "task-map.json",
            bundle / "experiment" / "task-map.json",
        )
        for task in json.loads(task_map.read_text(encoding="utf-8")).values()
    }
    fetch_repositories(work_dir / "repositories", commits)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else None
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "contextbench-calibration",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite the pinned summaries instead of comparing with them",
    )
    args = parser.parse_args()
    work_dir = args.work_dir.resolve()
    fetch_inputs(work_dir)

    bundle = work_dir / "bundle"
    repositories = work_dir / "repositories"
    worktrees = work_dir / "worktrees"
    mismatched = []
    for corpus, pinned in (
        (retained_corpus(bundle / "provenance" / RETAINED_CORPUS), SUMMARY_PATH),
        (parity_run_corpus(bundle), PARITY_RUNS_SUMMARY_PATH),
    ):
        summary = calibrate(corpus, repositories, worktrees)
        measured = work_dir / pinned.name
        write_json(measured, summary)
        if args.update:
            write_json(pinned, summary)
        elif json.loads(pinned.read_text(encoding="utf-8")) != summary:
            mismatched.append(f"{pinned.name} (measured: {measured})")
        totals = summary["totals"]
        print(
            f"{summary['corpus']['name']}: rule {totals['rule']} vs oracle "
            f"{totals['oracle']}; {totals['trajectories_with_identical_files']}/"
            f"{summary['corpus']['trajectories']} with identical files"
        )
    if mismatched:
        print("calibration differs from " + ", ".join(mismatched), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
