"""Project one ordinary Infra training-unit-test objective into an offline task."""

import ast
import hashlib
import json
import os
import shutil
import tomllib
from dataclasses import dataclass
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from urllib.request import urlopen

from filelock import FileLock

BASE = "85bddf5498adee812e10f376e9e675f579494ba4"
TRAIN_BLOB = "5b046c04f5f3b914c7528dcb3891c013abd3a4eb"
TEST_BLOB = "313752e2e97ba48fdd314e62684aba7a9960eb1d"
NATIVE_PATH = "/workspace/training-infra/training/tests/test_train.py"
TEMPLATE = Path(__file__).with_name("task-template")
SLUG = "infra-honest-add-unit-tests"


def verify_blob(content: bytes, expected: str) -> bytes:
    digest = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
    if digest != expected:
        raise ValueError("File differs from the pinned Git blob")
    return content


def read_training(source_dir: Path | None) -> bytes:
    if source_dir is None:
        url = f"https://raw.githubusercontent.com/UKGovernmentBEIS/ca-k8s-infra/{BASE}/training/train.py"
        with urlopen(url, timeout=60) as response:
            content = response.read()
    else:
        content = (source_dir / "train.py").read_bytes()
    return verify_blob(content, TRAIN_BLOB)


def native_material() -> tuple[str, str, bytes]:
    release = distribution("control-arena")
    if release.version != "20.1.1":
        raise ValueError("Expected control-arena==20.1.1")
    folder = Path(release.locate_file("control_arena/settings/infra/main_tasks/_add_unit_tests"))
    module = (folder / "task.py").read_text(encoding="utf-8")
    nodes = ast.parse(module).body
    expression, = [node.value for node in nodes if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "MAIN_TASK_INSTRUCTIONS" for t in node.targets)]
    # The released f-string has a single named substitution for the test path.
    substitutions = {"TRAIN_UNIT_TESTS_FILE_LOCATION": NATIVE_PATH}
    prompt = "".join(part.value if isinstance(part, ast.Constant) else substitutions[part.value.id]
                     for part in expression.values)
    bodies = {node.name: ast.get_source_segment(module, node) for node in nodes
              if isinstance(node, ast.AsyncFunctionDef) and node.name in {"score_add_unit_tests", "_test_with_bug"}}
    scorer = ("from __future__ import annotations\nimport logging\nfrom pathlib import Path\n"
              "from inspect_ai.scorer import CORRECT, INCORRECT, Score\n"
              "logger = logging.getLogger(__name__)\nCODE_PATH_SANDBOX = Path('/workspace/training-infra')\n"
              f"TRAIN_UNIT_TESTS_FILE_LOCATION = {NATIVE_PATH!r}\n\n"
              + bodies["score_add_unit_tests"] + "\n\n" + bodies["_test_with_bug"] + "\n")
    patch = (folder / "QA/solution.patch").read_text(encoding="utf-8").splitlines()
    content = patch[patch.index("+++ b/training/tests/test_train.py") + 2:]
    if not all(line.startswith("+") for line in content):
        raise ValueError("Unexpected upstream reference patch format")
    reference = ("\n".join(line[1:] for line in content) + "\n").encode()
    return prompt, scorer, verify_blob(reference, TEST_BLOB)


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def check_existing(path: Path, case: dict, overwrite: bool) -> None:
    if path.is_symlink() or path.is_junction() or not path.is_dir():
        raise ValueError(f"Existing path is not an Infra task directory: {path}")
    expected = {p.relative_to(TEMPLATE): p.is_dir() for p in TEMPLATE.rglob("*")
                if "__pycache__" not in p.parts and p.suffix != ".pyc"}
    expected.update({Path("environment/training"): True, Path("environment/training/tests"): True})
    expected.update({Path(name): False for name in (
        "LICENSE-ControlArena",
        "environment/training/__init__.py", "environment/training/train.py",
        "environment/training/tests/test_train.py", "tests/train.py", "tests/native_score.py",
        "tests/case.json", "solution/reference.py",
    )})
    actual = set()
    for entry in path.rglob("*"):
        relative = entry.relative_to(path)
        if entry.is_symlink() or entry.is_junction() or expected.get(relative) != entry.is_dir():
            raise ValueError(f"Preserving unexpected existing path: {entry}")
        actual.add(relative)
    try:
        name = tomllib.loads((path / "task.toml").read_text("utf-8"))["task"]["name"]
        marker = json.loads((path / "tests/case.json").read_bytes())
    except (KeyError, TypeError, OSError, ValueError) as exc:
        raise ValueError(f"Cannot verify existing task identity: {path}") from exc
    if name != f"control-arena/{SLUG}" or marker != case:
        raise ValueError(f"Destination belongs to another task: {path}")
    if actual != expected.keys() and not overwrite:
        raise ValueError(f"Incomplete generated task requires --overwrite: {path}")


@dataclass
class ControlArenaInfraUnitTestsHonestAdapter:
    output_dir: Path
    source_dir: Path | None = None
    task_ids: list[str] | None = None
    limit: int | None = None
    overwrite: bool = False

    def run(self) -> list[Path]:
        return generate(self.output_dir, self.source_dir, self.task_ids, self.limit, self.overwrite)


def generate(output_dir: Path, source_dir: Path | None = None, task_ids: list[str] | None = None,
             limit: int | None = None, overwrite: bool = False) -> list[Path]:
    if task_ids is not None and set(task_ids) - {"add_unit_tests", SLUG, "control-arena/" + SLUG}:
        raise ValueError("Only the add_unit_tests main objective is supported")
    if limit is not None and limit < 0:
        raise ValueError("--limit must be nonnegative")
    if limit == 0 or task_ids == []:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / SLUG
    case = {"setting": "infra", "objective": "add_unit_tests", "mode": "honest",
            "control_arena": "20.1.1", "commit": BASE, "train_blob": TRAIN_BLOB}
    key = hashlib.sha256(os.fsencode(output_dir.resolve())).hexdigest()
    with FileLock(Path(gettempdir()) / f"harbor-infra-unit-tests-{key}.lock"):
        if target.exists() or target.is_symlink() or target.is_junction():
            check_existing(target, case, overwrite)
            if not overwrite:
                return [target]
        training = read_training(source_dir)
        prompt, scorer, reference = native_material()
        with TemporaryDirectory(dir=output_dir, prefix=".infra-unit-") as temp:
            staged = Path(temp) / "new"
            shutil.copytree(TEMPLATE, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            release = distribution("control-arena")
            license_path, = (p for p in release.files if str(p).endswith(".dist-info/licenses/LICENSE"))
            shutil.copyfile(release.locate_file(license_path), staged / "LICENSE-ControlArena")
            train = staged / "environment/training"
            (train / "tests").mkdir(parents=True)
            (train / "__init__.py").touch()
            (train / "train.py").write_bytes(training)
            write(train / "tests/test_train.py", "# Write your unit tests here.\n")
            (staged / "tests/train.py").write_bytes(training)
            write(staged / "tests/native_score.py", scorer)
            write(staged / "tests/case.json", json.dumps(case) + "\n")
            (staged / "solution/reference.py").write_bytes(reference)
            instruction = staged / "instruction.md"
            write(instruction, instruction.read_text("utf-8").replace("{prompt}", prompt.rstrip()))
            for script in staged.rglob("*.sh"):
                write(script, script.read_text(encoding="utf-8"))
                script.chmod(0o755)
            previous = Path(temp) / "previous"
            if target.exists():
                target.rename(previous)
            try:
                staged.rename(target)
            except OSError:
                if previous.exists():
                    previous.rename(target)
                raise
        return [target]
