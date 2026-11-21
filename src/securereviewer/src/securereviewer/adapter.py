"""Generate Harbor tasks from SecureReviewer's expert-refined test set.

One Harbor task per test item with a security issue. The agent sees the code change
(unified diff) and must write a structured security review (Security type / Description /
Impact / Advice) to /workspace/review.txt. The verifier scores it with SecureReviewer's
SecureBLEU script (evaluate/SecureBleu.py), downloaded unmodified from the pinned commit.
"""

from __future__ import annotations

import json
import random
import shutil
from collections import defaultdict
import urllib.request
from pathlib import Path

UPSTREAM_REPO = "SIMIAO515/SecureReviewer"
# Pinned upstream commit for both the data and the scoring script.
UPSTREAM_COMMIT = "86df98bf8e0a4057cb4d89490cde400359af290d"
TEST_URL = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_COMMIT}/dataset/test.jsonl"

ORG = "securereviewer"
DATASET = "securereviewer"

# SecureBLEU skips items whose reference is "No Issue" (process_jsonl `continue`s on them),
# so they never contribute to the score; the adapter leaves them out.
SKIPPED_TYPE = "No Issue"

TEMPLATE_DIR = Path(__file__).parent / "task-template"

# Parity subset: ~10% of the 261 tasks, stratified by security type in proportion to its
# size, sampled with a fixed seed so the subset is reproducible.
PARITY_SIZE = 25
PARITY_SEED = 42


def parity_subset(candidates: list[tuple[int, dict]], size: int = PARITY_SIZE, seed: int = PARITY_SEED) -> list[tuple[int, dict]]:
    """Stratified, seeded sample of (index, item) pairs (proportional allocation, largest remainder)."""
    by_type: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for idx, item in candidates:
        by_type[item["security_type"]].append((idx, item))
    total = len(candidates)
    quotas = {t: size * len(v) / total for t, v in by_type.items()}
    alloc = {t: int(q) for t, q in quotas.items()}
    for t in sorted(quotas, key=lambda t: (alloc[t] - quotas[t], t))[: size - sum(alloc.values())]:
        alloc[t] += 1
    rng = random.Random(seed)
    chosen: list[tuple[int, dict]] = []
    for t in sorted(by_type):
        chosen.extend(rng.sample(by_type[t], alloc[t]))
    return sorted(chosen, key=lambda x: x[0])


def task_id_for_index(idx: int) -> str:
    """Stable id from the 0-based line number in dataset/test.jsonl."""
    return f"test-{idx:03d}"


def load_test_items(data_file: Path | None = None) -> list[dict]:
    if data_file is not None:
        text = Path(data_file).read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(TEST_URL, timeout=60) as resp:
            text = resp.read().decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def render_diff_block(patch: str) -> str:
    fence = "~~~~"
    while fence in patch:
        fence += "~"
    return f"{fence}diff\n{patch.rstrip()}\n{fence}"


class SecureReviewerAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        data_file: Path | None = None,
        split: str = "full",
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = set(task_ids) if task_ids else None
        self.data_file = data_file
        if split not in ("full", "parity"):
            raise ValueError(f"Unknown split {split!r}; expected 'full' or 'parity'")
        self.split = split

    def run(self) -> None:
        items = load_test_items(self.data_file)
        candidates = [(i, it) for i, it in enumerate(items) if it["security_type"] != SKIPPED_TYPE]
        pool = parity_subset(candidates) if self.split == "parity" else candidates
        selected = [(i, it) for i, it in pool if self.task_ids is None or task_id_for_index(i) in self.task_ids]
        if self.limit is not None:
            selected = selected[: self.limit]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = skipped = 0
        for idx, item in selected:
            task_dir = self.output_dir / task_id_for_index(idx)
            if task_dir.exists():
                if not self.overwrite:
                    skipped += 1
                    continue
                shutil.rmtree(task_dir)
            self._write_task(task_dir, idx, item)
            written += 1
        print(
            f"Wrote {written} tasks to {self.output_dir} (skipped {skipped} existing; "
            f"{len(candidates)} of {len(items)} test items have a security issue)"
        )

    def _write_task(self, task_dir: Path, idx: int, item: dict) -> None:
        shutil.copytree(TEMPLATE_DIR, task_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        task_id = task_id_for_index(idx)

        toml_path = task_dir / "task.toml"
        toml_path.write_text(
            toml_path.read_text(encoding="utf-8")
            .replace("{task_name}", f"{ORG}/{DATASET}__{task_id}")
            .replace("{source_index}", str(idx))
            .replace("{security_type}", item["security_type"]),
            encoding="utf-8",
            newline="\n",
        )

        instr_path = task_dir / "instruction.md"
        instr_path.write_text(
            instr_path.read_text(encoding="utf-8").replace("{diff_block}", render_diff_block(item["patch"])),
            encoding="utf-8",
            newline="\n",
        )

        (task_dir / "environment" / "patch.diff").write_text(item["patch"], encoding="utf-8", newline="\n")

        # Reference review: only uploaded at verification time.
        reference = {k: item[k] for k in ("patch", "security_type", "description", "impact", "advice", "comment")}
        (task_dir / "tests" / "reference.json").write_text(json.dumps(reference, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")

        # Oracle: the expert-refined reference comment, in the review format the parser expects.
        (task_dir / "solution" / "review.txt").write_text(item["comment"], encoding="utf-8", newline="\n")
        _fix_line_endings(task_dir)


def _fix_line_endings(task_dir: Path) -> None:
    """Shell scripts must keep LF endings even when generated on Windows."""
    for sh in task_dir.rglob("*.sh"):
        sh.write_bytes(sh.read_bytes().replace(b"\r\n", b"\n"))
