"""MLOps-Bench -> Harbor adapter.

Converts every task under ``dataset/mlops-bench/<repo>/<stage>/<instance>/`` of
https://github.com/oracle-samples/mlops-bench into a Harbor task directory.

Upstream task layout and how each part is used:

    problem.json            -> instruction.md (the ``problem`` block, minus metadata)
    repo/                   -> environment/repo/ (the agent's editable /workspace)
    tests/test_f2p.py       -> tests/ (scoring; only visible to the verifier)
    tests/test_p2p.py       -> tests/ (scoring; only visible to the verifier)
    expected_changes.patch  -> solution/ (oracle; only visible to the oracle agent)
    metadata.json           -> task.toml metadata (F2P/P2P counts, stage, repo)
    oracle/, buggy/, benchmark_complete.json, README.md -> not used

Per the upstream README's evaluation-isolation rules, ``oracle/``, ``buggy/``,
``expected_changes.patch`` and ``metadata.json`` are never copied into the agent
environment.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UPSTREAM_REPO_URL = "https://github.com/oracle-samples/mlops-bench.git"
# Pinned upstream revision used to generate the dataset.
UPSTREAM_COMMIT = "8f48b685df0491af048bde4b56c7917d0e42d336"

DATASET_SUBDIR = Path("dataset") / "mlops-bench"
TASK_NAME_ORG = "oracle-samples"
TASK_NAME_PREFIX = "mlops-bench__"

TEMPLATE_DIR = Path(__file__).parent / "task-template"

STAGE_KEYWORDS = {
    "DATA_PIPELINE": "data-pipeline",
    "FEATURE_ENGINEERING": "feature-engineering",
    "MODEL_TRAINING": "model-training",
    "MODEL_SERVING": "model-serving",
    "MONITORING_OBSERVABILITY": "monitoring-observability",
    "CICD_GOVERNANCE": "cicd-governance",
    "E2E_FULL_MLOPS_FLOW": "e2e-mlops-flow",
}

IGNORED_COPY_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")

# Parity subset (`--split parity`): PARITY_TASKS_PER_STAGE tasks from each of
# the 7 MLOps stages, drawn with a fixed seed from the instance ids of that
# stage sorted by name, so the subset is deterministic and covers every stage.
PARITY_SEED = 42
PARITY_TASKS_PER_STAGE = 7


def parity_subset(tasks: list["UpstreamTask"]) -> list["UpstreamTask"]:
    rng = random.Random(PARITY_SEED)
    by_stage: dict[str, list[UpstreamTask]] = {}
    for task in sorted(tasks, key=lambda t: t.instance_id):
        by_stage.setdefault(task.stage, []).append(task)
    chosen: set[str] = set()
    for stage in sorted(by_stage):
        picks = rng.sample(by_stage[stage], min(PARITY_TASKS_PER_STAGE, len(by_stage[stage])))
        chosen.update(t.instance_id for t in picks)
    return [t for t in tasks if t.instance_id in chosen]


def slugify(instance_id: str) -> str:
    """Registry-safe, stable slug for an upstream instance id.

    ``MLO-25_GREAT_EXPECTATIONS__GREAT_EXPECTATIONS-04_MODEL_SERVING`` ->
    ``mlo-25-great-expectations-great-expectations-04-model-serving``
    """
    slug = re.sub(r"[^a-z0-9]+", "-", instance_id.lower())
    return re.sub(r"-{2,}", "-", slug).strip("-")


@dataclass(frozen=True)
class UpstreamTask:
    instance_id: str
    path: Path
    problem: dict[str, Any]
    metadata: dict[str, Any]

    @property
    def slug(self) -> str:
        return slugify(self.instance_id)

    @property
    def stage(self) -> str:
        return str(self.metadata["stage"])


# ---------------------------------------------------------------------------
# instruction rendering
# ---------------------------------------------------------------------------


def _is_identifier_like(value: Any) -> bool:
    """Field names, module paths, file paths: safe to render inline as code."""
    return (
        isinstance(value, (str, int, float))
        and not isinstance(value, bool)
        and bool(re.fullmatch(r"[\w./\-]+", str(value)))
    )


def _bullets(items: list[Any], indent: int = 0) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            lines.extend(_dict_bullets(item, indent))
        else:
            lines.append(f"{pad}- {item}")
    return lines


def _dict_bullets(data: dict[str, Any], indent: int = 0) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}- {key}:")
            lines.extend(_dict_bullets(value, indent + 1))
        elif isinstance(value, list):
            if not value:
                lines.append(f"{pad}- {key}: (none)")
            elif all(_is_identifier_like(v) for v in value):
                lines.append(f"{pad}- {key}: " + ", ".join(f"`{v}`" for v in value))
            else:
                lines.append(f"{pad}- {key}:")
                lines.extend(_bullets(value, indent + 1))
        else:
            lines.append(f"{pad}- {key}: {value}")
    return lines


def _section(title: str, body: list[str]) -> list[str]:
    body = [line for line in body if line is not None]
    if not body:
        return []
    return [f"## {title}", "", *body, ""]


def _subsection(title: str, items: list[Any] | None) -> list[str]:
    if not items:
        return []
    return [f"### {title}", "", *_bullets(items), ""]


def render_instruction(problem: dict[str, Any]) -> str:
    """Render the upstream ``problem`` block as agent-facing Markdown.

    Every field of ``problem`` except its ``metadata`` block is rendered, in a
    fixed order, without rewording. Unknown top-level fields (none exist at the
    pinned revision) are appended generically so nothing is silently dropped.
    """
    known = {
        "task_title",
        "problem_context",
        "your_task",
        "public_api_contract",
        "data_context",
        "system_context",
        "system_constraints",
        "evaluation_criteria",
        "metadata",
    }
    out: list[str] = [f"# {problem['task_title']}", ""]

    ctx = problem.get("problem_context", {})
    ctx_lines: list[str] = []
    for key in ("business_scenario", "current_state", "business_impact"):
        if ctx.get(key):
            ctx_lines += [str(ctx[key]), ""]
    if ctx.get("gaps"):
        ctx_lines += ["Current gaps:", "", *_bullets(ctx["gaps"]), ""]
    out += _section("Context", ctx_lines[:-1] if ctx_lines else [])

    task = problem.get("your_task", {})
    out += ["## Your Task", "", str(task.get("objective", "")), ""]
    out += _subsection("Requirements", task.get("requirements"))
    out += _subsection("Success Criteria", task.get("success_criteria"))
    out += _subsection("Technical Constraints", task.get("technical_constraints"))

    api = problem.get("public_api_contract", {})
    if api:
        out += ["## Public API Contract", "", *_dict_bullets(api), ""]

    data_ctx = problem.get("data_context", {})
    if data_ctx.get("datasets"):
        ds_lines: list[str] = []
        for ds in data_ctx["datasets"]:
            ds_lines.append(f"### Dataset `{ds.get('name', 'dataset')}`")
            ds_lines.append("")
            ds_lines.extend(_dict_bullets({k: v for k, v in ds.items() if k != "name"}))
            ds_lines.append("")
        out += _section("Data Context", ds_lines[:-1])

    sys_ctx = problem.get("system_context", {})
    if sys_ctx:
        out += ["## System Context", "", *_dict_bullets(sys_ctx), ""]

    constraints = problem.get("system_constraints", {}).get("constraints")
    if constraints:
        out += ["## System Constraints", "", *_bullets(constraints), ""]

    criteria = problem.get("evaluation_criteria", {})
    if criteria:
        out += ["## Evaluation Criteria", "", *_dict_bullets(criteria), ""]

    for key, value in problem.items():
        if key in known:
            continue
        title = key.replace("_", " ").title()
        if isinstance(value, dict):
            out += [f"## {title}", "", *_dict_bullets(value), ""]
        elif isinstance(value, list):
            out += [f"## {title}", "", *_bullets(value), ""]
        else:
            out += [f"## {title}", "", str(value), ""]

    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# adapter
# ---------------------------------------------------------------------------


class MLOpsBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        source_dir: Path | None = None,
        source_ref: str = UPSTREAM_COMMIT,
        stages: list[str] | None = None,
        split: str = "full",
        **kwargs: Any,
    ):
        if split not in {"full", "parity"}:
            raise ValueError(f"Unknown split {split!r} (expected 'full' or 'parity')")
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.source_dir = Path(source_dir) if source_dir else None
        self.source_ref = source_ref
        self.stages = [s.upper() for s in stages] if stages else None
        self.split = split

    # -- source handling ---------------------------------------------------

    def _clone_upstream(self, dest: Path) -> Path:
        repo = dest / "mlops-bench"
        subprocess.run(
            ["git", "clone", "--quiet", UPSTREAM_REPO_URL, str(repo)], check=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "checkout", "--quiet", self.source_ref],
            check=True,
        )
        return repo

    def _resolve_commit(self, root: Path) -> str:
        try:
            out = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            return out.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return self.source_ref

    # -- discovery ------------------------------------------------------------

    @staticmethod
    def discover(root: Path) -> list[UpstreamTask]:
        dataset = root / DATASET_SUBDIR
        if not dataset.is_dir():
            raise FileNotFoundError(f"MLOps-Bench dataset not found at {dataset}")
        tasks: list[UpstreamTask] = []
        for task_dir in sorted(dataset.glob("*/*/MLO-*")):
            if not task_dir.is_dir():
                continue
            problem = json.loads((task_dir / "problem.json").read_text())["problem"]
            metadata = json.loads((task_dir / "metadata.json").read_text())
            instance_id = metadata["instance_id"]
            if instance_id != task_dir.name:
                raise ValueError(
                    f"instance_id {instance_id!r} does not match directory {task_dir.name!r}"
                )
            tasks.append(UpstreamTask(instance_id, task_dir, problem, metadata))
        return tasks

    def _select(self, tasks: list[UpstreamTask]) -> list[UpstreamTask]:
        if self.split == "parity":
            tasks = parity_subset(tasks)
        if self.stages:
            tasks = [t for t in tasks if t.stage in self.stages]
        if self.task_ids:
            wanted = {tid.strip() for tid in self.task_ids}
            wanted_slugs = {slugify(w.split("__", 1)[-1].split("/")[-1]) for w in wanted}
            tasks = [
                t for t in tasks if t.instance_id in wanted or t.slug in wanted_slugs
            ]
            found = {t.instance_id for t in tasks} | {t.slug for t in tasks}
            missing = [
                w
                for w in wanted
                if w not in found
                and slugify(w.split("__", 1)[-1].split("/")[-1]) not in found
            ]
            if missing:
                raise ValueError(f"Unknown task id(s): {', '.join(sorted(missing))}")
        if self.limit is not None:
            tasks = tasks[: self.limit]
        return tasks

    # -- generation ----------------------------------------------------------

    @staticmethod
    def _render(template: str, values: dict[str, str]) -> str:
        for key, value in values.items():
            template = template.replace("{{" + key + "}}", value)
        leftover = re.findall(r"\{\{[A-Z_]+\}\}", template)
        if leftover:
            raise ValueError(f"Unrendered template placeholders: {leftover}")
        return template

    def _write_task(self, task: UpstreamTask, commit: str) -> Path:
        out = self.output_dir / task.slug
        if out.exists():
            if not self.overwrite:
                return out
            shutil.rmtree(out)

        f2p = int(task.metadata["f2p_test_count"])
        p2p = int(task.metadata["p2p_test_count"])
        difficulty = str(
            task.problem.get("metadata", {}).get("difficulty", "hard")
        ).lower()
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "hard"

        values = {
            "TASK_NAME": f"{TASK_NAME_ORG}/{TASK_NAME_PREFIX}{task.slug}",
            "STAGE_KEYWORD": STAGE_KEYWORDS.get(task.stage, task.stage.lower()),
            "DIFFICULTY": difficulty,
            "SOURCE_COMMIT": commit,
            "INSTANCE_ID": task.instance_id,
            "REPO_KEY": str(task.metadata["repo_key"]),
            "STAGE": task.stage,
            "F2P_COUNT": str(f2p),
            "P2P_COUNT": str(p2p),
            "PROBLEM_STATEMENT": render_instruction(task.problem).rstrip(),
        }

        (out / "environment").mkdir(parents=True)
        (out / "solution").mkdir()
        (out / "tests").mkdir()

        # task.toml + instruction.md
        for name in ("task.toml", "instruction.md"):
            text = (TEMPLATE_DIR / name).read_text()
            (out / name).write_text(self._render(text, values))

        # environment: pinned Dockerfile + hash-locked requirements + the
        # editable starting workspace only
        for name in ("Dockerfile", "requirements.txt"):
            shutil.copy2(TEMPLATE_DIR / "environment" / name, out / "environment")
        shutil.copytree(
            task.path / "repo", out / "environment" / "repo", ignore=IGNORED_COPY_PATTERNS
        )

        # solution: oracle patch
        shutil.copy2(TEMPLATE_DIR / "solution" / "solve.sh", out / "solution")
        shutil.copy2(task.path / "expected_changes.patch", out / "solution")

        # tests: separate verifier image (Dockerfile + the same hash-locked
        # requirements), F2P + P2P scoring suites and the verifier script
        shutil.copy2(TEMPLATE_DIR / "tests" / "Dockerfile", out / "tests")
        shutil.copy2(TEMPLATE_DIR / "environment" / "requirements.txt", out / "tests")
        for suite in ("test_f2p.py", "test_p2p.py"):
            shutil.copy2(task.path / "tests" / suite, out / "tests" / suite)
        test_sh = self._render((TEMPLATE_DIR / "tests" / "test.sh").read_text(), values)
        (out / "tests" / "test.sh").write_text(test_sh)

        for script in (out / "solution" / "solve.sh", out / "tests" / "test.sh"):
            script.chmod(0o755)
        return out

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mlops-bench-src-") as tmp:
            root = self.source_dir or self._clone_upstream(Path(tmp))
            commit = self._resolve_commit(root)
            tasks = self._select(self.discover(root))
            written = 0
            for task in tasks:
                existed = (self.output_dir / task.slug).exists()
                self._write_task(task, commit)
                if not existed or self.overwrite:
                    written += 1
            print(
                f"MLOps-Bench @ {commit[:12]}: {len(tasks)} task(s) selected, "
                f"{written} written to {self.output_dir}"
            )
