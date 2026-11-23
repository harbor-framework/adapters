"""Materialize pinned public tensor inputs, rejecting truncated or changed bytes."""

import hashlib
import json
import shutil
import urllib.request
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare(root: Path, manifest: dict, cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    for relative, spec in manifest["blobs"].items():
        target = root / relative
        cached = cache / spec["sha256"]
        if not cached.exists():
            url = (
                "https://huggingface.co/datasets/flashinfer-ai/flashinfer-trace/resolve/"
                + manifest["dataset_revision"]
                + "/"
                + relative
            )
            with (
                urllib.request.urlopen(url, timeout=120) as stream,
                cached.open("wb") as out,
            ):
                shutil.copyfileobj(stream, out)
        if cached.stat().st_size != spec["size"] or digest(cached) != spec["sha256"]:
            raise ValueError(f"Tensor checksum mismatch: {cached}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, target)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("manifest", type=Path)
    p.add_argument("cache", type=Path)
    a = p.parse_args()
    prepare(a.root, json.loads(a.manifest.read_text()), a.cache)


def check_gpu(target):
    """Do not collect timing results under a different prompt/hardware target."""
    import torch

    if torch.cuda.device_count() != 1:
        raise RuntimeError("Exactly one visible CUDA GPU is required")
    actual = torch.cuda.get_device_name(0)
    if target.lower().replace(" ", "") not in actual.lower().replace(" ", ""):
        raise RuntimeError(f"Requested GPU {target!r}, found {actual!r}")
