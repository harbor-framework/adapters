"""Repositories and trajectories shared by the scoring and verifier tests."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

# One definition in each file type ContextBench's LANG_MAP parses with
# tree-sitter, keyed by repository path.
LANGUAGE_SAMPLES = {
    "sample.py": "def sample():\n    return 1\n",
    "sample.js": "function sample() {}\n",
    "sample.jsx": "function sample() {}\n",
    "sample.ts": "function sample(): void {}\n",
    "sample.tsx": "function sample(): void {}\n",
    "sample.java": "class Sample {}\n",
    "sample.go": "package sample\n\nfunc Sample() {}\n",
    "sample.rs": "fn sample() {}\n",
    "sample.c": "int sample(void) { return 0; }\n",
    "sample.h": "int sample(void) { return 0; }\n",
    "sample.cpp": "int sample() { return 0; }\n",
    "sample.cc": "int sample() { return 0; }\n",
    "sample.hpp": "int sample() { return 0; }\n",
    "sample.cs": "class Sample {}\n",
    "sample.php": "<?php\nfunction sample() {}\n",
    "sample.rb": "def sample\nend\n",
    "sample.swift": "func sample() {}\n",
    "sample.kt": "fun sample() {}\n",
    "sample.scala": "class Sample\n",
}


def synthetic_digest(reference: str) -> str:
    """The stand-in digest the tests give an image that is not pinned."""
    return f"sha256:{hashlib.sha256(reference.encode()).hexdigest()}"


def git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def commit_files(root: Path, files: dict[str, str]) -> str:
    """Create a Git repository holding ``files`` and return its commit."""
    root.mkdir(parents=True)
    git(root, "init", "--quiet")
    git(root, "config", "user.name", "ContextBench Test")
    git(root, "config", "user.email", "contextbench@example.invalid")
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "fixture")
    return git(root, "rev-parse", "HEAD").strip()


def whole_file_gold(files: dict[str, str]) -> list[dict[str, Any]]:
    """Gold annotations that cover each file in full."""
    return [
        {"file": path, "start_line": 1, "end_line": len(text.splitlines())}
        for path, text in files.items()
    ]


def whole_file_reads(files: dict[str, str]) -> list[dict[str, Any]]:
    """ATIF steps that read each file in full through a structured Read tool."""
    return [
        {
            "tool_calls": [
                {
                    "tool_call_id": f"read-{index}",
                    "function_name": "Read",
                    "arguments": {
                        "file_path": f"/workspace/{path}",
                        "offset": 1,
                        "limit": len(text.splitlines()),
                    },
                }
            ],
            "observation": {
                "results": [
                    {
                        "source_call_id": f"read-{index}",
                        "content": "\n".join(text.splitlines()),
                    }
                ]
            },
        }
        for index, (path, text) in enumerate(files.items(), start=1)
    ]
