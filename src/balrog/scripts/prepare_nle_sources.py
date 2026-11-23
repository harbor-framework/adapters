"""Fetch pinned MiniHack/Boxoban sources and create verified runtime archives.

Usage from the adapter project:
    python scripts/prepare_nle_sources.py --output-dir /path/to/runtime-sources

NLE itself is installed from the pinned balrog-nle wheel in the runtime
Dockerfile. This script prepares MiniHack code and the two required map sets.
It never edits benchmark code, downloads models, or calls a model API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
SOURCES = (
    ("minihack_source", "https://github.com/balrog-ai/minihack.git",
     "3ecb6da4eadcac7a4dbc5f8e801ccf636e34d7ec", ()),
    ("minihack_boxoban", "https://github.com/google-deepmind/boxoban-levels.git",
     "78011d8c86ad423bfb2e1005012393b4c3c24409", ("hard", "medium/train", "LICENSE", "README.md")),
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(*args: str, capture: bool = False) -> str:
    result = subprocess.run(["git", *map(str, args)], check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, help="Optional existing checkout cache; defaults under output-dir")
    parser.add_argument("--force", action="store_true", help="Regenerate archives even when their hashes already match")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    cache = (args.cache_dir or output / ".nle-source-cache").resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((PROJECT / "src/balrog/fixtures/runtime_sources.json").read_text(encoding="utf-8"))
    expected = {Path(item["path"]).name: item for item in manifest["minihack"]}
    for name, url, commit, paths in SOURCES:
        archive = output / f"{name}.tar.gz"
        entry = expected[archive.name]
        if entry["commit"] != commit:
            raise RuntimeError(f"Source commit disagrees with runtime_sources.json: {name}")
        if not args.force and archive.exists() and sha256(archive) == entry["sha256"]:
            print(f"Verified existing {archive.name}: {entry['sha256']}")
            continue
        checkout = cache / name
        if not checkout.exists():
            git("clone", "--filter=blob:none", "--no-checkout", url, str(checkout))
        remote = git("-C", str(checkout), "config", "--get", "remote.origin.url", capture=True)
        if remote.rstrip("/") != url:
            raise RuntimeError(f"Unexpected origin for {checkout}: {remote}")
        available = subprocess.run(["git", "-C", str(checkout), "cat-file", "-e", f"{commit}^{{commit}}"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not available:
            git("-C", str(checkout), "fetch", "--depth=1", "origin", commit)
        # Git on Windows can convert archive contents under core.autocrlf=true.
        # Disable conversion so Linux shell scripts and .des files retain LF.
        temporary = archive.with_suffix(archive.suffix + ".partial")
        git("-C", str(checkout), "-c", "core.autocrlf=false", "archive", "--format=tar.gz",
            f"--output={temporary}", commit, *paths)
        actual = sha256(temporary)
        if actual != entry["sha256"]:
            temporary.unlink()
            raise RuntimeError(f"Archive hash mismatch for {name}: expected {entry['sha256']}, got {actual}; "
                               "do not update the manifest automatically")
        temporary.replace(archive)
        print(f"Prepared {archive.name}: {actual}")


if __name__ == "__main__":
    main()
