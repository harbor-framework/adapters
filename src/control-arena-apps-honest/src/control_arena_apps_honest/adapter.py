"""Generate honest APPS tasks from the reviewed projection of the pinned dataset."""

import ast
import json
import shutil
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory

import fsspec
import pyarrow.dataset as ds
from filelock import FileLock

DATASET = "RoganInglis/apps-control-arena"
REVISION = "29db28f76042952d56add8671f798280b200744d"
SHARD = "data/train-00000-of-00003.parquet"
SOURCE = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{SHARD}"
# Each reviewed row is in row group zero of the pinned shard.
PROBLEMS = {"0": "Accordion", "1": "Maximum digit sum", "17": "Stadium wave"}
COLUMNS = ["problem_id", "question", "solution_passes_tests", "is_nondeterministic",
           "inputs", "outputs", "solutions"]
TEMPLATE = Path(__file__).with_name("task-template")


def task_id(problem_id: str) -> str:
    return f"apps-honest-{int(problem_id):04d}"


def load_records(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    if set(ids) - PROBLEMS.keys():
        raise ValueError("Only reviewed APPS problem IDs can be loaded")
    # Keep reads seekable and unbuffered. Arrow can read only the selected column chunks.
    with fsspec.open(SOURCE, "rb", block_size=1, cache_type="none") as source:
        parquet = ds.ParquetFileFormat()
        fragment = parquet.make_fragment(source, row_groups=[0])
        scan_options = ds.ParquetFragmentScanOptions(pre_buffer=False)
        table = fragment.to_table(
            columns=COLUMNS, filter=ds.field("problem_id").isin(ids),
            use_threads=False, fragment_scan_options=scan_options,
        )
    records = {row["problem_id"]: row for row in table.to_pylist()}
    if set(records) != set(ids) or table.num_rows != len(ids):
        raise ValueError("Pinned APPS source returned missing or duplicate IDs")
    return [records[key] for key in ids]


def native_material() -> tuple[str, str]:
    """Copy only the honest setting description and the two pure comparison functions."""
    package = distribution("control-arena")
    if package.version != "20.1.1":
        raise ValueError("Expected control-arena==20.1.1")
    base = Path(package.locate_file("control_arena/settings/apps/task"))
    dataset = ast.parse((base / "dataset.py").read_text(encoding="utf-8"))
    (prompt,) = [
        ast.literal_eval(node.value) for node in dataset.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "SETTING_DESCRIPTION"
    ]
    source = (base / "scorers.py").read_text(encoding="utf-8")
    functions = {node.name: ast.get_source_segment(source, node)
                 for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)
                 and node.name in {"check_str_floats_equal", "check_solutions_equal"}}
    comparison = "\n\n".join(["import math", functions["check_str_floats_equal"],
                               functions["check_solutions_equal"]]) + "\n"
    return prompt, comparison


def write_task(staged: Path, record: dict, description: str, comparison: str) -> None:
    key = record["problem_id"]
    if not record["solution_passes_tests"] or record["is_nondeterministic"]:
        raise ValueError(f"Problem {key} failed upstream honest-mode eligibility checks")
    inputs, outputs = record["inputs"], record["outputs"]
    if not inputs or len(inputs) != len(outputs) or not all(
        isinstance(item, str) for items in (inputs, outputs) for item in items
    ):
        raise ValueError(f"Problem {key} lacks paired stdin/stdout tests")
    oracle = next((s["code"] for s in record["solutions"]
                   if s["compiles"] and s["passes_tests"] and s["code"]), None)
    if oracle is None:
        raise ValueError(f"Problem {key} lacks a validated honest reference solution")
    shutil.copytree(TEMPLATE, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    task = staged / "task.toml"
    task.write_text(task.read_text(encoding="utf-8").replace("{task_id}", task_id(key)),
                    encoding="utf-8", newline="\n")
    instruction = staged / "instruction.md"
    text = instruction.read_text(encoding="utf-8").format(
        setting=description.rstrip(), prompt=record["question"]
    )
    instruction.write_text(text, encoding="utf-8", newline="\n")
    (staged / "tests/comparison.py").write_text(comparison, encoding="utf-8", newline="\n")
    tests = {"problem_id": key, "revision": REVISION,
             "cases": list(zip(inputs[:10], outputs[:10], strict=True))}
    for name, data in [("tests/cases.json", tests), ("solution/submission.json", {"code": oracle})]:
        (staged / name).write_text(json.dumps(data, ensure_ascii=False) + "\n",
                                   encoding="utf-8", newline="\n")
    for path in [*staged.rglob("*.sh"), staged / "environment/submit"]:
        path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        path.chmod(0o755)


def generate(output_dir: Path, task_ids: list[str] | None = None,
             limit: int | None = None, overwrite: bool = False) -> list[Path]:
    if limit is not None and limit < 0:
        raise ValueError("--limit must be nonnegative")
    ids = list(PROBLEMS)
    if task_ids is not None:
        requested = {name.removeprefix("control-arena/") for name in task_ids}
        unknown = requested - {task_id(key) for key in ids}
        if unknown:
            raise ValueError(f"Unknown task IDs: {', '.join(sorted(unknown))}")
        ids = [key for key in ids if task_id(key) in requested]
    ids = ids[:limit]
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = [output_dir / task_id(key) for key in ids]
    # Serialize replacements on a common output directory without polluting the dataset.
    with FileLock(str(output_dir.parent / f".{output_dir.name}.apps-honest.lock")):
        pending = []
        for key, target in zip(ids, targets, strict=True):
            if target.exists() or target.is_symlink() or target.is_junction():
                marker = target / "tests/cases.json"
                if not marker.is_file() or marker.resolve() != output_dir.resolve() / target.name / "tests/cases.json":
                    raise ValueError(f"Destination belongs to another task: {target}")
                case = json.loads(marker.read_bytes())
                if not isinstance(case, dict) or (case.get("problem_id"), case.get("revision")) != (key, REVISION):
                    raise ValueError(f"Destination belongs to another task: {target}")
                if not overwrite:
                    continue
            pending.append(key)
        if not pending:
            return targets
        records = load_records(pending)
        description, comparison = native_material()
        for record in records:
            dest = output_dir / task_id(record["problem_id"])
            with TemporaryDirectory(dir=output_dir.parent) as temp:
                staged, previous = Path(temp) / "task", Path(temp) / "previous"
                write_task(staged, record, description, comparison)
                if dest.exists():
                    dest.rename(previous)
                try:
                    staged.rename(dest)
                except OSError:
                    if previous.exists():
                        previous.rename(dest)
                    raise
    return targets
