"""
RSI-Exam -> Harbor adapter.

RSI-Exam (https://github.com/aiming-lab/RSI-Exam) is authored natively in Harbor's
task format: every public task on the Hugging Face dataset ``RSI-Exam/RSI-Exam`` is a
complete Harbor task directory (``task.toml``, ``instruction.md``, ``environment/``,
``tests/`` and, for some tasks, ``solution/``), with the grader running in a separate,
sealed verifier container.

The adapter therefore does not re-author prompts, environments or graders. It:

1. Lists the task directories at a pinned dataset revision and selects the requested
   subset (``--task-ids`` / ``--limit``).
2. Downloads only the selected task directories (or reads them from ``--source-dir``).
3. Copies each task verbatim into ``output_dir/<task_id>/``.
4. Rewrites ``[task].name`` to a stable, registry-safe ``rsi-exam/<task_id>`` (upstream
   names are inconsistent, e.g. ``autoresearch-arena/...`` vs ``campaign-003/...``,
   and some differ from the directory name).
5. For tasks that ship no upstream reference solution, renders
   ``task-template/solution/solve.sh``: a no-op oracle that leaves the shipped
   baseline in place.

The autoresearch run protocol (prompt template, mounted program/task/budget files)
is applied at run time exactly as upstream does; see ``protocol/`` and the README.
"""

from __future__ import annotations

import logging
import re
import shutil
import stat
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_REPO_ID = "RSI-Exam/RSI-Exam"
# Pinned dataset revision (2026-09-07). Bump deliberately; task contents (and hence
# anchors / scores) are only comparable at the same revision.
DEFAULT_REVISION = "66f54935eaa576e27dae446f74c2ce17875c14da"

TASK_ORG = "rsi-exam"
REQUIRED_TASK_FILES = (
    "task.toml",
    "instruction.md",
    "environment/Dockerfile",
    "tests/test.sh",
)
# Top-level entries of the HF dataset repo that are not tasks.
NON_TASK_ENTRIES = {"assets", "README.md", "LICENSE", ".gitattributes"}

TEMPLATE_DIR = Path(__file__).parent / "task-template"
# Hidden staging dirs inside output_dir; never visible as tasks once a run ends.
STAGING_PREFIX = ".rsi-exam-staging."

SPLITS = ("full", "parity")
# Parity subset: the 22 public tasks that need no GPU/TPU and no task-side LLM API key,
# so both sides run on commodity Docker hosts (see README, parity section). Excluded:
# 8 NVIDIA-GPU tasks, 1 TPU v6e task, and 4 tasks that call a model from inside the task.
PARITY_TASKS = frozenset(
    {
        "bbo_noisy_continuous",
        "bbo_simopt_inventory",
        "bigann_filtered_vector_search",
        "citywide_signal_coordination",
        "cxr_ood_triage_policy",
        "device_iv_regime_extrapolation",
        "eda_gate_sizing",
        "feeder_phase_impedance_inversion",
        "finscope_dcf_valuation",
        "game2048_policy_search",
        "johnson1991_leighton_graph_coloring",
        "mbff_banking_placement",
        "multiview_dense_reconstruction",
        "pbmc_batch_correction",
        "qec_decoder_arena",
        "qlib_alpha_factor_icir",
        "roadef_glass_cutting",
        "robotap_switch_budget_candidate_routing_optimization",
        "tddn_contraction_planning",
        "tidal_friction_inverse",
        "trifinger_offline_rl_push_refined",
        "warehouse_robot_macro_routing",
    }
)

# Oracle-only fixes for upstream reference solutions that cannot run as shipped
# (found by running the oracle on both sides; see README "Notes & Caveats").
# They touch solution/ only: instruction.md, environment/ and tests/ stay byte-identical.
#
# Tasks whose upstream solve.sh is replaced by the baseline placeholder:
PLACEHOLDER_ORACLE_OVERRIDES = {
    # solve.sh defaults to ANCHOR=baseline, but solution/methods/baseline/ is not in the
    # release (only sota/, which needs chromobius/clorco and "only runs author-side"),
    # so it exits 1. The baseline anchor is the shipped environment/methods/main.
    "qec_decoder_arena",
}
# Shell appended to an upstream solve.sh (which runs with `set -euo pipefail`):
ORACLE_APPENDS = {
    # The sealed grader drops to an unprivileged uid before running the submission in a
    # root-owned copy of /app/methods/main, so the reference solver's build-on-demand
    # (`make` -> mkdir obj/) fails with "Permission denied" and scores 0. solver.py skips
    # `make` when the binary exists; agent and grader images share the same pinned base
    # image and toolchain, so build it here with the solver's own flags.
    "mbff_banking_placement": (
        "\n# --- appended by the Harbor rsi-exam adapter (oracle-only fix) ---\n"
        "# The grader runs the submission as an unprivileged user in a root-owned dir, so\n"
        "# the reference solver cannot build itself there. Prebuild with its own _build().\n"
        '(cd /app/methods/main && python3 -c "import solver; solver._build()")\n'
        'echo "[oracle] prebuilt reference binary for the unprivileged grader"\n'
    ),
}

_NAME_LINE_RE = re.compile(r"""^(\s*name\s*=\s*)(["']).*?\2(\s*(?:#.*)?)$""")
_HEADER_RE = re.compile(r"^\s*\[")


@dataclass
class GenerationSummary:
    generated: list[str]
    skipped_existing: list[str]
    invalid: list[str]
    placeholder_oracle: list[str]


def sanitize_task_id(raw: str) -> str:
    """Lowercase and replace anything outside ``[a-z0-9._-]`` with hyphens."""
    task_id = re.sub(r"[^a-z0-9._-]+", "-", raw.strip().lower()).strip("-._")
    if not task_id:
        raise ValueError(f"Cannot derive a task id from {raw!r}")
    return task_id


def rewrite_task_name(toml_text: str, new_name: str) -> str:
    """Replace ``name`` under ``[task]`` while leaving every other byte untouched."""
    lines = toml_text.splitlines(keepends=True)
    in_task = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if _HEADER_RE.match(line):
            in_task = stripped == "[task]"
            continue
        if in_task:
            m = _NAME_LINE_RE.match(line.rstrip("\r\n"))
            if m:
                newline = line[len(line.rstrip("\r\n")) :]
                lines[i] = f'{m.group(1)}"{new_name}"{m.group(3)}{newline}'
                return "".join(lines)
    raise ValueError("task.toml has no `name` under [task]")


class RSIExamAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "full",
        source_dir: Path | None = None,
        repo_id: str = DEFAULT_REPO_ID,
        revision: str = DEFAULT_REVISION,
        **kwargs,
    ):
        """
        Args:
            output_dir: Directory to write the generated tasks to.
            limit: Generate only the first N tasks (sorted by upstream directory name).
            overwrite: Overwrite existing task directories.
            task_ids: Only generate these tasks (upstream directory names or the
                sanitized ids used in the output).
            split: "full" (every task) or "parity" (the 22-task parity subset,
                ``PARITY_TASKS``). Combines with task_ids and limit.
            source_dir: Use a local copy of the dataset (e.g. the full 88-task suite
                obtained from the RSI-Exam authors) instead of downloading.
            repo_id: Hugging Face dataset repo id.
            revision: Hugging Face dataset revision (commit sha, tag or branch).
        """
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        if split not in SPLITS:
            raise ValueError(f"--split must be one of {', '.join(SPLITS)}")
        self.split = split
        self.repo_id = repo_id
        self.revision = revision

        if limit is not None and limit < 0:
            raise ValueError("--limit must be non-negative")

        if source_dir is not None:
            self.source_dir = Path(source_dir).expanduser().resolve()
            if not self.source_dir.is_dir():
                raise FileNotFoundError(f"--source-dir {self.source_dir} not found")
            available = sorted(
                p.name
                for p in self.source_dir.iterdir()
                if p.is_dir() and (p / "task.toml").is_file()
            )
        else:
            self.source_dir = None
            available = self._list_remote_tasks()

        self.selected = self._select(available)
        if self.source_dir is None and self.selected:
            self.source_dir = self._download(self.selected)

    # ------------------------------------------------------------------ loading

    def _list_remote_tasks(self) -> list[str]:
        from huggingface_hub import HfApi

        files = HfApi().list_repo_files(
            self.repo_id, repo_type="dataset", revision=self.revision
        )
        return sorted(
            {
                f.split("/", 1)[0]
                for f in files
                if f.count("/") == 1 and f.endswith("/task.toml")
            }
            - NON_TASK_ENTRIES
        )

    def _select(self, available: list[str]) -> list[str]:
        selected = list(available)
        if self.task_ids:
            by_key: dict[str, str] = {}
            for name in available:
                by_key[name] = name
                by_key[sanitize_task_id(name)] = name
            unknown = [t for t in self.task_ids if t not in by_key]
            if unknown:
                raise ValueError(
                    f"Unknown task id(s): {', '.join(unknown)}. "
                    f"Available: {', '.join(available)}"
                )
            wanted = {by_key[t] for t in self.task_ids}
            selected = [name for name in available if name in wanted]
        if self.split == "parity":
            missing = sorted(PARITY_TASKS - set(available))
            if missing:
                raise ValueError(
                    f"Parity task(s) not found in the source: {', '.join(missing)}"
                )
            selected = [name for name in selected if name in PARITY_TASKS]
        if self.limit is not None:
            selected = selected[: self.limit]
        return selected

    def _download(self, task_dirs: list[str]) -> Path:
        from huggingface_hub import snapshot_download

        logger.info(
            "Downloading %d task(s) from hf://datasets/%s@%s",
            len(task_dirs),
            self.repo_id,
            self.revision,
        )
        path = snapshot_download(
            self.repo_id,
            repo_type="dataset",
            revision=self.revision,
            allow_patterns=[f"{name}/**" for name in task_dirs],
        )
        return Path(path)

    # --------------------------------------------------------------- generation

    def _check_no_overlap(self) -> None:
        """Refuse to run when the output and source trees overlap.

        With overlap, ``--overwrite`` would delete a source task before copying it.
        """
        if self.source_dir is None:
            return
        src = self.source_dir.resolve()
        out = self.output_dir.expanduser().resolve()
        if out == src or src in out.parents or out in src.parents:
            raise ValueError(
                f"--output-dir ({out}) must not overlap the task source ({src}); "
                "write the generated tasks to a separate directory."
            )

    def _clean_stale_staging(self) -> None:
        """Remove staging/backup dirs left behind by a killed earlier run."""
        for stale in self.output_dir.glob(f"{STAGING_PREFIX}*"):
            if stale.is_dir():
                logger.warning("Removing stale staging directory %s", stale)
                shutil.rmtree(stale, ignore_errors=True)

    @staticmethod
    def _is_complete(task_dir: Path, task_id: str) -> bool:
        """True if ``task_dir`` looks like a fully generated task for ``task_id``."""
        required = (*REQUIRED_TASK_FILES, "solution/solve.sh")
        if not all((task_dir / f).is_file() for f in required):
            return False
        try:
            parsed = tomllib.loads((task_dir / "task.toml").read_text())
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            return False
        return parsed.get("task", {}).get("name") == f"{TASK_ORG}/{task_id}"

    def run(self) -> GenerationSummary:
        self._check_no_overlap()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._clean_stale_staging()
        summary = GenerationSummary([], [], [], [])
        assert self.source_dir is not None or not self.selected

        seen: dict[str, str] = {}
        for upstream_name in self.selected:
            task_id = sanitize_task_id(upstream_name)
            if task_id in seen:
                raise ValueError(
                    f"Task id collision: {upstream_name!r} and {seen[task_id]!r} "
                    f"both map to {task_id!r}"
                )
            seen[task_id] = upstream_name

            src = self.source_dir / upstream_name
            missing = [f for f in REQUIRED_TASK_FILES if not (src / f).is_file()]
            if missing:
                logger.warning(
                    "Skipping %s: missing %s", upstream_name, ", ".join(missing)
                )
                summary.invalid.append(upstream_name)
                continue

            dst = self.output_dir / task_id
            if dst.exists() and not self.overwrite:
                if self._is_complete(dst, task_id):
                    summary.skipped_existing.append(task_id)
                    continue
                logger.warning(
                    "Existing %s is incomplete or stale; regenerating it", dst
                )

            placeholder = self._generate_task(src, dst, task_id)
            summary.generated.append(task_id)
            if placeholder:
                summary.placeholder_oracle.append(task_id)

        logger.info(
            "Generated %d task(s) in %s (skipped existing: %d, invalid: %d, "
            "no upstream oracle: %d)",
            len(summary.generated),
            self.output_dir,
            len(summary.skipped_existing),
            len(summary.invalid),
            len(summary.placeholder_oracle),
        )
        if summary.placeholder_oracle:
            logger.info(
                "Tasks using the baseline (no-op) oracle: %s",
                ", ".join(summary.placeholder_oracle),
            )
        return summary

    def _generate_task(self, src: Path, dst: Path, task_id: str) -> bool:
        """Build one task in a staging dir, validate it, then publish it at ``dst``.

        ``dst`` is only ever a complete task: a failed or interrupted build leaves
        any existing ``dst`` untouched. Returns True if a placeholder oracle was
        written.
        """
        staging_root = Path(
            tempfile.mkdtemp(prefix=f"{STAGING_PREFIX}{task_id}.", dir=self.output_dir)
        )
        try:
            staged = staging_root / task_id
            placeholder = self._build_task(src, staged, task_id)
            if not self._is_complete(staged, task_id):
                raise RuntimeError(f"Generated task {task_id} failed validation")

            backup = staging_root / f"{task_id}.previous"
            if dst.exists():
                dst.rename(backup)
            try:
                staged.rename(dst)
            except BaseException:
                if backup.exists():
                    backup.rename(dst)
                raise
            return placeholder
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

    def _build_task(self, src: Path, dst: Path, task_id: str) -> bool:
        """Copy one upstream task into ``dst``; return True if a placeholder oracle was written."""
        # Resolve symlinks (the HF cache stores files as symlinks into blobs/).
        shutil.copytree(src, dst, symlinks=False)

        toml_path = dst / "task.toml"
        new_name = f"{TASK_ORG}/{task_id}"
        toml_path.write_text(rewrite_task_name(toml_path.read_text(), new_name))
        parsed = tomllib.loads(toml_path.read_text())
        if parsed.get("task", {}).get("name") != new_name:
            raise RuntimeError(f"Failed to set [task].name in {toml_path}")

        placeholder = False
        solve = dst / "solution" / "solve.sh"
        if task_id in PLACEHOLDER_ORACLE_OVERRIDES:
            solve.unlink(missing_ok=True)
        elif task_id in ORACLE_APPENDS:
            if not solve.is_file():
                raise RuntimeError(f"{task_id}: expected an upstream solution/solve.sh")
            solve.write_text(
                solve.read_text().rstrip("\n") + "\n" + ORACLE_APPENDS[task_id]
            )
        if not solve.is_file():
            solve.parent.mkdir(parents=True, exist_ok=True)
            template = (TEMPLATE_DIR / "solution" / "solve.sh").read_text()
            solve.write_text(template.replace("{task_id}", task_id))
            placeholder = True

        # HF does not preserve the executable bit.
        for script in (*dst.glob("solution/*.sh"), *dst.glob("tests/*.sh")):
            script.chmod(
                script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )
        return placeholder
