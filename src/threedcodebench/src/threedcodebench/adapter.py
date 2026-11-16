"""3DCodeBench -> Harbor adapter.

Converts the 212 text-to-3D instances of 3DCodeBench (one canonical seed per
Infinigen category, ``<Category>_seed0``) into Harbor tasks that reproduce the
upstream coding-agent setting (``tasks/coding_agent/run_*_agent.sh``): the agent
gets the category caption, writes a Blender 5.0 Python script, may run Blender
to test it, and is scored by re-executing that script independently.

Upstream sources are pinned:
  * code:  https://github.com/gaoypeng/3dcodebench @ UPSTREAM_COMMIT
  * data:  https://huggingface.co/datasets/YipengGao/3DCode (folder 3DCodeBench/) @ HF_REVISION
"""

from __future__ import annotations

import re
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

UPSTREAM_REPO = "https://github.com/gaoypeng/3dcodebench.git"
UPSTREAM_COMMIT = "42c7780ed3fcbd466f17f058f62e7996233777f7"
HF_REPO_ID = "YipengGao/3DCode"
HF_REVISION = "b9ebb354234efcec00573e31917a07fe11603742"
HF_SUBDIR = "3DCodeBench"

TASK_ORG = "3dcodebench"
# Upstream run_{claude,codex}_agent.sh default TIME_LIMIT (seconds); it is both
# the wall-clock cap and the "Hard time budget" stated in the prompt.
AGENT_TIME_LIMIT_SEC = 600

# Upstream scoring helpers, copied byte-for-byte into each task's tests/upstream/.
UPSTREAM_TEST_FILES = (
    "core/render.py",
    "core/export_glb.py",
    "metrics/shape_chamfer.py",
)

# Minimal fixes for reference scripts that do not run as published.
# Each entry is (old, new); `old` must occur exactly once. Documented in README.
REFERENCE_PATCHES: dict[str, list[tuple[str, str]]] = {
    # n_ep is computed from a geometry-dependent candidate count, but the
    # endpoint indices below it are hardcoded (5 of them). Whenever the count is
    # not 5, csr_matrix() gets index/data arrays of different lengths and the
    # script raises ValueError. Pin n_ep to the hardcoded endpoint count.
    "FanCoral_seed0": [
        (
            "endpoints = np.array([572, 248, 14, 253, 26])\n",
            "endpoints = np.array([572, 248, 14, 253, 26])\n"
            "n_ep = len(endpoints)  # harbor adapter fix, see adapter README\n",
        )
    ],
}

TEMPLATE_DIR = Path(__file__).parent / "task-template"
TEMPLATED_FILES = (
    "task.toml",
    "instruction.md",
    "solution/solve.sh",
    "tests/test.sh",
)


def to_task_id(instance: str) -> str:
    """Registry-safe, stable task id: ``ArmChair_seed0`` -> ``armchair-seed0``."""
    return re.sub(r"[^a-z0-9]+", "-", instance.lower()).strip("-")


@dataclass(frozen=True)
class Instance:
    name: str  # upstream id, e.g. ArmChair_seed0
    category: str  # e.g. ArmChair
    description: str  # prompt_description.txt (what the coding agent sees)
    reference_script: str  # ground-truth Blender 5.0 factory script

    @property
    def task_id(self) -> str:
        return to_task_id(self.name)


class ThreeDCodeBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        benchmark_dir: Path | None = None,
        upstream_dir: Path | None = None,
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.benchmark_dir = Path(benchmark_dir) if benchmark_dir else None
        self.upstream_dir = Path(upstream_dir) if upstream_dir else None

    # ------------------------------------------------------------------ sources
    @staticmethod
    def _download_benchmark(dest: Path) -> Path:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=HF_REPO_ID,
            repo_type="dataset",
            revision=HF_REVISION,
            allow_patterns=[f"{HF_SUBDIR}/*"],
            local_dir=dest,
        )
        return dest / HF_SUBDIR

    @staticmethod
    def _clone_upstream(dest: Path) -> Path:
        dest.mkdir(parents=True, exist_ok=True)
        run = lambda *a: subprocess.run(["git", "-C", str(dest), *a], check=True, capture_output=True)  # noqa: E731
        run("init", "-q")
        run("remote", "add", "origin", UPSTREAM_REPO)
        run("fetch", "-q", "--depth", "1", "origin", UPSTREAM_COMMIT)
        run("checkout", "-q", "FETCH_HEAD")
        return dest

    @staticmethod
    def _load_instances(bench: Path) -> list[Instance]:
        instances = []
        for d in sorted(p for p in bench.iterdir() if p.is_dir()):
            script = d / f"{d.name}.py"
            desc = d / "prompt_description.txt"
            if not (script.is_file() and desc.is_file()):
                raise FileNotFoundError(f"Incomplete benchmark instance: {d}")
            instances.append(
                Instance(
                    name=d.name,
                    category=d.name.rsplit("_seed", 1)[0],
                    # upstream: DESC=$(cat prompt_description.txt) strips trailing newlines
                    description=desc.read_text(encoding="utf-8").rstrip("\n"),
                    reference_script=script.read_text(encoding="utf-8"),
                )
            )
        if not instances:
            raise RuntimeError(f"No instances found under {bench}")
        return instances

    def _select(self, instances: list[Instance]) -> list[Instance]:
        if self.task_ids:
            wanted = set(self.task_ids)
            known = {i.name for i in instances} | {i.task_id for i in instances}
            unknown = sorted(wanted - known)
            if unknown:
                raise SystemExit(f"Unknown task ids: {', '.join(unknown)}")
            instances = [i for i in instances if i.name in wanted or i.task_id in wanted]
        if self.limit is not None:
            instances = instances[: self.limit]
        return instances

    # ------------------------------------------------------------------ writing
    @staticmethod
    def _patched_reference(inst: Instance) -> str:
        code = inst.reference_script
        for old, new in REFERENCE_PATCHES.get(inst.name, []):
            if code.count(old) != 1:
                raise RuntimeError(f"Patch for {inst.name} no longer applies cleanly")
            code = code.replace(old, new)
        return code

    def _write_task(self, inst: Instance, upstream: Path) -> bool:
        out = self.output_dir / inst.task_id
        if out.exists():
            if not self.overwrite:
                return False
            shutil.rmtree(out)
        shutil.copytree(TEMPLATE_DIR, out)

        values = {
            "{{TASK_ORG}}": TASK_ORG,
            "{{TASK_ID}}": inst.task_id,
            "{{INSTANCE}}": inst.name,
            "{{CATEGORY}}": inst.category,
            "{{DESCRIPTION}}": inst.description,
            "{{TIME_LIMIT}}": str(AGENT_TIME_LIMIT_SEC),
        }
        for rel in TEMPLATED_FILES:
            path = out / rel
            text = path.read_text(encoding="utf-8")
            for key, val in values.items():
                text = text.replace(key, val)
            path.write_text(text, encoding="utf-8")

        reference = self._patched_reference(inst)
        (out / "solution" / f"{inst.name}.py").write_text(reference, encoding="utf-8")
        ref_dir = out / "tests" / "reference"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / f"{inst.name}.py").write_text(reference, encoding="utf-8")

        up_dir = out / "tests" / "upstream"
        up_dir.mkdir(parents=True, exist_ok=True)
        for rel in UPSTREAM_TEST_FILES:
            shutil.copy2(upstream / rel, up_dir / Path(rel).name)

        for script in out.rglob("*.sh"):
            script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return True

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="threedcodebench-") as tmp:
            tmp_path = Path(tmp)
            bench = self.benchmark_dir or self._download_benchmark(tmp_path / "hf")
            upstream = self.upstream_dir or self._clone_upstream(tmp_path / "upstream")
            instances = self._select(self._load_instances(bench))
            written = sum(self._write_task(inst, upstream) for inst in instances)
        skipped = len(instances) - written
        print(
            f"Wrote {written} task(s) to {self.output_dir}"
            + (f" ({skipped} existing skipped; use --overwrite)" if skipped else "")
        )
