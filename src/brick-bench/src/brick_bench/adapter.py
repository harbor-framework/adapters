"""BrickBench adapter: converts all 300 upstream BrickBench tasks into Harbor format."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, StrictUndefined

UPSTREAM_REPO = "https://github.com/kulits/BrickAgent"
UPSTREAM_COMMIT = "b3df55e36c669b22ef089b13db1ee841907d09b3"
UPSTREAM_RAW_BASE = f"https://raw.githubusercontent.com/kulits/BrickAgent/{UPSTREAM_COMMIT}"

ORACLE_REPO = "https://huggingface.co/datasets/kulits/BrickBench-Runs"
ORACLE_REVISION = "feecb33e7f2aa9d35e6e894c7333d44602c12ca0"
ORACLE_SYSTEM = "astra"
ORACLE_RAW_BASE = f"{ORACLE_REPO}/raw/{ORACLE_REVISION}"

SPLITS: tuple[str, ...] = ("model", "set", "alt-build")
HF_SPLIT_NAME: dict[str, str] = {"model": "model", "set": "set", "alt-build": "alt"}

# BrickLink Designer Program categories in upstream task order (10 tasks per block).
CATEGORIES: tuple[str, ...] = (
    "Medieval / Castle",
    "Vehicle / Boat / Airplane",
    "Train",
    "Space / Sci-Fi / Fantasy",
    "Art / Object",
    "Building",
    "Floral / Nature",
    "Animal",
    "Pirate",
    "History / Period",
)

# Stratified 30-task parity subset: first task of each of the 10 categories in each split.
PARITY_INDICES: tuple[int, ...] = (1, 11, 21, 31, 41, 51, 61, 71, 81, 91)
PARITY_TASK_IDS: tuple[str, ...] = tuple(
    f"{prefix}-{idx:03d}"
    for prefix in ("model", "set", "alt")
    for idx in PARITY_INDICES
)

# 9-task E2E oracle smoke subset: 3 tasks per split across 3 distinct categories.
ORACLE_SMOKE_TASK_IDS: tuple[str, ...] = (
    "model-001",
    "model-011",
    "model-021",
    "set-001",
    "set-011",
    "set-021",
    "alt-001",
    "alt-011",
    "alt-021",
)

TEMPLATE_DIR = Path(__file__).parent / "task-template"
DEFAULT_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "harbor-brick-bench"


@dataclass(frozen=True)
class BrickBenchTask:
    task_id: str
    split: str
    category: str
    prompt: str
    questions: list[dict]


def task_category(task_id: str) -> str:
    """Return the BrickLink category for an upstream task ID (e.g. model-001)."""
    _, num_str = task_id.rsplit("-", 1)
    idx = (int(num_str) - 1) // 10
    if not 0 <= idx < len(CATEGORIES):
        raise ValueError(f"Task ID {task_id!r} index out of expected 1..100 range")
    return CATEGORIES[idx]


def sanitize_task_name(task_id: str) -> str:
    """Return a registry-safe Harbor task name under the brickbench namespace."""
    slug = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in task_id.lower()).strip("-")
    return f"brickbench/{slug}"


def _download_cached(url: str, dest: Path) -> Path:
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "harbor-brick-bench-adapter/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp, tmp.open("wb") as out:
        shutil.copyfileobj(resp, out)
    tmp.replace(dest)
    return dest


def _read_upstream_text(rel_path: str, *, repo_path: Path | None, cache_dir: Path) -> str:
    if repo_path is not None:
        local = repo_path / rel_path
        if not local.is_file():
            raise FileNotFoundError(f"Missing upstream file in --repo-path: {local}")
        return local.read_text(encoding="utf-8")
    cached = cache_dir / "upstream" / UPSTREAM_COMMIT / rel_path
    _download_cached(f"{UPSTREAM_RAW_BASE}/{rel_path}", cached)
    return cached.read_text(encoding="utf-8")


def _read_oracle_build(
    task_id: str,
    split: str,
    *,
    oracle_dir: Path | None,
    cache_dir: Path,
) -> str:
    hf_split = HF_SPLIT_NAME[split]
    rel_path = f"{ORACLE_SYSTEM}/{hf_split}/{task_id}/build.py"
    if oracle_dir is not None:
        candidates = (
            oracle_dir / rel_path,
            oracle_dir / hf_split / task_id / "build.py",
            oracle_dir / task_id / "build.py",
        )
        for cand in candidates:
            if cand.is_file():
                return cand.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Oracle build.py for {task_id} not found under {oracle_dir}")
    cached = cache_dir / "oracle" / ORACLE_REVISION / rel_path
    _download_cached(f"{ORACLE_RAW_BASE}/{rel_path}", cached)
    return cached.read_text(encoding="utf-8")


def render_instruction(prompt_template: str, object_prompt: str, split: str) -> str:
    """Render instruction.md byte-for-byte identically to upstream scripts/prompt.py."""
    return (
        Environment(undefined=StrictUndefined, keep_trailing_newline=True)
        .from_string(prompt_template)
        .render(object_prompt=object_prompt, split=split)
    )


def _make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class BrickBenchAdapter:
    """Adapter that generates Harbor task directories for BrickBench."""

    def __init__(
        self,
        output_dir: Path,
        *,
        split: str = "all",
        task_ids: list[str] | None = None,
        limit: int | None = None,
        overwrite: bool = False,
        repo_path: Path | None = None,
        oracle_dir: Path | None = None,
        cache_dir: Path | None = None,
        skip_oracle_fetch: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.split = split
        self.task_ids = list(task_ids) if task_ids is not None else None
        self.limit = limit
        self.overwrite = overwrite
        self.repo_path = Path(repo_path) if repo_path is not None else None
        self.oracle_dir = Path(oracle_dir) if oracle_dir is not None else None
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
        self.skip_oracle_fetch = skip_oracle_fetch

        self._prompt_template = _read_upstream_text(
            "scripts/prompt.md", repo_path=self.repo_path, cache_dir=self.cache_dir
        )
        self._alt_inventory_text = _read_upstream_text(
            "benchmark/alt-build/inventory.json",
            repo_path=self.repo_path,
            cache_dir=self.cache_dir,
        )
        self._tasks = self._load_tasks()

    def _load_tasks(self) -> list[BrickBenchTask]:
        if self.split == "all" or self.split == "parity" or self.split == "oracle-smoke":
            selected_splits = SPLITS
        elif self.split in SPLITS:
            selected_splits = (self.split,)
        else:
            raise ValueError(
                f"Unknown split {self.split!r}. Expected one of: all, parity, oracle-smoke, {', '.join(SPLITS)}"
            )

        all_tasks: list[BrickBenchTask] = []
        for sp in selected_splits:
            raw = json.loads(
                _read_upstream_text(
                    f"benchmark/{sp}/tasks.json",
                    repo_path=self.repo_path,
                    cache_dir=self.cache_dir,
                )
            )
            for item in raw:
                tid = item["id"]
                all_tasks.append(
                    BrickBenchTask(
                        task_id=tid,
                        split=sp,
                        category=task_category(tid),
                        prompt=item["prompt"],
                        questions=item["questions"],
                    )
                )

        if self.split == "parity":
            parity_set = set(PARITY_TASK_IDS)
            all_tasks = [t for t in all_tasks if t.task_id in parity_set]
        elif self.split == "oracle-smoke":
            smoke_set = set(ORACLE_SMOKE_TASK_IDS)
            all_tasks = [t for t in all_tasks if t.task_id in smoke_set]

        if self.task_ids is not None:
            by_id = {t.task_id: t for t in all_tasks}
            missing = [tid for tid in self.task_ids if tid not in by_id]
            if missing:
                raise ValueError(f"Unknown task ID(s) for split={self.split!r}: {', '.join(missing)}")
            all_tasks = [by_id[tid] for tid in self.task_ids]

        if self.limit is not None:
            if self.limit < 0:
                raise ValueError(f"--limit must be non-negative, got {self.limit}")
            all_tasks = all_tasks[: self.limit]

        return all_tasks

    @property
    def tasks(self) -> list[BrickBenchTask]:
        return list(self._tasks)

    def _render_task_toml(self, task: BrickBenchTask) -> str:
        tpl = (TEMPLATE_DIR / "task.toml").read_text(encoding="utf-8")
        return (
            tpl.replace("@@TASK_NAME@@", sanitize_task_name(task.task_id))
            .replace("@@TASK_ID@@", task.task_id)
            .replace("@@SPLIT@@", task.split)
            .replace("@@CATEGORY@@", task.category)
        )

    def _render_agent_dockerfile(self, task: BrickBenchTask) -> str:
        base = (TEMPLATE_DIR / "environment" / "Dockerfile").read_text(encoding="utf-8")
        if task.split != "alt-build":
            return base
        return (
            base.rstrip()
            + "\n\n# Alt-Build restricted part inventory (retail set 10698)\n"
            + "COPY inventory.json /opt/brickbench/inventory.json\n"
            + "RUN chmod 0444 /opt/brickbench/inventory.json\n"
            + "ENV BRICKAGENT_SET=/opt/brickbench/inventory.json\n"
        )

    def generate_task(self, task: BrickBenchTask) -> Path:
        task_dir = self.output_dir / task.task_id
        if task_dir.exists():
            if not self.overwrite:
                return task_dir
            shutil.rmtree(task_dir)

        env_dir = task_dir / "environment"
        sol_dir = task_dir / "solution"
        tests_dir = task_dir / "tests"
        for d in (env_dir, sol_dir, tests_dir):
            d.mkdir(parents=True, exist_ok=True)

        # 1. task.toml & instruction.md
        (task_dir / "task.toml").write_text(self._render_task_toml(task), encoding="utf-8")
        instruction = render_instruction(self._prompt_template, task.prompt, task.split)
        (task_dir / "instruction.md").write_text(instruction, encoding="utf-8")

        # 2. Agent environment/
        (env_dir / "Dockerfile").write_text(self._render_agent_dockerfile(task), encoding="utf-8")
        if task.split == "alt-build":
            (env_dir / "inventory.json").write_text(self._alt_inventory_text, encoding="utf-8")

        # 3. Oracle solution/
        solve_dst = sol_dir / "solve.sh"
        shutil.copyfile(TEMPLATE_DIR / "solution" / "solve.sh", solve_dst)
        _make_executable(solve_dst)
        if not self.skip_oracle_fetch:
            build_py = _read_oracle_build(
                task.task_id,
                task.split,
                oracle_dir=self.oracle_dir,
                cache_dir=self.cache_dir,
            )
            (sol_dir / "build.py").write_text(build_py, encoding="utf-8")

        # 4. Separate verifier tests/
        for fname in ("Dockerfile", "test.sh", "grade.py"):
            dst = tests_dir / fname
            shutil.copyfile(TEMPLATE_DIR / "tests" / fname, dst)
        _make_executable(tests_dir / "test.sh")

        task_payload = {
            "id": task.task_id,
            "split": task.split,
            "category": task.category,
            "prompt": task.prompt,
            "questions": task.questions,
            "upstream_commit": UPSTREAM_COMMIT,
            "inventory_sha256": (
                hashlib.sha256(self._alt_inventory_text.encode("utf-8")).hexdigest()
                if task.split == "alt-build"
                else None
            ),
        }
        (tests_dir / "task.json").write_text(
            json.dumps(task_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if task.split == "alt-build":
            (tests_dir / "inventory.json").write_text(self._alt_inventory_text, encoding="utf-8")

        return task_dir

    def run(self) -> list[Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if not self.skip_oracle_fetch and self.oracle_dir is None and len(self._tasks) > 1:
            to_fetch = [
                t
                for t in self._tasks
                if self.overwrite or not (self.output_dir / t.task_id).exists()
            ]
            if to_fetch:
                with ThreadPoolExecutor(max_workers=16) as pool:
                    list(
                        pool.map(
                            lambda t: _read_oracle_build(
                                t.task_id,
                                t.split,
                                oracle_dir=None,
                                cache_dir=self.cache_dir,
                            ),
                            to_fetch,
                        )
                    )
        return [self.generate_task(task) for task in self._tasks]
