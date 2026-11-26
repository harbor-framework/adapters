import inspect
import json
import os
import shutil
import sys
from importlib.machinery import ModuleSpec
from importlib.metadata import distribution
from importlib.util import module_from_spec
from pathlib import Path
from tempfile import TemporaryDirectory

import fsspec
import pyarrow.dataset as ds
from filelock import FileLock

SOURCE_ID = "django__django-15996"
TASK_ID = "swe-django-honest-15996"
BASE_COMMIT = "b30c0081d4d8a31ab7dc7f72a4c7099af606ef29"
DATA_REVISION = "fe1a73f1a8372e1ff447d2218e84ad33f20ad70e"
SOURCE = ("https://huggingface.co/datasets/schaeff/SWE-django-sidetasks/resolve/"
          f"{DATA_REVISION}/data/test-00000-of-00001.parquet")
IMAGE = ("swebench/sweb.eval.x86_64.django_1776_django-15996@"
         "sha256:a668a52a07bf8ca7b4f8626ec7295e7d4d224ae59a5c92e5a840d6da1f47561a")
COLUMNS = ["instance_id", "base_commit", "repo", "version", "problem_statement", "patch",
           "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS", "hints_text", "created_at",
           "environment_setup_commit"]
TEMPLATE = Path(__file__).with_name("task-template")


def prepare_swebench_imports() -> None:
    """On Windows, skip SWE-bench's unrelated POSIX image-builder package initializers."""
    if os.name != "nt" or "swebench" in sys.modules:
        return
    installed = distribution("swebench")
    if installed.version != "4.1.0":
        raise ValueError("Expected swebench==4.1.0")
    # Its top-level package eagerly imports the image builder, which requires Unix resource.
    # Load the installed constants, parsers, and test specifications normally below these roots.
    for name in ("swebench", "swebench.harness"):
        spec = ModuleSpec(name, loader=None, is_package=True)
        spec.submodule_search_locations = [str(installed.locate_file(name.replace(".", "/")))]
        module = module_from_spec(spec)
        sys.modules[name] = module
        if name == "swebench.harness":
            sys.modules["swebench"].harness = module


def load_issue() -> dict:
    with fsspec.open(SOURCE, "rb", block_size=1, cache_type="none") as source:
        fragment = ds.ParquetFileFormat().make_fragment(source)
        rows = fragment.to_table(
            columns=COLUMNS, filter=ds.field("instance_id") == SOURCE_ID, use_threads=False,
            fragment_scan_options=ds.ParquetFragmentScanOptions(pre_buffer=False),
        ).to_pylist()
    if len(rows) != 1:
        raise ValueError("Expected exactly one reviewed Django issue")
    record = rows[0]
    if (record["repo"], record["base_commit"], record["version"]) != ("django/django", BASE_COMMIT, "4.2"):
        raise ValueError("The pinned Django base revision or version has changed")
    for key in ("FAIL_TO_PASS", "PASS_TO_PASS"):
        while isinstance(record[key], str):
            record[key] = json.loads(record[key])
        if not record[key] or not all(isinstance(x, str) for x in record[key]):
            raise ValueError(f"Missing upstream {key} test identities")
    return record


def write_task(root: Path, issue: dict) -> None:
    prepare_swebench_imports()
    from control_arena.settings.swebench.dataset import DEFAULT_INPUT_PROMPT
    from control_arena.settings.swebench.prompts import SETTING_DESCRIPTION
    from control_arena.settings.swebench.scorers import get_eval_script
    from swebench.harness.constants import (
        APPLY_PATCH_FAIL, RESET_FAILED, TESTS_ERROR, TESTS_TIMEOUT, TestStatus,
    )
    from swebench.harness.log_parsers.python import parse_log_django

    shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for filename in ("environment/Dockerfile", "tests/Dockerfile"):
        path = root / filename
        path.write_text(path.read_text().replace("{image}", IMAGE), encoding="utf-8", newline="\n")
    prompt = DEFAULT_INPUT_PROMPT.format(issue_text=issue["problem_statement"])
    instruction = root / "instruction.md"
    text = instruction.read_text(encoding="utf-8").format(
        setting=SETTING_DESCRIPTION.rstrip(), prompt=prompt
    )
    instruction.write_text(text, encoding="utf-8", newline="\n")
    (root / "solution/gold.patch").write_text(issue["patch"], encoding="utf-8", newline="\n")
    script = get_eval_script(issue["test_patch"], issue["repo"], issue["version"], BASE_COMMIT)
    (root / "tests/native_eval.sh").write_text(script, encoding="utf-8", newline="\n")
    # The upstream Django parser ignores its test_spec argument. Package only this parser.
    parser = ("from __future__ import annotations\nimport re\nfrom enum import Enum\n\n" +
              inspect.getsource(TestStatus) + "\n" + inspect.getsource(parse_log_django))
    (root / "tests/django_parser.py").write_text(parser, encoding="utf-8", newline="\n")
    cases = {key: issue[key] for key in ["FAIL_TO_PASS", "PASS_TO_PASS"]}
    cases["error_markers"] = [APPLY_PATCH_FAIL, RESET_FAILED, TESTS_ERROR, TESTS_TIMEOUT,
                              "Failed to reset task environment"]
    (root / "tests/case.json").write_text(json.dumps(cases) + "\n", encoding="utf-8", newline="\n")
    for path in [*root.rglob("*.sh"), root / "environment/submit"]:
        path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        path.chmod(0o755)


def generate(output_dir: Path, task_ids: list[str] | None = None,
             limit: int | None = None, overwrite: bool = False) -> list[Path]:
    if limit is not None and limit < 0:
        raise ValueError("--limit must be nonnegative")
    if task_ids and {name.removeprefix("control-arena/") for name in task_ids} != {TASK_ID}:
        raise ValueError(f"Only {TASK_ID} is available")
    if limit == 0 or task_ids == []:
        return []
    output_dir.mkdir(exist_ok=True, parents=True)
    dest = output_dir / TASK_ID
    with FileLock(str(output_dir.parent / f".{output_dir.name}.django-honest.lock")):
        if dest.exists() and not overwrite:
            return [dest]
        with TemporaryDirectory(dir=output_dir.parent) as temp:
            staged, previous = Path(temp) / "task", Path(temp) / "previous"
            write_task(staged, load_issue())
            if dest.exists():
                dest.rename(previous)
            try:
                staged.rename(dest)
            except OSError:
                if previous.exists():
                    previous.rename(dest)
                raise
    return [dest]
