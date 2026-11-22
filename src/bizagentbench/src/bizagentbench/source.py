"""Only a clean, exact upstream Git snapshot can become a runtime image."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

UPSTREAM_URL = "https://github.com/ant-intl/BizAgentBench.git"
UPSTREAM_COMMIT = "670ec25cd934ae8c18e18f5c8f91fdfa0bb571d4"


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def validate_source(root: Path) -> None:
    if git(root, "rev-parse", "HEAD") != UPSTREAM_COMMIT:
        raise ValueError(f"Expected upstream commit {UPSTREAM_COMMIT}")
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Upstream checkout must be clean (including untracked files)")


def archive_source(root: Path, destination: Path) -> str:
    validate_source(root)
    subprocess.run(["git", "-C", str(root), "archive", "--format=tar", "-o",
                    str(destination.resolve()), UPSTREAM_COMMIT], check=True)
    return hashlib.sha256(destination.read_bytes()).hexdigest()
