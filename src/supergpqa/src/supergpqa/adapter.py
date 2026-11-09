"""Reproducibly convert the pinned SuperGPQA zero-shot bank into Harbor tasks."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml

UPSTREAM_COMMIT = "e31e8bf3e7089aef808be5ddecafd4538dee6e41"
DATA_SHA256 = "28b998e70205ee95e540317b5adc06a06552a3961fb50b153df126b833f7a910"
DATA_URL = (
    "https://raw.githubusercontent.com/SuperGPQA/SuperGPQA/"
    f"{UPSTREAM_COMMIT}/data/SuperGPQA-all.jsonl"
)
PACKAGE_DIR = Path(__file__).parent
TEMPLATE_DIR = PACKAGE_DIR / "task-template"
ANSWER_HANDOFF = (
    "\n\nSave your complete response, including the final answer line, "
    "to /app/answer.txt. This is a closed-book question: do not use external "
    "knowledge sources, web search, or computational tools to solve it. "
    "Use the terminal only to write your response file.\n"
)


def load_records(path: Path | None, cache_dir: Path) -> list[dict[str, Any]]:
    """Reject changed source data rather than silently changing the benchmark."""
    if path is None:
        path = cache_dir / f"SuperGPQA-all-{UPSTREAM_COMMIT}.jsonl"
        if not path.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            with urlopen(DATA_URL, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != DATA_SHA256:
                raise ValueError(
                    "Downloaded dataset checksum does not match pinned source"
                )
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != DATA_SHA256:
        raise ValueError(f"Dataset checksum mismatch: {path}")
    records = [json.loads(line) for line in data.decode("utf-8").splitlines()]
    validate_records(records)
    return records


def validate_records(records: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for record in records:
        task_id = record["uuid"]
        if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-f]{32}", task_id):
            raise ValueError(f"Invalid upstream UUID: {task_id!r}")
        if task_id in seen:
            raise ValueError(f"Duplicate UUID: {task_id}")
        seen.add(task_id)
        options = record["options"]
        if not 2 <= len(options) <= 10 or not all(isinstance(o, str) for o in options):
            raise ValueError(f"Invalid options: {task_id}")
        answer = record["answer_letter"]
        if answer not in [chr(65 + i) for i in range(len(options))]:
            raise ValueError(f"Invalid answer letter: {task_id}")
        if options[ord(answer) - 65] != record["answer"]:
            raise ValueError(f"Answer text/letter mismatch: {task_id}")
        for key in ("question", "discipline", "field", "subfield", "difficulty"):
            if not isinstance(record[key], str) or not record[key]:
                raise ValueError(f"Invalid {key}: {task_id}")
        if record["difficulty"] not in ("easy", "middle", "hard"):
            raise ValueError(f"Unknown difficulty: {task_id}")


def original_prompt(record: dict[str, Any]) -> str:
    """Exactly mirror upstream infer/data_loader.py's zero-shot rendering."""
    template = yaml.safe_load((PACKAGE_DIR / "zero-shot.yaml").read_text())[
        "prompt_format"
    ][0]
    question = (
        record["question"]
        + "\n"
        + "\n".join(
            f"{chr(65 + i)}) {option}" for i, option in enumerate(record["options"])
        )
    )
    return template.format(question)


def parity_subset(
    records: list[dict[str, Any]], size: int, seed: int
) -> list[dict[str, Any]]:
    """Deterministic proportional sampling by full taxonomy and difficulty.

    This is a selection utility, not an approved experiment plan. Small subsets
    cannot cover every stratum; the manifest records the exact selected UUIDs.
    """
    if not 1 <= size <= len(records):
        raise ValueError("parity-size must be between 1 and the dataset size")
    strata: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        strata[
            tuple(row[k] for k in ("discipline", "field", "subfield", "difficulty"))
        ].append(row)
    quotas = {key: size * len(rows) // len(records) for key, rows in strata.items()}
    remaining = size - sum(quotas.values())
    ordered = sorted(
        strata, key=lambda key: (-(size * len(strata[key]) % len(records)), key)
    )
    for key in ordered[:remaining]:
        quotas[key] += 1
    selected = []
    for key, rows in sorted(strata.items()):
        ranked = sorted(
            rows,
            key=lambda row: hashlib.sha256(f"{seed}:{row['uuid']}".encode()).digest(),
        )
        selected.extend(ranked[: quotas[key]])
    return sorted(selected, key=lambda row: row["uuid"])


class SuperGPQAAdapter:
    NAME = "supergpqa"

    def __init__(
        self,
        output_dir: Path,
        records: list[dict[str, Any]],
        *,
        overwrite: bool = False,
    ):
        validate_records(records)
        self.output_dir = Path(output_dir)
        self.records = records
        self.overwrite = overwrite

    @staticmethod
    def task_id(record: dict[str, Any]) -> str:
        return "supergpqa-" + record["uuid"]

    def run(self) -> list[Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        targets = [self.output_dir / self.task_id(row) for row in self.records]
        for target in targets:
            if target.exists() and not self.overwrite:
                raise FileExistsError(
                    f"Task exists; use --overwrite explicitly: {target}"
                )
            if target.is_symlink():
                raise ValueError(f"Refusing to overwrite task symlink: {target}")
        for row, target in zip(self.records, targets, strict=True):
            self._generate(row, target)
        return targets

    def _generate(self, row: dict[str, Any], target: Path) -> None:
        with tempfile.TemporaryDirectory(
            prefix=".supergpqa-", dir=self.output_dir
        ) as staging:
            task = Path(staging) / "task"
            shutil.copytree(TEMPLATE_DIR, task)
            config = (task / "task.toml").read_text()
            replacements = {
                "__TASK_ID__": self.task_id(row),
                "__DIFFICULTY__": "medium"
                if row["difficulty"] == "middle"
                else row["difficulty"],
                "__METADATA__": "\n".join(
                    f"{key} = {json.dumps(row[key], ensure_ascii=False)}"
                    for key in ("uuid", "discipline", "field", "subfield", "difficulty")
                ),
            }
            # Keep original difficulty under a distinct key to avoid duplicate TOML keys.
            replacements["__METADATA__"] = replacements["__METADATA__"].replace(
                "\ndifficulty =", "\nsource_difficulty ="
            )
            for key, value in replacements.items():
                config = config.replace(key, value)
            (task / "task.toml").write_text(config)
            instruction = (
                (TEMPLATE_DIR / "instruction.md")
                .read_text()
                .replace("__PROMPT__", original_prompt(row))
                .replace("__HANDOFF__", ANSWER_HANDOFF)
            )
            (task / "instruction.md").write_text(instruction)
            # Gold data and oracle are outside the Docker build context.
            (task / "tests/record.json").write_text(
                json.dumps(row, ensure_ascii=False) + "\n"
            )
            for filename in ("upstream_parser.py", "scoring.py"):
                shutil.copyfile(PACKAGE_DIR / filename, task / "tests" / filename)
            solution = (
                (task / "solution/solve.sh")
                .read_text()
                .replace("__LETTER__", row["answer_letter"])
            )
            (task / "solution/solve.sh").write_text(solution)
            if target.exists():
                shutil.rmtree(target)
            task.replace(target)
