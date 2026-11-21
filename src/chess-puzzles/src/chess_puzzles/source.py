"""Fetch an immutable upstream snapshot; never execute unverified cached files."""

import ast
import hashlib
import importlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

PINS = json.loads(Path(__file__).with_name("source_pins.json").read_text())


def prepare_source(source_dir=None):
    root = Path(
        source_dir
        or os.environ.get(
            "CHESS_PUZZLES_SOURCE_DIR", ".cache/chess-puzzles/" + PINS["commit"]
        )
    ).resolve()
    for relative, digest in PINS["files"].items():
        path = root / relative
        if not path.exists():
            if source_dir or os.environ.get("CHESS_PUZZLES_SOURCE_DIR"):
                raise FileNotFoundError(path)
            url = f"https://raw.githubusercontent.com/{PINS['repo']}/{PINS['commit']}/{relative}"
            data = urllib.request.urlopen(url, timeout=60).read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"Download checksum mismatch: {relative}")
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                stream.write(data)
                temporary = Path(stream.name)
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Source checksum mismatch: {relative}")
    return root


def upstream(source_dir=None):
    root = prepare_source(source_dir)
    # A single pinned bench package per process; reject conflicting installed packages.
    existing = sys.modules.get("bench")
    if existing and Path(existing.__file__).resolve() != root / "bench/__init__.py":
        raise RuntimeError(
            "Another bench package is already imported; use a separate process"
        )
    sys.path.insert(0, str(root)) if str(root) not in sys.path else None
    return importlib.import_module("bench.task.chess_puzzles")


def question_template(source_dir=None):
    """Read the pinned literal without importing Inspect or executing upstream code."""
    path = prepare_source(source_dir) / "bench/task/chess_puzzles/__init__.py"
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "QUESTION_TEMPLATE"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, str) or "{prompt}" not in value:
                raise ValueError("Invalid upstream QUESTION_TEMPLATE")
            return value
    raise ValueError("Upstream QUESTION_TEMPLATE not found")
