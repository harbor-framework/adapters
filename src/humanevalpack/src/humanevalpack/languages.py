"""Per-language program assembly for HumanEvalPack (HumanEvalFix setting).

The upstream evaluator (bigcode-evaluation-harness ``humanevalpack.py`` plus the
``Muennighoff/code_eval_octopack`` metric) executes ``candidate + "\\n" + test``
after some language-specific pre-processing (import helpers for Python/C++,
import detection for Go, ``fn main(){}`` for Rust). Here we apply that
pre-processing once, at generation time, so the file the agent edits is already
a complete, runnable program. The verifier then only has to swap in a pristine
copy of the upstream ``test`` block and run the same command as upstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# https://github.com/bigcode-project/bigcode-evaluation-harness/blob/main/bigcode_eval/tasks/humanevalpack.py
PYTHON_IMPORT_HELPER = [
    "import math",
    "import re",
    "import sys",
    "import copy",
    "import datetime",
    "import itertools",
    "import collections",
    "import heapq",
    "import statistics",
    "import functools",
    "import hashlib",
    "import numpy",
    "import numpy as np",
    "import string",
    "from typing import *",
    "from collections import *",
]

GO_IMPORT_HELPER = [
    "math",
    "strings",
    "fmt",
    "strconv",
    "time",
    "bytes",
    "regexp",
    "sort",
    "math/rand",
    "crypto/md5",
]

# Upstream lists "using namespace std;" first; it is moved after the includes
# here so the file is valid on its own (the namespace only exists once a
# standard header has been included).
CPP_INCLUDE_HELPER = [
    "#include<stdlib.h>",
    "#include<algorithm>",
    "#include<cmath>",
    "#include<math.h>",
    "#include<numeric>",
    "#include<stdio.h>",
    "#include<vector>",
    "#include<set>",
    "#include<map>",
    "#include<queue>",
    "#include<stack>",
    "#include<list>",
    "#include<deque>",
    "#include<boost/any.hpp>",
    "#include<string>",
    "#include<climits>",
    "#include<cstring>",
    "#include<iostream>",
    "#include<sstream>",
    "#include<fstream>",
]


@dataclass(frozen=True)
class LanguageSpec:
    key: str  # task-name prefix and template directory name
    hf_config: str  # bigcode/humanevalpack config name
    display: str
    file_path: str  # file the agent edits (absolute, inside the container)
    run_command: str  # shown to the agent; mirrors the upstream command


LANGUAGES: dict[str, LanguageSpec] = {
    "python": LanguageSpec(
        "python", "python", "Python", "/workspace/solution.py",
        "python3 /workspace/solution.py",
    ),
    "js": LanguageSpec(
        "js", "js", "JavaScript", "/workspace/solution.js",
        "node /workspace/solution.js",
    ),
    "java": LanguageSpec(
        "java", "java", "Java", "/workspace/Main.java",
        "cd /workspace && javac Main.java && java -cp . Main",
    ),
    "go": LanguageSpec(
        "go", "go", "Go", "/workspace/main_test.go",
        "cd /workspace && go test main_test.go",
    ),
    "cpp": LanguageSpec(
        "cpp", "cpp", "C++", "/workspace/solution.cpp",
        "cd /workspace && g++ -std=c++11 solution.cpp -lcrypto -lssl && ./a.out",
    ),
    "rust": LanguageSpec(
        "rust", "rust", "Rust", "/workspace/src/main.rs",
        "cd /workspace && cargo test",
    ),
}

DEFAULT_LANGUAGES = ["js", "java", "go", "cpp", "rust"]

# task_id prefixes used in the HF dataset (e.g. "JavaScript/0", "CPP/0")
HF_PREFIX_TO_KEY = {
    "Python": "python",
    "JavaScript": "js",
    "Java": "java",
    "Go": "go",
    "CPP": "cpp",
    "Rust": "rust",
}


def _go_imports(code: str, test_setup: str) -> list[str]:
    """Return the import list for a Go program, mirroring upstream detection.

    Upstream keeps the imports in ``test_setup`` and adds any helper package
    whose identifier is used on a non-comment line. Unlike upstream (which adds
    the bare last path component, e.g. ``"rand"``), the full import path is
    used so that ``math/rand`` and ``crypto/md5`` resolve.
    """
    imports: list[str] = re.findall(r'"([^"]+)"', test_setup)
    body_lines = [ln for ln in code.split("\n") if not ln.strip().startswith("//")]
    for pkg in GO_IMPORT_HELPER:
        if pkg in imports:
            continue
        ident = pkg.split("/")[-1]
        pattern = re.compile(r"(?<![\w.])" + re.escape(ident) + r"\.")
        if any(pattern.search(ln) for ln in body_lines):
            imports.append(pkg)
    return imports


def _strip_go_imports_and_comments(prompt: str) -> str:
    """Drop the import block and ``//`` comment lines from a Go ``prompt``."""
    text = re.sub(r"^import\s*\((?:[^)]*)\)\s*\n", "", prompt, flags=re.M)
    text = re.sub(r'^import\s+"[^"]+"\s*\n', "", text, flags=re.M)
    lines = [ln for ln in text.split("\n") if not ln.strip().startswith("//")]
    return "\n".join(lines).lstrip("\n")


def fixed_declaration(lang: str, row: dict) -> tuple[str, str | None]:
    """Return ``(declaration, reason)``, repairing known upstream data defects.

    ``reason`` is ``None`` when the upstream ``declaration`` is used unchanged.
    The HumanEvalFix prompt is built from ``declaration``, which for five
    problems is not a valid prefix of either solution (so even the canonical
    solution cannot compile upstream):

    * Go/10, Go/32, Go/38, Go/50: ``declaration`` omits a helper function that
      the solution calls (it only exists in ``prompt``). We use ``prompt``
      without its import block and without ``//`` comments (the docstrings),
      which keeps the HumanEvalFix "no docstring" setting.
    * CPP/38: ``declaration`` already contains the first lines of the
      ``decode_cyclic`` body, which the solutions repeat. We cut it right
      after the ``decode_cyclic`` signature.
    """
    declaration: str = row["declaration"]
    entry: str = row["entry_point"]
    if lang == "go":
        prompt: str = row["prompt"]
        prompt_funcs = set(re.findall(r"^func (\w+)", prompt, re.M))
        decl_funcs = set(re.findall(r"^func (\w+)", declaration, re.M))
        missing = sorted(prompt_funcs - decl_funcs)
        if missing:
            return (
                "\n" + _strip_go_imports_and_comments(prompt),
                f"declaration is missing helper(s) {', '.join(missing)}; "
                "taken from prompt without comments",
            )
    if lang == "cpp":
        lines = declaration.rstrip("\n").split("\n")
        sig = [i for i, ln in enumerate(lines) if re.search(rf"\b{re.escape(entry)}\s*\(", ln)]
        if sig and sig[-1] != len(lines) - 1:
            return (
                "\n".join(lines[: sig[-1] + 1]) + "\n",
                f"declaration contains part of the {entry} body; "
                "truncated after the signature",
            )
    return declaration, None


def build_program(lang: str, row: dict, body: str) -> str:
    """Assemble the runnable file: prefix + declaration + ``body`` + "\\n" + test.

    ``body`` is either ``buggy_solution`` (what the agent starts from) or
    ``canonical_solution`` (oracle).
    """
    declaration, _ = fixed_declaration(lang, row)
    test: str = row["test"]
    code = declaration + body

    if lang == "python":
        prefix = "\n".join(PYTHON_IMPORT_HELPER) + "\n"
        return prefix + code + "\n" + test
    if lang == "cpp":
        prefix = "\n".join(CPP_INCLUDE_HELPER) + "\nusing namespace std;\n"
        return prefix + code + "\n" + test
    if lang == "go":
        imports = _go_imports(code + "\n" + test, row["test_setup"])
        header = "package main\n\nimport (\n"
        header += "".join(f'    "{p}"\n' for p in imports)
        header += ")\n"
        return header + code + "\n" + test
    if lang == "rust":
        return "fn main(){}\n" + code + "\n" + test
    # js, java: upstream runs candidate + "\n" + test without extra helpers
    return code + "\n" + test
