"""TraceTrial-Bench adapter for Harbor."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

TASK_TEMPLATE_DIR = Path(__file__).resolve().parent / "task-template"
VALID_SPLITS = ("standalone", "single-turn", "parity", "all")


class TraceTrialBenchAdapter:
    """Converts TraceTrial-Bench tasks into Harbor task directories."""

    TRACETRIAL_REPO = "https://github.com/TraceLite-AI/TraceTrial-Bench.git"
    TRACETRIAL_COMMIT = "4f94ae64a8e99ef8806200ffdcf496c9d7390f76"

    def __init__(
        self,
        output_dir: Path,
        *,
        source_dir: Path | None = None,
        split: str = "standalone",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.source_dir = Path(source_dir) if source_dir is not None else None
        if split not in VALID_SPLITS:
            raise ValueError(f"Unsupported split {split!r}; expected one of {VALID_SPLITS}")
        self.split = split
        self.template_dir = TASK_TEMPLATE_DIR

    def _materialize_source(self) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
        if self.source_dir is not None:
            if not (self.source_dir / "Task").is_dir():
                raise FileNotFoundError(f"Expected Task/ directory under {self.source_dir}")
            return self.source_dir, None

        tmp = tempfile.TemporaryDirectory(prefix="tracetrial_bench_src_")
        repo_path = Path(tmp.name) / "repo"
        logger.info("Fetching TraceTrial-Bench @ %s...", self.TRACETRIAL_COMMIT[:10])
        subprocess.run(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--sparse",
                "--no-checkout",
                self.TRACETRIAL_REPO,
                str(repo_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_path), "sparse-checkout", "set", "Task", "verifier"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", self.TRACETRIAL_COMMIT],
            check=True,
            capture_output=True,
            text=True,
        )
        return repo_path, tmp

    @staticmethod
    def _task_matches_split(task_dir: Path, meta: dict[str, Any], split: str) -> bool:
        if split == "all":
            return True
        if (task_dir / "simulator").exists():
            return False
        harness_meta = meta.get("harness") if isinstance(meta.get("harness"), dict) else {}
        subdim = str(harness_meta.get("subdimension") or "")
        # L4 and L5 require multi-principal child-subagent session transcripts not modeled by single-session ATIF
        if subdim in ("L4", "L5"):
            return False
        exec_json = task_dir / "runtime" / "execution.json"
        if exec_json.is_file():
            try:
                ed = json.loads(exec_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return False
            if ed.get("conversation") != "single_turn":
                return False
            if ed.get("requires"):
                return False
            return True
        input_mode = meta.get("input_mode")
        return input_mode in (None, "single_turn")

    def list_available_tasks(self) -> list[str]:
        src_root, tmp = self._materialize_source()
        try:
            task_ids: list[str] = []
            for task_yaml in sorted((src_root / "Task").glob("*/task.yaml")):
                meta = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
                if self._task_matches_split(task_yaml.parent, meta, self.split):
                    tid = str(meta.get("id") or task_yaml.parent.name)
                    task_ids.append(tid)
            return task_ids
        finally:
            if tmp is not None:
                tmp.cleanup()

    def _resolve_oracle_script(self, task_id: str) -> Path:
        oracles_dir = Path(__file__).resolve().parent / "oracles"
        custom = oracles_dir / f"{task_id.lower()}.sh"
        if custom.is_file():
            return custom
        ref_e8 = Path(__file__).resolve().parent / "e8_reference_solve.sh"
        if task_id == "E8-exit-code-masked-by-output-001" and ref_e8.is_file():
            return ref_e8
        return self.template_dir / "solution" / "solve.sh"

    def _generate_one_task(self, src_task_dir: Path, dst_task_dir: Path, overwrite: bool) -> bool:
        if dst_task_dir.exists():
            if not overwrite:
                logger.info("Skipping existing task directory: %s", dst_task_dir)
                return False
            shutil.rmtree(dst_task_dir)

        meta = yaml.safe_load((src_task_dir / "task.yaml").read_text(encoding="utf-8")) or {}
        task_id = str(meta.get("id") or src_task_dir.name)
        prompt_text = (src_task_dir / "prompt.md").read_text(encoding="utf-8")

        harness_meta = meta.get("harness") if isinstance(meta.get("harness"), dict) else {}
        dimension = str(harness_meta.get("dimension") or "unknown")
        subdimension = str(harness_meta.get("subdimension") or "unknown")
        intensity_meta = meta.get("intensity") if isinstance(meta.get("intensity"), dict) else {}
        difficulty = str(intensity_meta.get("level") or "L2").lower()
        scenario_meta = meta.get("scenario") if isinstance(meta.get("scenario"), dict) else {}
        category = str(scenario_meta.get("primary_subscenario") or subdimension)
        input_mode = str(meta.get("input_mode") or "single_turn")

        budget = meta.get("budget") if isinstance(meta.get("budget"), dict) else {}
        agent_timeout = int(budget.get("max_wall_time_sec") or 1800)
        verifier_timeout = 300

        keywords = sorted({"tracetrial-bench", "harness-reliability", dimension.lower(), subdimension.lower()})

        dst_env = dst_task_dir / "environment"
        dst_sol = dst_task_dir / "solution"
        dst_tests = dst_task_dir / "tests"
        for d in (dst_env, dst_sol, dst_tests):
            d.mkdir(parents=True, exist_ok=True)

        # 1. Render task.toml
        toml_tpl = (self.template_dir / "task.toml").read_text(encoding="utf-8")
        rendered_toml = toml_tpl.format(
            task_id_lower=task_id.lower(),
            task_id=task_id,
            source_commit=self.TRACETRIAL_COMMIT,
            keywords=json.dumps(keywords),
            dimension=dimension,
            subdimension=subdimension,
            difficulty=difficulty,
            category=category.replace('"', "'"),
            input_mode=input_mode,
            verifier_timeout_sec=verifier_timeout,
            agent_network_mode="public",
            agent_timeout_sec=agent_timeout,
        )
        (dst_task_dir / "task.toml").write_text(rendered_toml, encoding="utf-8")

        # 2. Render instruction.md (untouched benchmark prompt)
        (dst_task_dir / "instruction.md").write_text(prompt_text, encoding="utf-8")

        # 3. Stage ONLY agent-facing workspace/ into environment/workspace/ (never verifier/)
        src_ws = src_task_dir / "workspace"
        dst_ws = dst_env / "workspace"
        if src_ws.is_dir():
            shutil.copytree(src_ws, dst_ws)
        else:
            dst_ws.mkdir(parents=True, exist_ok=True)

        shutil.copy2(self.template_dir / "environment" / "Dockerfile", dst_env / "Dockerfile")
        cc_dst = dst_env / "collect_containment.py"
        shutil.copy2(self.template_dir / "environment" / "collect_containment.py", cc_dst)
        cc_dst.chmod(0o755)

        # 4. Stage solution/solve.sh and record its SHA-256 in tests/oracle_sha256.txt
        solve_dst = dst_sol / "solve.sh"
        oracle_src = self._resolve_oracle_script(task_id)
        shutil.copy2(oracle_src, solve_dst)
        solve_dst.chmod(0o755)
        oracle_sha = hashlib.sha256(solve_dst.read_bytes()).hexdigest()

        # 5. Stage separate verifier container context into tests/ (Harbor #3712)
        shutil.copy2(self.template_dir / "tests" / "Dockerfile", dst_tests / "Dockerfile")
        test_sh_dst = dst_tests / "test.sh"
        shutil.copy2(self.template_dir / "tests" / "test.sh", test_sh_dst)
        test_sh_dst.chmod(0o755)

        shutil.copy2(Path(__file__).resolve().parent / "atif_bridge.py", dst_tests / "atif_bridge.py")
        verify_py_dst = dst_tests / "verify.py"
        shutil.copy2(Path(__file__).resolve().parent / "verify_runner.py", verify_py_dst)
        verify_py_dst.chmod(0o755)
        (dst_tests / "oracle_sha256.txt").write_text(f"{oracle_sha}\n", encoding="utf-8")
        (dst_tests / "task_id.txt").write_text(f"{task_id}\n", encoding="utf-8")

        src_verifier = src_task_dir / "verifier"
        if src_verifier.is_dir():
            shutil.copytree(src_verifier, dst_tests / "verifier")
        if src_ws.is_dir():
            shutil.copytree(src_ws, dst_tests / "workspace")

        return True

    def run(
        self,
        *,
        task_ids: list[str] | None = None,
        limit: int | None = None,
        overwrite: bool = False,
    ) -> list[Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        src_root, tmp = self._materialize_source()
        try:
            task_map: dict[str, Path] = {}
            for task_yaml in sorted((src_root / "Task").glob("*/task.yaml")):
                meta = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
                tid = str(meta.get("id") or task_yaml.parent.name)
                if task_ids is not None or self._task_matches_split(task_yaml.parent, meta, self.split):
                    task_map[tid] = task_yaml.parent

            if task_ids is not None:
                missing = [t for t in task_ids if t not in task_map]
                if missing:
                    raise ValueError(f"Unknown TraceTrial-Bench task IDs: {missing}")
                selected = task_ids
            else:
                selected = list(task_map.keys())

            if limit is not None:
                selected = selected[: max(0, limit)]

            written: list[Path] = []
            for tid in selected:
                dst = self.output_dir / tid.lower()
                if self._generate_one_task(task_map[tid], dst, overwrite=overwrite):
                    written.append(dst)
            return written
        finally:
            if tmp is not None:
                tmp.cleanup()
