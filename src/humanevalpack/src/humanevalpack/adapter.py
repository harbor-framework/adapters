"""HumanEvalPack (HumanEvalFix) adapter for Harbor.

Converts the HumanEvalFix bug-repair split of ``bigcode/humanevalpack`` into
Harbor tasks, one per (language, problem). Each task gives the agent a single
runnable source file containing the buggy function followed by the upstream
tests (the "HumanEvalFixTests" setting of the original benchmark), and the
verifier re-runs the upstream tests the same way the upstream evaluator does.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from datasets import load_dataset

from .languages import (
    DEFAULT_LANGUAGES,
    HF_PREFIX_TO_KEY,
    LANGUAGES,
    LanguageSpec,
    build_program,
    fixed_declaration,
)

DATASET_NAME = "bigcode/humanevalpack"
DATASET_REVISION = "9a41762f73a8cb23bb5811b73d5aab164efcf378"
DATASET_SPLIT = "test"
TASK_NAME_PREFIX = "bigcode/humanevalpack__"
ORACLE_DELIMITER = "HUMANEVALPACK_ORACLE_EOF"

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "task-template"
DOCKERFILES_DIR = PACKAGE_DIR / "dockerfiles"

# Upstream Cargo.toml used by the octopack evaluator (Muennighoff/code_eval_octopack)
RUST_CARGO_TOML = """[package]
name = "rust"
version = "0.1.0"
edition = "2021"

[dependencies]
rand = "0.4"
regex = "1"
md5 = "0.7.0"
"""

VERIFIER_TIMEOUT = {
    "python": 120.0,
    "js": 120.0,
    "java": 180.0,
    "go": 300.0,
    "cpp": 240.0,
    "rust": 900.0,
}
BUILD_TIMEOUT = {"rust": 1800.0}

# Tasks that cannot be graded reliably because of an upstream defect that the
# adapter cannot repair without changing the benchmark. Skipped by default
# (generate them anyway with --include-excluded).
EXCLUDED_TASKS = {
    "go-95": (
        "canonical solution of CheckDictCase stops after the second key, so the "
        "result depends on Go's random map iteration order; the oracle passes "
        "only ~70% of runs (14/20 locally)"
    ),
    "rust-32": (
        "the test checks find_zero on 100 random polynomials and the canonical "
        "Newton iteration has no iteration limit, so on some draws it never "
        "converges and the test hangs until the timeout"
    ),
}

# Prompt structure follows the OpenHands HumanEvalFix runner used for the
# existing `humanevalfix` (Python) adapter, generalised to other languages, and
# keeps the upstream HumanEvalFix instruction ("Fix bugs in <entry_point>.").
INSTRUCTION_TEMPLATE = """Fix bugs in {entry_point}.

Please fix the function in {file_path} such that all test cases pass.
Environment has been set up for you to start working. You may assume all necessary tools are installed.
You can run the tests with:

```
{run_command}
```
{extra_notes}
# Problem Statement
{problem_statement}

IMPORTANT: You should ONLY interact with the environment provided to you AND NEVER ASK FOR HUMAN HELP.
You should NOT modify the existing test code at the end of {file_path}; it is re-run unchanged by the grader. If needed, you can add new test cases in a NEW file to reproduce the issue.
You SHOULD INCLUDE PROPER INDENTATION in your edit commands."""

EXTRA_NOTES = {
    "js": "\nThe program must not print anything when it is run: any output on stdout or stderr (including failed `console.assert` calls) counts as a failure.\n",
}


@dataclass(frozen=True)
class HumanEvalPackTask:
    spec: LanguageSpec
    row: dict[str, Any]

    @property
    def number(self) -> int:
        return int(str(self.row["task_id"]).split("/")[1])

    @property
    def task_id(self) -> str:
        return f"{self.spec.key}-{self.number}"

    @property
    def source_task_id(self) -> str:
        return str(self.row["task_id"])

    @property
    def buggy_program(self) -> str:
        return build_program(self.spec.key, self.row, self.row["buggy_solution"])

    @property
    def oracle_program(self) -> str:
        return build_program(self.spec.key, self.row, self.row["canonical_solution"])

    @property
    def difficulty(self) -> str:
        # Same heuristic as the existing humanevalfix adapter
        if self.row.get("bug_type") in {"excess logic", "missing logic", "variable misuse"}:
            return "medium"
        return "easy"

    @property
    def instruction(self) -> str:
        fence = "```"
        problem = f"{fence}{self.spec.key}\n{self.buggy_program.rstrip()}\n{fence}"
        return INSTRUCTION_TEMPLATE.format(
            entry_point=self.row["entry_point"],
            file_path=self.spec.file_path,
            run_command=self.spec.run_command,
            extra_notes=EXTRA_NOTES.get(self.spec.key, ""),
            problem_statement=problem,
        )


def _toml_str(value: Any) -> str:
    """Escape a value for use inside a TOML basic string."""
    return json.dumps(str(value))[1:-1]


def render(template: str, replacements: dict[str, str]) -> str:
    """Single-pass placeholder substitution; unknown ``{...}`` are left alone."""

    def repl(m: re.Match[str]) -> str:
        return replacements.get(m.group(1), m.group(0))

    return re.sub(r"\{([a-z_]+)\}", repl, template)


def _normalize_task_id(value: str) -> str:
    """Accept "js-0", "JavaScript/0" or "bigcode/humanevalpack__js-0"."""
    value = value.strip()
    if value.startswith(TASK_NAME_PREFIX):
        value = value[len(TASK_NAME_PREFIX):]
    if "/" in value:
        prefix, num = value.split("/", 1)
        key = HF_PREFIX_TO_KEY.get(prefix, prefix.lower())
        return f"{key}-{num}"
    return value.lower()


class HumanEvalPackAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        languages: list[str] | None = None,
        dataset_revision: str = DATASET_REVISION,
        include_excluded: bool = False,
        **kwargs: Any,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = {_normalize_task_id(t) for t in task_ids} if task_ids else None
        self.languages = languages or list(DEFAULT_LANGUAGES)
        unknown = [lang for lang in self.languages if lang not in LANGUAGES]
        if unknown:
            raise ValueError(
                f"Unknown language(s) {unknown}; choose from {sorted(LANGUAGES)}"
            )
        self.dataset_revision = dataset_revision
        self.include_excluded = include_excluded

    # ------------------------------------------------------------------ loading
    def load_tasks(self) -> list[HumanEvalPackTask]:
        tasks: list[HumanEvalPackTask] = []
        for lang in self.languages:
            spec = LANGUAGES[lang]
            ds = load_dataset(
                DATASET_NAME,
                spec.hf_config,
                split=DATASET_SPLIT,
                revision=self.dataset_revision,
            )
            lang_tasks = [HumanEvalPackTask(spec=spec, row=dict(r)) for r in ds]
            if not self.include_excluded:
                for t in lang_tasks:
                    if t.task_id in EXCLUDED_TASKS:
                        print(f"Skipping {t.task_id}: {EXCLUDED_TASKS[t.task_id]}")
                lang_tasks = [t for t in lang_tasks if t.task_id not in EXCLUDED_TASKS]
            lang_tasks.sort(key=lambda t: t.number)
            tasks.extend(lang_tasks)
        if self.task_ids is not None:
            tasks = [t for t in tasks if t.task_id in self.task_ids]
            missing = self.task_ids - {t.task_id for t in tasks}
            if missing:
                print(f"Warning: task ids not found: {sorted(missing)}")
        if self.limit is not None:
            # --limit applies per language so that `--limit 3` yields a few tasks
            # of every selected language.
            per_lang: dict[str, int] = {}
            limited = []
            for t in tasks:
                if per_lang.get(t.spec.key, 0) < self.limit:
                    limited.append(t)
                    per_lang[t.spec.key] = per_lang.get(t.spec.key, 0) + 1
            tasks = limited
        return tasks

    # ------------------------------------------------------------------ writing
    def run(self) -> list[HumanEvalPackTask]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        tasks = self.load_tasks()
        written = skipped = 0
        for task in tasks:
            if self._write_task(task):
                written += 1
            else:
                skipped += 1
        print(
            f"Generated {written} HumanEvalPack tasks in {self.output_dir}"
            + (f" (skipped {skipped} existing; use --overwrite)" if skipped else "")
        )
        return tasks

    def _write_task(self, task: HumanEvalPackTask) -> bool:
        task_dir = self.output_dir / task.task_id
        if task_dir.exists():
            if not self.overwrite:
                return False
            shutil.rmtree(task_dir)

        shutil.copytree(
            TEMPLATE_DIR,
            task_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        spec = task.spec
        oracle = task.oracle_program
        if ORACLE_DELIMITER in oracle:
            raise ValueError(f"{task.task_id}: oracle contains heredoc delimiter")

        replacements = {
            "task_id": task.task_id,
            "language": spec.display,
            "language_key": spec.key,
            "entry_point": _toml_str(task.row["entry_point"]),
            "difficulty": task.difficulty,
            "source_task_id": _toml_str(task.source_task_id),
            "bug_type": _toml_str(task.row.get("bug_type", "")),
            "failure_symptoms": _toml_str(task.row.get("failure_symptoms", "")),
            "verifier_timeout": str(VERIFIER_TIMEOUT[spec.key]),
            "build_timeout": str(BUILD_TIMEOUT.get(spec.key, 600.0)),
            "instruction": task.instruction,
            "file_path": spec.file_path,
            "oracle_program": oracle.rstrip("\n"),
        }
        for rel in ("task.toml", "instruction.md", "solution/solve.sh"):
            path = task_dir / rel
            path.write_text(
                render(path.read_text(encoding="utf-8"), replacements),
                encoding="utf-8",
                newline="\n",
            )

        # Environment: per-language Dockerfile + the buggy file in workspace/
        env_dir = task_dir / "environment"
        shutil.copy(DOCKERFILES_DIR / f"{spec.key}.Dockerfile", env_dir / "Dockerfile")
        workspace = env_dir / "workspace"
        rel_file = Path(spec.file_path).relative_to("/workspace")
        (workspace / rel_file).parent.mkdir(parents=True, exist_ok=True)
        (workspace / rel_file).write_text(task.buggy_program, encoding="utf-8", newline="\n")
        if spec.key == "rust":
            (workspace / "Cargo.toml").write_text(RUST_CARGO_TOML, encoding="utf-8", newline="\n")

        # Verifier inputs: pristine upstream test block + language config
        tests_dir = task_dir / "tests"
        (tests_dir / "test_block.txt").write_text(task.row["test"], encoding="utf-8", newline="\n")
        (tests_dir / "config.json").write_text(
            json.dumps(
                {
                    "lang": spec.key,
                    "file": spec.file_path,
                    "source_task_id": task.source_task_id,
                    "dataset": DATASET_NAME,
                    "dataset_revision": self.dataset_revision,
                    "declaration_fix": fixed_declaration(spec.key, task.row)[1],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        for script in (task_dir / "solution" / "solve.sh", tests_dir / "test.sh"):
            script.chmod(0o755)
        return True
