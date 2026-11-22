"""Load the scoring functions from the exact OpenAI release used for conversion."""

import ast
from hashlib import sha1
import re


SCORER_BLOB = "7e4023bebe8fd945d3513e64093c2c2affa749fd"


def load_reference(path):
    data = path.read_bytes()
    if sha1(f"blob {len(data)}\0".encode() + data).hexdigest() != SCORER_BLOB:
        raise ValueError("Expected the pinned OpenAI grade_school_math/dataset.py")
    tree = ast.parse(data)
    tree.body = [node for node in tree.body if is_scoring_definition(node)]
    namespace = {"re": re}
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace["extract_answer"], namespace["is_correct"]


def is_scoring_definition(node):
    if isinstance(node, ast.FunctionDef):
        return node.name in {"extract_answer", "is_correct"}
    if isinstance(node, ast.Assign):
        return node.targets[0].id in {"ANS_RE", "INVALID_ANS"}
    return False
