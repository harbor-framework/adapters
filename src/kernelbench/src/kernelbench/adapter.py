"""Generate Harbor tasks for KernelBench and KernelBench-Verified.

Both variants cover the same 250 KernelBench L1-L3 problems and give the agent
the same kind of task (write a faster CUDA ``ModelNew``). They differ in the
prompt and in the grader, each taken unchanged from its upstream repo:

  kernelbench           ScalingIntelligence/KernelBench: one-shot CUDA prompt
                        from prompts.toml, ``kernelbench.eval`` grading
                        (5 seeded correctness trials, atol=rtol=1e-4, speedup
                        vs. PyTorch fp32 eager).
  kernelbench-verified  facebookresearch/kernel_bench_verified: its own prompt
                        template, input-stripped prompts for the 4 known
                        reward-hacked problems, correctness on 4 hidden input
                        distributions (atol=rtol=1e-3), speedup vs. PyTorch with
                        TF32 enabled, peak memory.
"""

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

KB_REPO = "https://github.com/ScalingIntelligence/KernelBench.git"
KB_REV = "423217d9fda91e0c2d67e4a43bf62f96f6d104f1"
KBV_REPO = "https://github.com/facebookresearch/kernel_bench_verified.git"
KBV_REV = "3fdf6fec7372a4d0cb682635f00e7bdcbc55d50e"

VARIANTS = ("kernelbench", "kernelbench-verified")
TEMPLATE = Path(__file__).parent / "task-template"

# Degenerate problems KBV removes from its leaderboard (output is constant zero).
KBV_EXCLUDED = {(2, 23), (2, 80), (2, 83)}
# Unscoreable in both: L2-66 applies training-mode dropout, so even the PyTorch
# reference fails its own correctness check.
BOTH_EXCLUDED = {(2, 66)}

# From each benchmark's BibTeX citation.
AUTHORS = {
    "kernelbench": [
        "Anne Ouyang",
        "Simon Guo",
        "Simran Arora",
        "Alex L. Zhang",
        "William Hu",
        "Christopher Ré",
        "Azalia Mirhoseini",
    ],
    "kernelbench-verified": [
        "Yunxiang Zhang",
        "Ping Yu",
        "Jianyu Wang",
        "Max (Xiangjun) Fan",
        "Julian Reed",
        "Azalia Mirhoseini",
        "Will Su",
    ],
}
AGENT_TIMEOUT_MIN = {1: 60, 2: 60, 3: 90}

CHECK_NOTE = (
    "- `python /workspace/check.py` compiles your solution and compares it against the "
    "reference on the visible inputs (correctness + a rough timing). It is a convenience "
    "only; the final grader uses its own inputs and timing."
)
BLIND_NOTE = (
    "- For this problem the test inputs are intentionally withheld (only the `Model` class "
    "is shown; see the shapes in its docstring). Write your own tests; there is no `check.py`."
)
VERIFIED_NOTE = (
    "\n- Grading is strict: correctness is checked on several hidden input distributions "
    "(different magnitudes and signs), and speed is measured against PyTorch with TF32 "
    "Tensor Cores enabled. Kernels that special-case the visible inputs or skip work will fail."
)


@dataclass
class Problem:
    level: int
    pid: int
    file_name: str
    ref_src: str  # reference architecture the grader uses
    prompt_src: str  # what the agent sees (input-stripped for KBV hacked pids)

    @property
    def blind(self) -> bool:
        return self.prompt_src != self.ref_src


def _checkout(repo: str, rev: str, dest: Path) -> Path:
    if not (dest / ".git").exists():
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", str(dest)], check=True)
    head = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != rev:
        subprocess.run(
            ["git", "-C", str(dest), "fetch", "-q", "--depth", "1", repo, rev],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(dest), "checkout", "-q", "FETCH_HEAD"], check=True
        )
    return dest


def _exec_module(path: Path, strip_import: str, helpers: dict) -> dict:
    """Run an upstream module with its heavy package import replaced by `helpers`.

    The upstream packages import torch / LLM SDKs at package level; the prompt code
    itself only needs a few file helpers, so we inject those instead.
    """
    src = path.read_text()
    assert strip_import in src, f"{path}: expected `{strip_import}`"
    ns = {"__file__": str(path), "__name__": f"_upstream_{path.stem}", **helpers}
    # Trusted, pinned upstream source; see docstring.
    exec(compile(src.replace(strip_import, ""), str(path), "exec"), ns)  # noqa: S102
    return ns


def _read_file(p) -> str:
    return Path(p).read_text()


def load_kb_prompt(kb_root: Path):
    pkg = kb_root / "src" / "kernelbench"

    def resource(rel: str) -> str:
        return str(pkg / rel)

    def resolve(rel: str) -> str:
        return rel if Path(rel).is_absolute() else str(kb_root / rel)

    ns = _exec_module(
        pkg / "prompt_constructor_toml.py",
        "from kernelbench.utils import read_file, get_package_resource_path, resolve_path, REPO_TOP_PATH",
        {
            "read_file": _read_file,
            "get_package_resource_path": resource,
            "resolve_path": resolve,
            "REPO_TOP_PATH": str(kb_root),
        },
    )
    fn = ns["get_prompt_for_backend"]
    return lambda src: fn(src, backend="cuda", option="one_shot", precision="fp32")


def load_kbv_prompt(kbv_root: Path):
    ns = _exec_module(
        kbv_root / "src" / "prompt_constructor.py",
        "from .utils import read_file",
        {"read_file": _read_file},
    )
    fn = ns["prompt_generate_custom_cuda_from_prompt_template"]
    return (
        lambda src: fn(src, precision="fp32"),
        ns["STRIP_TEST_CONFIG_PIDS"],
        ns["strip_test_config"],
    )


def slug(file_name: str) -> str:
    s = "_".join(file_name.removesuffix(".py").split("_")[1:])
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class KernelBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        variant: str = "kernelbench",
        levels: list[int] | None = None,
        source_dir: Path | None = None,
        **kwargs,
    ):
        assert variant in VARIANTS, variant
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = set(task_ids) if task_ids else None
        self.variant = variant
        self.levels = levels or [1, 2, 3]
        self.source_dir = Path(
            source_dir or Path.home() / ".cache" / "harbor-kernelbench"
        )
        self.kb_root = _checkout(KB_REPO, KB_REV, self.source_dir / "KernelBench")
        self.kbv_root = _checkout(
            KBV_REPO, KBV_REV, self.source_dir / "kernel_bench_verified"
        )

    def task_dir_name(self, p: Problem) -> str:
        return f"{self.variant}-l{p.level}-{p.pid:03d}-{slug(p.file_name)}"

    def task_id(self, p: Problem) -> str:
        return f"{self.variant}-l{p.level}-{p.pid:03d}"

    def problems(self):
        verified = self.variant == "kernelbench-verified"
        if verified:
            _, strip_pids, strip = load_kbv_prompt(self.kbv_root)
        for level in self.levels:
            src_root = (
                (self.kbv_root if verified else self.kb_root)
                / "KernelBench"
                / f"level{level}"
            )
            for f in sorted(
                src_root.glob("*.py"), key=lambda p: int(p.name.split("_")[0])
            ):
                pid = int(f.name.split("_")[0])
                if (level, pid) in BOTH_EXCLUDED or (
                    verified and (level, pid) in KBV_EXCLUDED
                ):
                    continue
                ref = f.read_text()
                prompt_src = (
                    strip(ref) if verified and (level, pid) in strip_pids else ref
                )
                yield Problem(level, pid, f.name, ref, prompt_src)

    def run(self) -> None:
        if self.variant == "kernelbench":
            prompt = load_kb_prompt(self.kb_root)
        else:
            prompt = load_kbv_prompt(self.kbv_root)[0]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        for p in self.problems():
            if self.task_ids and self.task_id(p) not in self.task_ids:
                continue
            if self.limit is not None and n >= self.limit:
                break
            out = self.output_dir / self.task_dir_name(p)
            if out.exists():
                if not self.overwrite:
                    n += 1
                    continue
                shutil.rmtree(out)
            self.write_task(p, prompt(p.prompt_src), out)
            n += 1
        print(f"{self.variant}: {n} tasks -> {self.output_dir}")

    def write_task(self, p: Problem, prompt: str, out: Path) -> None:
        verified = self.variant == "kernelbench-verified"
        shutil.copytree(TEMPLATE, out)
        env, tests, sol = out / "environment", out / "tests", out / "solution"

        instruction = (
            (TEMPLATE / "instruction.md")
            .read_text()
            .format(
                prompt=prompt.rstrip(),
                check_note=BLIND_NOTE if p.blind else CHECK_NOTE,
                verified_note=VERIFIED_NOTE if verified else "",
            )
        )
        (out / "instruction.md").write_text(instruction)

        authors = ", ".join(f'{{ name = "{n}" }}' for n in AUTHORS[self.variant])
        (out / "task.toml").write_text(
            (TEMPLATE / "task.toml")
            .read_text()
            .format(
                name=f"kernelbench/{self.task_dir_name(p)}",
                authors=authors,
                variant=self.variant,
                level=p.level,
                pid=p.pid,
                problem_name=p.file_name.removesuffix(".py"),
                agent_timeout=AGENT_TIMEOUT_MIN[p.level] * 60,
            )
        )

        # Agent workspace: the visible reference (+ local self-check).
        (env / "reference.py").write_text(p.prompt_src)
        copies = ["reference.py"]
        if p.blind:
            (env / "check.py").unlink()
        else:
            copies.append("check.py")
        (env / "Dockerfile").write_text(
            (env / "Dockerfile")
            .read_text()
            .format(
                kb_rev=KB_REV,
                kbv_rev=KBV_REV,
                kb_repo=KB_REPO,
                kbv_repo=KBV_REPO,
                copies=" ".join(copies),
            )
        )

        # Grader side: full reference and, for KBV, the hidden inputs.
        (tests / "reference.py").write_text(p.ref_src)
        if verified:
            hidden = (
                self.kbv_root
                / "hidden_tests"
                / f"level{p.level}"
                / f"{p.pid}_hidden.py"
            )
            src = re.sub(
                r"^_PROB_PATH = .*$",
                "_PROB_PATH = '/tests/reference.py'",
                hidden.read_text(),
                count=1,
                flags=re.MULTILINE,
            )
            (tests / "hidden.py").write_text(src)

        # Oracle: the PyTorch reference itself wrapped as ModelNew.
        (sol / "reference.py").write_text(p.ref_src)
        for f in (tests / "test.sh", sol / "solve.sh"):
            f.chmod(0o755)
