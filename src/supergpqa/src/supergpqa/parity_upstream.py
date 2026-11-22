"""Independently execute selected unmodified functions from the pinned upstream.

AST selection avoids importing unused Excel/pandas inference/report dependencies.
Function bodies and decorators are compiled unchanged from the verified checkout.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import timeout_decorator
import yaml

from supergpqa.adapter import ANSWER_HANDOFF, PACKAGE_DIR


def upstream_functions(path: Path, names: set[str], namespace: dict) -> dict:
    tree = ast.parse(path.read_text())
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if {node.name for node in nodes} != names:
        raise ValueError(f"Missing upstream functions in {path}")
    # Execute only named functions from a checksum-verified, revision-pinned checkout.
    exec(
        compile(
            ast.Module(body=list[ast.stmt](nodes), type_ignores=[]), str(path), "exec"
        ),
        namespace,
    )  # noqa: S102
    return namespace


def load_upstream(root: Path) -> tuple[dict[str, str], dict]:
    pins = json.loads((PACKAGE_DIR.parents[1] / "source_pins.json").read_text())
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != pins["upstream_commit"]:
        raise ValueError("Upstream checkout revision is not pinned")
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--exit-code",
            "HEAD",
            "--",
            "infer/data_loader.py",
        ],
        check=True,
        capture_output=True,
    )
    for name, expected in pins["files"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Changed pinned upstream source: {name}")
    # These adapters provide I/O only; upstream load_data supplies prompt rendering.
    namespace: dict[str, Any] = {
        "read_yaml": lambda mode: yaml.safe_load(
            (root / "config/prompt" / f"{mode}.yaml").read_text()
        ),
        "read_json_or_jsonl": lambda folder, split: [
            json.loads(line)
            for line in (root / folder / f"{split}.jsonl").read_text().splitlines()
        ],
    }
    upstream_functions(root / "infer/data_loader.py", {"load_data"}, namespace)
    prompts = {}
    for prompt, row in namespace["load_data"]("SuperGPQA-all", "zero-shot"):
        # Match the generated instruction template's final newline and Harbor's loading.
        prompts[row["uuid"]] = (
            (prompt + ANSWER_HANDOFF + "\n").replace("\r\n", "\n").replace("\r", "\n")
        )
    parser = upstream_functions(
        root / "eval/eval.py",
        {
            "safe_regex_search",
            "extract_option_labels",
            "extract_option_content",
        },
        {"re": re, "timeout_decorator": timeout_decorator},
    )
    return prompts, parser


def score_original(record: dict, response: str, parser: dict) -> int:
    predict = parser["extract_option_labels"](response, "ABCDEFGHIJ")
    if predict is None:
        content = parser["extract_option_content"](response, record["options"])
        predict = chr(record["options"].index(content) + 65) if content else None
    return int(bool(predict) and predict == record["answer_letter"])
