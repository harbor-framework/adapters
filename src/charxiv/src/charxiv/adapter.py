"""CharXiv -> Harbor adapter.

Generates one Harbor task per CharXiv validation question:

* ``charxiv-descriptive-<figure_id>-<subq_idx>`` (4 per chart, 4000 total)
* ``charxiv-reasoning-<figure_id>`` (1 per chart, 1000 total)

Question text is built exactly as in the official response-generation code
(``descriptive_utils.build_descriptive_quries`` /
``reasoning_utils.build_reasoning_queries``) using the vendored upstream
``constants.py``. Grading reuses the official GPT-4o judge prompts (see
``task-template/tests/judge.py``).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import upstream_constants as C

ADAPTER_NAME = "charxiv"
TASK_ORG = "princeton-nlp"
SPLIT = "val"
MODES = ("descriptive", "reasoning")

# Source pins (see README "Notes & Caveats").
GITHUB_REPO = "princeton-nlp/CharXiv"
GITHUB_COMMIT = "7ebe88f78dee387691551f071abcb2b9e1a8025b"
HF_DATASET = "princeton-nlp/CharXiv"
HF_REVISION = "f441eb632fc62f6f777830a0f47619e6e86459b0"
IMAGES_ZIP_SHA256 = "c4b151cef2aba35523764dd1091d719d64acf81a16904d72f31da2723efbd855"
DATA_FILES = ("descriptive_val.json", "reasoning_val.json", "image_metadata_val.json")

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "harbor-charxiv"

IMAGE_DIR_IN_CONTAINER = "/app/images"
ANSWER_PATH = "/app/answer.txt"

AUTHORS = [
    "Zirui Wang",
    "Mengzhou Xia",
    "Luxi He",
    "Howard Chen",
    "Yitao Liu",
    "Richard Zhu",
    "Kaiqu Liang",
    "Xindi Wu",
    "Haotian Liu",
    "Sadhika Malladi",
    "Alexis Chevalier",
    "Sanjeev Arora",
    "Danqi Chen",
]

TEMPLATE_DIR = Path(__file__).parent / "task-template"
UPSTREAM_CONSTANTS_FILE = Path(__file__).parent / "upstream_constants.py"


# ---------------------------------------------------------------------------
# Upstream query construction (mirrors princeton-nlp/CharXiv src/*_utils.py)
# ---------------------------------------------------------------------------


def descriptive_query_helper(qid: int, subplot_loc: Any) -> str:
    """Verbatim port of ``descriptive_utils.descriptive_query_helper``."""
    if qid in [18, 19]:
        return C.DESCRIPTIVE_RESP_INST[qid]
    if isinstance(subplot_loc, list):
        if subplot_loc[0] == 0:
            prefix = "For the current plot, "
        else:
            prefix = f"For the subplot at row {subplot_loc[0]} and column {subplot_loc[1]}, "
    elif isinstance(subplot_loc, str):
        prefix = f"For {subplot_loc}, "
    else:
        raise ValueError(f"Invalid subplot_loc: {subplot_loc}")
    return C.DESCRIPTIVE_RESP_INST[qid].format(prefix)


def get_number_instruction(answer: str) -> str:
    """Verbatim port of ``reasoning_utils.get_number_instruction``."""
    base = answer.split(".")
    whole, decimal = base[0], None if len(base) == 1 else base[1]
    if whole is not None and decimal is None:
        inst = "* Your final answer must be an exact integer."
    elif whole is not None and decimal is not None:
        num_decimal = len(decimal)
        inst = f"* Your final answer must be a number with {num_decimal} decimal places."
    else:
        raise ValueError(f"Invalid answer: {answer}")
    return inst


def reasoning_question(d: dict[str, Any]) -> str:
    """Question construction from ``reasoning_utils.build_reasoning_queries``."""
    inst_category = d["inst_category"]
    if inst_category in [1, 2, 3]:
        return C.REASONING_RESP_INST[inst_category].format(d["query"])
    if inst_category == 4:
        return C.REASONING_RESP_INST[inst_category].format(
            d["query"], get_number_instruction(d["answer"])
        )
    raise ValueError(f"Invalid instruction category: {inst_category}")


# ---------------------------------------------------------------------------
# Task model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CharXivTask:
    mode: str  # "descriptive" | "reasoning"
    figure_id: int
    question: str  # full upstream question (with instructions) shown to the model
    answer: str  # ground truth
    subq_idx: int | None = None  # descriptive only
    qid: int | None = None  # descriptive template id
    inst_category: int | None = None  # reasoning answer type
    raw_question: str | None = None  # reasoning query without instructions (judge input)
    qa_source: int | None = None
    num_subplots: int | None = None
    image_meta: dict[str, Any] | None = None

    @property
    def task_id(self) -> str:
        if self.mode == "descriptive":
            raw = f"{ADAPTER_NAME}-descriptive-{self.figure_id}-{self.subq_idx}"
        else:
            raw = f"{ADAPTER_NAME}-reasoning-{self.figure_id}"
        return sanitize(raw)

    @property
    def task_name(self) -> str:
        return f"{TASK_ORG}/{self.task_id}"

    @property
    def image_filename(self) -> str:
        return f"{self.figure_id}.jpg"

    def grading_config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "mode": self.mode,
            "figure_id": self.figure_id,
            "ground_truth": self.answer,
        }
        if self.mode == "descriptive":
            cfg.update({"qid": self.qid, "subq_idx": self.subq_idx})
        else:
            cfg.update(
                {"inst_category": self.inst_category, "raw_question": self.raw_question}
            )
        return cfg


def sanitize(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return value.strip("-")


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "harbor-charxiv-adapter"})
    with urllib.request.urlopen(req, timeout=600) as resp, tmp.open("wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.replace(dest)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class CharXivSource:
    """Pinned CharXiv validation data (QA json from GitHub, images from HF)."""

    def __init__(self, source_dir: Path | None = None, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.source_dir = Path(source_dir) if source_dir else None
        self.cache_dir = Path(cache_dir)

    def data_dir(self) -> Path:
        if self.source_dir is not None:
            return self.source_dir / "data"
        d = self.cache_dir / GITHUB_COMMIT / "data"
        for name in DATA_FILES:
            if not (d / name).exists():
                url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_COMMIT}/data/{name}"
                _download(url, d / name)
        return d

    def load_json(self, name: str) -> dict[str, Any]:
        return json.loads((self.data_dir() / name).read_text(encoding="utf-8"))

    def images_zip(self) -> Path:
        z = self.cache_dir / HF_REVISION / "images.zip"
        if not z.exists():
            url = f"https://huggingface.co/datasets/{HF_DATASET}/resolve/{HF_REVISION}/images.zip"
            _download(url, z)
        digest = _sha256(z)
        if digest != IMAGES_ZIP_SHA256:
            raise RuntimeError(f"images.zip sha256 mismatch: {digest} != {IMAGES_ZIP_SHA256}")
        return z

    def image_reader(self):
        """Return a callable figure_id -> jpeg bytes."""
        if self.source_dir is not None and (self.source_dir / "images").is_dir():
            img_dir = self.source_dir / "images"
            return lambda fid: (img_dir / f"{fid}.jpg").read_bytes()
        zf = zipfile.ZipFile(self.images_zip())
        return lambda fid: zf.read(f"{fid}.jpg")


def load_tasks(source: CharXivSource, modes: tuple[str, ...] = MODES) -> list[CharXivTask]:
    descriptive = source.load_json("descriptive_val.json")
    reasoning = source.load_json("reasoning_val.json")
    image_meta = source.load_json("image_metadata_val.json")

    tasks: list[CharXivTask] = []
    for key in sorted(descriptive, key=int):
        d = descriptive[key]
        figure_id = int(d["figure_id"])
        meta = image_meta.get(key)
        if "descriptive" in modes:
            for i, qid in enumerate(d["qids"]):
                tasks.append(
                    CharXivTask(
                        mode="descriptive",
                        figure_id=figure_id,
                        question=descriptive_query_helper(qid, d["subplot_loc"]),
                        answer=d["answers"][i],
                        subq_idx=i,
                        qid=qid,
                        num_subplots=d["num_subplots"],
                        image_meta=meta,
                    )
                )
        if "reasoning" in modes:
            r = reasoning[key]
            tasks.append(
                CharXivTask(
                    mode="reasoning",
                    figure_id=figure_id,
                    question=reasoning_question(r),
                    answer=r["answer"],
                    inst_category=r["inst_category"],
                    raw_question=r["query"],
                    qa_source=r["qa_source"],
                    num_subplots=d["num_subplots"],
                    image_meta=meta,
                )
            )
    for t in tasks:
        if t.answer is None:
            raise ValueError(f"{t.task_id}: missing ground truth")
    return tasks


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render(template: str, values: dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        return values.get(m.group(1), m.group(0))

    return re.sub(r"\{\{([a-z_]+)\}\}", repl, template)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def heredoc_safe(text: str, marker: str) -> str:
    if marker in text:
        raise ValueError(f"heredoc marker {marker} occurs in text")
    return text


class CharXivAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        modes: tuple[str, ...] = MODES,
        source_dir: Path | None = None,
        cache_dir: Path = DEFAULT_CACHE_DIR,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = set(task_ids) if task_ids else None
        self.modes = tuple(modes)
        self.source = CharXivSource(source_dir=source_dir, cache_dir=cache_dir)

    def select_tasks(self) -> list[CharXivTask]:
        tasks = load_tasks(self.source, self.modes)
        if self.task_ids is not None:
            tasks = [t for t in tasks if t.task_id in self.task_ids or t.task_name in self.task_ids]
        if self.limit is not None:
            tasks = tasks[: self.limit]
        return tasks

    def run(self) -> list[Path]:
        tasks = self.select_tasks()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        read_image = self.source.image_reader()
        paths = []
        for task in tasks:
            paths.append(self.write_task(task, read_image(task.figure_id)))
        print(f"Generated {len(paths)} CharXiv tasks in {self.output_dir}")
        return paths

    def write_task(self, task: CharXivTask, image_bytes: bytes) -> Path:
        task_dir = self.output_dir / task.task_id
        if task_dir.exists():
            if not self.overwrite:
                raise FileExistsError(f"{task_dir} exists; pass --overwrite")
            shutil.rmtree(task_dir)
        shutil.copytree(
            TEMPLATE_DIR, task_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )

        meta = task.image_meta or {}
        tags = ["chart-understanding", "multimodal", "vqa", task.mode]
        if meta.get("category"):
            tags.append(sanitize(meta["category"]))
        values = {
            "task_name": task.task_name,
            "authors": ",\n".join(f"  {{ name = {toml_string(a)} }}" for a in AUTHORS),
            "tags": ", ".join(toml_string(t) for t in tags),
            "category": f"chart-{task.mode}",
            "image_path": f"{IMAGE_DIR_IN_CONTAINER}/{task.image_filename}",
            "image_filename": task.image_filename,
            "answer_path": ANSWER_PATH,
            "question": task.question,
            "answer": heredoc_safe(task.answer, "CHARXIV_ORACLE_EOF"),
        }
        for rel in ["task.toml", "instruction.md", "solution/solve.sh", "environment/Dockerfile"]:
            p = task_dir / rel
            p.write_text(render(p.read_text(encoding="utf-8"), values), encoding="utf-8")

        img_dir = task_dir / "environment" / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / task.image_filename).write_bytes(image_bytes)

        tests_dir = task_dir / "tests"
        shutil.copy2(UPSTREAM_CONSTANTS_FILE, tests_dir / "charxiv_constants.py")
        cfg = task.grading_config()
        cfg["source"] = {
            "github": f"{GITHUB_REPO}@{GITHUB_COMMIT}",
            "hf": f"{HF_DATASET}@{HF_REVISION}",
            "split": SPLIT,
            "num_subplots": task.num_subplots,
            "qa_source": task.qa_source,
            "category": meta.get("category"),
            "year": meta.get("year"),
            "paper_id": meta.get("paper_id"),
        }
        (tests_dir / "config.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        for script in [task_dir / "solution" / "solve.sh", tests_dir / "test.sh"]:
            script.chmod(0o755)
        return task_dir
