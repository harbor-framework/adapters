"""Generate native Harbor tasks from the pinned GSM8K train and test splits."""

from dataclasses import dataclass
from hashlib import sha1, sha256
from importlib.metadata import version
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import shlex
from urllib.request import urlopen

from harbor.models.dataset.manifest import DatasetInfo, DatasetManifest, DatasetTaskRef
from harbor.models.task.task import Task
from harbor.publisher.packager import Packager


HARBOR_VERSION = "0.27.0"
REVISION = "3101c7d5072418e28b9008a6636bde82a006892c"
# Git blob ID, file bytes and number of rows in the pinned upstream release.
SPLITS = {
    "train": ("7d97154b91aef28d01c3301741c81ce90039a4b1", 4166206, 7473),
    "test": ("e4c2ff4942b9a78bd74f04141224c11e28d12dc9", 749738, 1319),
}
DEFAULT_IMAGE = "quay.io/fedora/python-311@sha256:d12ae9699d4c0af68366e8589c43339db948df57837de06c3c1536b3ec852520"
TEMPLATES = Path(__file__).with_name("task-template")
GOLD_LINE = re.compile(r"#### (-?[0-9]+(?:\.[0-9]+)?)")
ANSWER_PATH = "/app/output/answer.txt"
WRAPPER = (f"\n\nWrite the final number on its own in `{ANSWER_PATH}`. "
           "Use standard decimal notation, with an optional minus sign and properly grouped "
           "thousands separators. Omit redundant leading zeros and decimal places. "
           "Keep any work or units outside that file.\n")


@dataclass(frozen=True)
class Example:
    row: int
    line_sha256: str
    question: str
    upstream_answer: str
    gold: str
    split: str = "test"

    @property
    def task_name(self):
        return f"gsm8k-{self.split}-{self.row:04d}"


def require_harbor():
    if version("harbor") != HARBOR_VERSION:
        raise ValueError(f"Harbor {HARBOR_VERSION} is required")


def check_source(data, split="test"):
    blob, size, _ = SPLITS[split]
    header = f"blob {len(data)}\0".encode("ascii")
    if len(data) != size or sha1(header + data).hexdigest() != blob:
        raise ValueError(f"Source must match the pinned OpenAI {split}.jsonl Git blob")


def download_source(split):
    url = f"https://raw.githubusercontent.com/openai/grade-school-math/{REVISION}/grade_school_math/data/{split}.jsonl"
    with urlopen(url, timeout=40) as response:
        data = response.read(SPLITS[split][1] + 1)
    check_source(data, split)
    return data


def parse_example(index, line, split="test"):
    record = json.loads(line)
    question, answer = record["question"], record["answer"]
    if not isinstance(question, str) or not question.strip() or "\x00" in question:
        raise ValueError(f"Invalid question at source row {index}")
    if not isinstance(answer, str) or answer.count("####") != 1:
        raise ValueError(f"Expected one answer marker at source row {index}")
    match = GOLD_LINE.fullmatch(answer.rstrip().splitlines()[-1].replace(",", ""))
    if match is None:
        raise ValueError(f"Invalid final answer at source row {index}")
    return Example(index, sha256(line).hexdigest(), question, answer, match[1], split)


def read_source(data, split="test"):
    check_source(data, split)
    lines = data.splitlines()
    if len(lines) != SPLITS[split][2]:
        raise ValueError(f"Unexpected GSM8K {split} row count")
    return [parse_example(index, line, split) for index, line in enumerate(lines)]


ADAPTER = "gsm8k-v0.2.0"

def select_examples(examples, task_ids=(), limit=None):
    known = {row.task_name for row in examples}
    selected = [task.removeprefix("gsm8k/") for task in task_ids]
    requested = set(selected)
    if len(requested) != len(selected):
        raise ValueError("Task IDs must be unique")
    if unknown := requested - known:
        raise ValueError(f"Unknown task IDs: {sorted(unknown)}")
    rows = [row for row in examples if not requested or row.task_name in requested]
    return rows if limit is None else rows[:limit]


def render_task(path, example, image):
    substitutions = {
        "task.toml": {"task_name": example.task_name, "revision": REVISION, "split": example.split, "row": example.row},
        "instruction.md": {"question": example.question},
        "environment/Dockerfile": {"image": image},
        "solution/solve.sh": {"gold": shlex.quote(example.gold)},
    }
    for template in sorted(TEMPLATES.rglob("*")):
        if not template.is_file():
            continue
        name = template.relative_to(TEMPLATES).as_posix()
        dest = path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        contents = template.read_bytes()
        for key, value in substitutions.get(name, {}).items():
            contents = contents.replace(f"{{{key}}}".encode(), str(value).encode())
        dest.write_bytes(contents)
        if name.endswith(".sh"):
            dest.chmod(0o755)
    (path / "tests/gold.txt").write_text(example.gold + "\n", encoding="utf-8")


def describe_task(path, example):
    task = Task(path)
    if task.instruction != example.question + WRAPPER:
        raise ValueError(f"Generated instruction differs for {example.task_name}")
    digest, _ = Packager.compute_content_hash(path)
    return {
        "task_name": example.task_name,
        "registry_name": task.config.task.name,
        "task_digest": f"sha256:{digest}",
        "harbor_checksum": task.checksum,
        "source_row": example.row,
        "source_line_sha256": example.line_sha256,
        "question_sha256": sha256(example.question.encode()).hexdigest(),
        "files": {file.relative_to(path).as_posix(): sha256(file.read_bytes()).hexdigest()
                  for file in sorted(path.rglob("*")) if file.is_file()},
    }


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_dataset(root, selection, tasks):
    dataset = DatasetInfo(
        name=f"gsm8k/gsm8k-{selection}",
        description=f"GSM8K {selection} tasks from OpenAI source revision {REVISION}.",
        authors=[{"name": "Karl Cobbe"}, {"name": "stein-wang0226"}],
        keywords=["gsm8k", "math", "agent-evaluation"],
    )
    refs = [DatasetTaskRef(name=task["registry_name"], digest=task["task_digest"]) for task in tasks]
    (root / "dataset.toml").write_text(DatasetManifest(dataset=dataset, tasks=refs).to_toml(), encoding="utf-8")


def generate(root, source_data, selection, examples, image):
    root.mkdir()
    tasks = []
    for example in examples:
        task_dir = root / example.task_name
        render_task(task_dir, example, image)
        tasks.append(describe_task(task_dir, example))
    split = examples[0].split
    write_dataset(root, selection, tasks)
    manifest = {
        "adapter": ADAPTER, "harbor_version": HARBOR_VERSION, "image": image,
        "selection": selection, "task_count": len(tasks), "tasks": tasks,
        "source": {"repository": "openai/grade-school-math", "revision": REVISION,
                   "split": split, "path": f"grade_school_math/data/{split}.jsonl",
                   "git_blob": SPLITS[split][0], "sha256": sha256(source_data).hexdigest()},
    }
    write_json(root / "manifest.json", manifest)
    return manifest


def check_replaceable(output):
    if output.is_symlink() or not output.is_dir():
        raise ValueError(f"Cannot replace {output}")
    if not any(output.iterdir()):
        return
    manifest_path = output / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Cannot replace a directory without an adapter manifest: {output}")
    manifest = json.loads(manifest_path.read_bytes())
    expected = {task["task_name"] for task in manifest["tasks"]} | {"dataset.toml", "manifest.json"}
    if manifest.get("adapter") != ADAPTER or expected != {path.name for path in output.iterdir()}:
        raise ValueError(f"Directory contains content outside the GSM8K build: {output}")


def replace_output(candidate, output, overwrite):
    if not (output.exists() or output.is_symlink()):
        candidate.rename(output)
        return
    if not overwrite:
        raise FileExistsError(f"Output already exists: {output}")
    check_replaceable(output)
    backup = candidate.parent / "previous"
    output.rename(backup)
    try:
        candidate.rename(output)
    except OSError:
        backup.rename(output)
        raise


def build(output, selection, source=None, task_ids=(), limit=None, overwrite=False, image=DEFAULT_IMAGE):
    require_harbor()
    if selection == "parity" and not task_ids:
        raise ValueError("Select a parity subset explicitly with --task-ids")
    if limit is not None and limit < 1:
        raise ValueError("Limit must be positive")
    if not re.fullmatch(r"[a-zA-Z0-9._:/-]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("The task image must be pinned by SHA-256")
    split = "test" if selection == "parity" else selection
    data = source.read_bytes() if source else download_source(split)
    examples = select_examples(read_source(data, split), task_ids, limit)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".gsm8k-build-", dir=output.parent) as directory:
        candidate = Path(directory) / "dataset"
        manifest = generate(candidate, data, selection, examples, image)
        replace_output(candidate, output, overwrite)
    return manifest
