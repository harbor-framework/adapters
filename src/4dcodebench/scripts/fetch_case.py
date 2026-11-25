#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "huggingface_hub>=0.30",
#     "h5py==3.16.0",
#     "hdf5plugin>=4.4",
#     "numpy==2.3.1",
# ]
# ///
"""Download the reference data of a few 4DCodeBench cases, in the upstream layout.

    uv run scripts/fetch_case.py --repo <4DCodeBench checkout> --root <data home> synthetic/B_01 [...]

The upstream `scripts/download_data.py` fetches every case of a kind. This fetches
only the named ones, from the same Hugging Face datasets at the revisions this
adapter was written against, verifies each file's SHA-256 against the Hub, and
unpacks synthetic worlds with the upstream `unpack` (imported from the checkout,
not copied):

    <root>/cases/<kind>/<case>/reference.mp4
    <root>/data/synthetic/<case>/world/                 (worlds/<case>.h5, unpacked)
    <root>/data/real/<case>/annotation/dynamic_mask.npz
    <root>/data/<kind>/<case>/estimates/*               (Dataset-Model-Estimation)

`<root>/SHA256SUMS` then lists every file under cases/ and data/ that this script
wrote, for `sha256sum -c` after the data is copied elsewhere. No authentication is
needed; the three datasets are public. Files already in place are kept.

A real case whose video the authors do not redistribute cannot be fetched this way;
build it with the upstream `download_data.py --kind real` (its `prepare_videos.py`).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

SYNTHETIC = ("4DCodeBench/Dataset-Synthetic", "6b634b2ef9e63ffa6b78639c16b6859717423a59")
REAL = ("4DCodeBench/Dataset-Real-World", "2e6f267c94b9a61afd2c82852765758afe838f33")
ESTIMATES = ("4DCodeBench/Dataset-Model-Estimation", "671db39a7ca642005478a2d2cd913a3455e1a235")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def remote_files(api: HfApi, source: tuple[str, str], paths: list[str]) -> dict[str, tuple[int, str]]:
    """{path: (size, sha256)} for the files of `paths` that exist at the pinned revision."""
    repo, revision = source
    found = {}
    for info in api.get_paths_info(repo, paths, revision=revision, repo_type="dataset", expand=True):
        if getattr(info, "lfs", None) is None:
            raise SystemExit(f"{repo}/{info.path}: not an LFS file, cannot verify its SHA-256")
        found[info.path] = (info.size, info.lfs.sha256)
    return found


def list_dir(api: HfApi, source: tuple[str, str], folder: str) -> list[str]:
    repo, revision = source
    return sorted(entry.path for entry in api.list_repo_tree(repo, folder, revision=revision,
                                                             repo_type="dataset")
                  if not hasattr(entry, "tree_id"))


def fetch(source: tuple[str, str], path: str, expected: tuple[int, str], tmp: Path) -> Path:
    repo, revision = source
    local = Path(hf_hub_download(repo, path, revision=revision, repo_type="dataset", local_dir=tmp))
    size, digest = expected
    if local.stat().st_size != size or sha256(local) != digest:
        raise SystemExit(f"{repo}/{path}: size or SHA-256 differs from the Hub")
    return local


def place(local: Path, target: Path, written: list[Path]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(local, target)
    written.append(target)


def load_unpack(repo: Path):
    script = repo / "scripts" / "download_data.py"
    if not script.is_file():
        raise SystemExit(f"{repo} is not a 4DCodeBench checkout (no scripts/download_data.py)")
    spec = importlib.util.spec_from_file_location("_upstream_download_data", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.unpack


def fetch_case(api: HfApi, root: Path, kind: str, case: str, unpack, tmp: Path) -> list[Path]:
    written: list[Path] = []
    source = SYNTHETIC if kind == "synthetic" else REAL
    video = root / "cases" / kind / case / "reference.mp4"
    wanted = {f"videos/{case}.mp4": video}
    if kind == "real":
        wanted[f"annotations/{case}/dynamic_mask.npz"] = root / "data/real" / case / "annotation/dynamic_mask.npz"
    world = root / "data/synthetic" / case / "world"
    if kind == "synthetic" and not world.exists():
        wanted[f"worlds/{case}.h5"] = None
    info = remote_files(api, source, list(wanted))
    missing = sorted(set(wanted) - set(info))
    if missing:
        hint = " (a video not redistributed: use the upstream download_data.py)" if f"videos/{case}.mp4" in missing \
            and kind == "real" else ""
        raise SystemExit(f"{kind}/{case}: not in {source[0]}@{source[1][:12]}: {missing}{hint}")
    for path, target in wanted.items():
        if target is not None and target.exists():
            continue
        local = fetch(source, path, info[path], tmp)
        if target is None:                       # the packed world
            unpack(local, world)
            local.unlink()
            written.extend(sorted(p for p in world.rglob("*") if p.is_file()))
        else:
            place(local, target, written)

    estimates = list_dir(api, ESTIMATES, f"{kind}/{case}")
    if not estimates:
        raise SystemExit(f"{kind}/{case}: no estimates in {ESTIMATES[0]}@{ESTIMATES[1][:12]}")
    info = remote_files(api, ESTIMATES, estimates)
    for path in estimates:
        target = root / "data" / kind / case / "estimates" / path.rsplit("/", 1)[1]
        if not target.exists():
            place(fetch(ESTIMATES, path, info[path], tmp), target, written)
    return written


def update_sums(root: Path, written: list[Path]) -> Path:
    sums = root / "SHA256SUMS"
    entries = {}
    if sums.exists():
        for line in sums.read_text(encoding="utf-8").splitlines():
            digest, name = line.split("  ", 1)
            entries[name] = digest
    for path in written:
        entries[path.relative_to(root).as_posix()] = sha256(path)
    sums.write_text("".join(f"{entries[name]}  {name}\n" for name in sorted(entries)),
                    encoding="utf-8", newline="\n")
    return sums


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, required=True, help="4DCodeBench checkout (for its unpack)")
    parser.add_argument("--root", type=Path, required=True, help="data home: receives cases/ and data/")
    parser.add_argument("cases", nargs="+", help="<kind>/<case>, e.g. synthetic/B_01")
    args = parser.parse_args(argv)

    unpack = load_unpack(args.repo.resolve())
    root = args.root.resolve()
    api = HfApi()
    written: list[Path] = []
    for key in args.cases:
        kind, _, case = key.partition("/")
        if kind not in ("synthetic", "real") or not case:
            parser.error(f"expected <kind>/<case>, got {key!r}")
        with tempfile.TemporaryDirectory() as tmp:
            new = fetch_case(api, root, kind, case, unpack, Path(tmp))
        written.extend(new)
        print(f"{key}: {len(new)} files written")
    if written:
        print(f"checksums: {update_sums(root, written)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
