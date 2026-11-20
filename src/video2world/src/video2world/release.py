"""Pinned upstream checkout, manifest and cohort boundaries."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from . import DATA_REVISION, MANIFEST_SHA256, UPSTREAM_REVISION


def key(row: dict) -> str:
    return row["family"] + "/" + row["sample"]


def task_id(configuration_key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", configuration_key.lower()).strip("-")


def read_manifest(data: Path) -> list[dict]:
    path = data / "manifest.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != MANIFEST_SHA256:
        raise ValueError(f"{path}: expected data revision {DATA_REVISION}")
    return json.loads(path.read_text())["samples"]


def load_upstream(root: Path, data: Path) -> None:
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
        text=True,
    )
    if revision != UPSTREAM_REVISION or dirty:
        raise ValueError(
            f"upstream must be an unmodified checkout of {UPSTREAM_REVISION}"
        )
    os.environ["V2W_DATA"] = str(data.resolve())
    sys.path.insert(0, str(root.resolve()))


def load_selection(root: Path, data: Path, selection: Path) -> list[dict]:
    load_upstream(root, data)
    selected = json.loads(selection.read_text())
    if (
        selected["manifest_sha256"] != MANIFEST_SHA256
        or selected["upstream_revision"] != UPSTREAM_REVISION
    ):
        raise ValueError("selection provenance does not match this adapter")
    rows = selected["configurations"]
    original = {key(row): row for row in read_manifest(data)}
    if any(original.get(key(row)) != row for row in rows):
        raise ValueError("selection differs from the pinned manifest")
    return rows
