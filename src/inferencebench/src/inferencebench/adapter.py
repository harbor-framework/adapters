"""Generate Harbor tasks for InferenceBench from a pinned upstream checkout."""

import hashlib
import json
import logging
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

UPSTREAM_REPO = "https://github.com/aisa-group/InferenceBench.git"
UPSTREAM_COMMIT = "108ec747fab0bd92fd9de501f62157d074c50ed5"

TEMPLATE_DIR = Path(__file__).resolve().parent / "task-template"
DATA_DIR = Path(__file__).resolve().parent / "data"

MODELS = {"mistral-7b": "mistralai/Mistral-7B-Instruct-v0.3"}
# The commit of each model repository that the healthcheck downloads. The repository's main
# branch has pointed at this commit since 2025-12-03.
MODEL_REVISIONS = {
    "mistralai/Mistral-7B-Instruct-v0.3": "c170c708c41dac9275d15a8fff4eca08d52bab71",
}
PROMPT_AGENT = "claude"
SHARED_ENV = [
    "INFERENCE_BENCH_MAX_MODEL_LEN",
    "INFERENCE_BENCH_INPUT_TOKEN_MARGIN",
    "INFERENCE_BENCH_LONGBENCH_N",
    "INFERENCE_BENCH_QUALITY_TAU",
    "INFERENCE_BENCH_QUALITY_SEED",
    "INFERENCE_BENCH_QUALITY_MMLUPRO_N",
    "INFERENCE_BENCH_QUALITY_CONCURRENCY",
    "INFERENCE_BENCH_QUALITY_BASELINE_BACKEND",
]
EVAL_FILES = ["__init__.py", "runner.py", "quality_gate.py", "cache_samples.py"]
# What upstream uses to compute the PyTorch quality reference; see pytorch_reference.sh.
REFERENCE_FILES = [
    "__init__.py",
    "runner.py",
    "quality_gate.py",
    "precompute_all_baselines.py",
    "precompute_quality_baseline.py",
    "servers/__init__.py",
    "servers/transformers_openai_server.py",
]
# Only the image needs these; the verifier starts the server through the image's copy.
SERVER_FILES = ["bin/launch_supervised_server.sh", "bin/server_ready.py"]
REWARD_FILES = ["hpo_search_baselines.py", "precompute_all_baselines.py"]
JUDGE_FILES = ["judge.sh", "get_judge_prompt.py"]
# Where test.sh puts the judge's copy of the task directory and expects its verdicts.
JUDGE_HOME = "/var/lib/ib_judge"
# Where collect.sh writes the hand-off, and how many parts of handoff.py's PART_BYTES it may have.
HANDOFF_DIR = "/var/lib/ib_handoff"
HANDOFF_PARTS = 40
VLLM_VERSION = "0.11.0"
# sha256 of src.eval.inference.cache_samples output for the default sample counts.
SAMPLE_SHA256 = {
    "longbench": "7252f4609ba5ec73f04dfe85ec1a5479e70bd044cd9593fe65dbf2c70840ff59",
    "mmlu": "648e4ec1dbe5129818a3ef49918edbbe113b879cc902739dd48e1acf4dc0d0dc",
}


@dataclass(frozen=True)
class TaskSpec:
    scenario_key: str
    scenario: str
    model_key: str
    base_model: str
    agent_seed: str
    eval_seed: str

    @property
    def task_id(self) -> str:
        return (
            f"inferencebench-{self.scenario_key}-{self.model_key}"
            f"-{self.agent_seed}-{self.eval_seed}"
        )


def checkout_commit(path: Path) -> str:
    """Return the commit of the git checkout at path.

    The result ends in "-dirty" if the files differ from the commit, and is "unknown" if path is
    not the top level of a git checkout.
    """

    def git(*args: str) -> str | None:
        result = subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    top, head, status = git("rev-parse", "--show-toplevel"), git("rev-parse", "HEAD"), git("status", "--porcelain")
    if top is None or head is None or status is None or Path(top).resolve() != path.resolve():
        return "unknown"
    return head + ("-dirty" if status else "")


def fetch_upstream(cache_dir: Path) -> Path:
    """Check out the pinned upstream commit into cache_dir and return its path."""
    checkout = cache_dir / UPSTREAM_COMMIT
    if not (checkout / "src" / "run_task.sh").is_file():
        checkout.mkdir(parents=True, exist_ok=True)
        for command in (
            ["git", "init", "-q"],
            ["git", "fetch", "-q", "--depth", "1", UPSTREAM_REPO, UPSTREAM_COMMIT],
            ["git", "checkout", "-q", "--detach", "FETCH_HEAD"],
        ):
            subprocess.run(command, cwd=checkout, check=True)
    found = checkout_commit(checkout)
    if found != UPSTREAM_COMMIT:
        raise RuntimeError(
            f"{checkout} is not an unmodified checkout of {UPSTREAM_COMMIT} (found {found}); "
            "delete it and run the adapter again"
        )
    return checkout


def place(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


def parse_num_hours(value: str) -> str:
    """Accept what upstream's run_task.sh accepts: a decimal number of at least one second."""
    if not re.fullmatch(r"[0-9]+([.][0-9]+)?", value) or int(float(value) * 3600) < 1:
        raise ValueError(f"the time budget must be a number of hours of at least one second, got {value!r}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def handoff_artifacts() -> str:
    """The TOML array of the files that collect.sh may write; see handoff.py."""
    names = ["manifest.json", "complete", "collect.log", *(f"part.{index:03d}" for index in range(HANDOFF_PARTS))]
    return "[\n" + "".join(f'    "{HANDOFF_DIR}/{name}",\n' for name in names) + "]"


def render(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


class InferenceBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        upstream_dir: Path | None = None,
        cache_dir: Path | None = None,
        num_hours: str = "2",
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.num_hours = parse_num_hours(num_hours)
        self.upstream = (
            Path(upstream_dir)
            if upstream_dir
            else fetch_upstream(
                Path(cache_dir)
                if cache_dir
                else Path.home() / ".cache" / "harbor-inferencebench"
            )
        )
        # The commit that the tasks record. fetch_upstream checks the pinned one; another
        # checkout is recorded as what it is.
        self.upstream_commit = checkout_commit(self.upstream) if upstream_dir else UPSTREAM_COMMIT
        self.eval_dir = self.upstream / "src" / "eval"
        self.inference_dir = self.eval_dir / "inference"
        self.run_task = (self.upstream / "src" / "run_task.sh").read_text(encoding="utf-8")
        env_vars = (self.upstream / "src" / "commit_utils" / "set_env_vars.sh").read_text(
            encoding="utf-8"
        )
        raw = dict(re.findall(r'^set_default (\w+) "(.*)"$', env_vars, re.MULTILINE))
        self.settings = {
            key: re.sub(r"\$\{(\w+)\}", lambda m: raw.get(m[1], ""), value)
            for key, value in raw.items()
        }
        self.seed_pairs = re.search(r'^DEFAULT_SEED_PAIRS="(.*)"$', env_vars, re.MULTILINE)[1].split(",")

    def task_specs(self) -> list[TaskSpec]:
        scenarios = {
            path.name.split("_")[2]: path.name
            for path in sorted((self.eval_dir / "tasks").glob("inference_scenario_*"))
        }
        return [
            TaskSpec(key, scenario, model_key, model, *pair.split(":"))
            for key, scenario in scenarios.items()
            for model_key, model in MODELS.items()
            for pair in self.seed_pairs
        ]

    def selected_specs(self) -> list[TaskSpec]:
        specs = self.task_specs()
        if self.task_ids:
            known = {spec.task_id for spec in specs}
            unknown = sorted(set(self.task_ids) - known)
            if unknown:
                raise ValueError(f"Unknown task IDs: {', '.join(unknown)}")
            specs = [spec for spec in specs if spec.task_id in self.task_ids]
        return specs[: self.limit] if self.limit is not None else specs

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for spec in self.selected_specs():
            task_dir = self.output_dir / spec.task_id
            if task_dir.exists() and not self.overwrite:
                logger.info("Skipping %s: already exists", spec.task_id)
                continue
            # Build the task next to its final place, so that a failure leaves no partial
            # task behind for a later run to skip.
            partial = self.output_dir / f".{spec.task_id}.partial"
            shutil.rmtree(partial, ignore_errors=True)
            try:
                self.generate_task(spec, partial)
                if task_dir.exists():
                    shutil.rmtree(task_dir)
                partial.rename(task_dir)
            finally:
                shutil.rmtree(partial, ignore_errors=True)
            logger.info("Generated %s", task_dir)

    def generate_task(self, spec: TaskSpec, task_dir: Path) -> None:
        task_dir.mkdir(parents=True)
        self.write_task_toml(spec, task_dir)
        self.write_instruction(spec, task_dir)
        self.write_environment(spec, task_dir / "environment")
        self.write_solution(task_dir / "solution")
        self.write_tests(spec, task_dir / "tests")
        self.write_manifest(spec, task_dir)

    def heredoc(self, start: str, end: str = "PY") -> str:
        lines = self.run_task.splitlines()
        begin = next((i for i, line in enumerate(lines) if start in line), None)
        if begin is None:
            raise RuntimeError(f"src/run_task.sh: no heredoc after {start!r}")
        return "\n".join(lines[begin + 1 : lines.index(end, begin + 1)]) + "\n"

    def write_task_toml(self, spec: TaskSpec, task_dir: Path) -> None:
        shared_env = "\n".join(
            f"{key} = {json.dumps(self.settings[key])}" for key in SHARED_ENV
        )
        content = render(
            (TEMPLATE_DIR / "task.toml").read_text(encoding="utf-8"),
            {
                "task_id": spec.task_id,
                "scenario_key": spec.scenario_key.upper(),
                "scenario": spec.scenario,
                "base_model": spec.base_model,
                "agent_seed": spec.agent_seed,
                "eval_seed": spec.eval_seed,
                "num_hours": self.num_hours,
                "model_revision": MODEL_REVISIONS[spec.base_model],
                "upstream_commit": self.upstream_commit,
                "shared_env": shared_env,
                "handoff_artifacts": handoff_artifacts(),
                "agent_timeout_sec": str(float(self.num_hours) * 3600),
            },
        )
        (task_dir / "task.toml").write_text(content, encoding="utf-8")

    def write_instruction(self, spec: TaskSpec, task_dir: Path) -> None:
        # The prompt's only agent-specific clause (non-interactive mode, keep start_server.sh)
        # is kept for every agent, because a registered task has a single instruction.
        env = {
            "INFERENCE_BENCH_METRICS_PATH": "/home/agent/task/metrics_preview.json",
            "INFERENCE_BENCH_SERVER_URL": "http://127.0.0.1:8000",
        }
        prompt = subprocess.run(
            [
                sys.executable,
                str(self.eval_dir / "general" / "get_prompt.py"),
                "--base-model",
                spec.base_model,
                "--scenario-id",
                spec.scenario,
                "--num-hours",
                self.num_hours,
                "--agent",
                PROMPT_AGENT,
            ],
            cwd=self.upstream,
            env={**env, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        template = (TEMPLATE_DIR / "instruction.md").read_text(encoding="utf-8")
        (task_dir / "instruction.md").write_text(
            template.replace("{instruction}", prompt.strip()), encoding="utf-8"
        )

    def write_environment(self, spec: TaskSpec, env_dir: Path) -> None:
        env_dir.mkdir(parents=True)
        base = self.upstream / "src" / "harbor_adapter" / "template" / "Dockerfile"
        tail = render(
            (TEMPLATE_DIR / "environment" / "Dockerfile").read_text(encoding="utf-8"),
            {
                "agent_seed": spec.agent_seed,
                "quality_seed": self.settings["INFERENCE_BENCH_QUALITY_SEED"],
                "quality_n": self.settings["INFERENCE_BENCH_QUALITY_MMLUPRO_N"],
                "longbench_n": self.settings["INFERENCE_BENCH_LONGBENCH_N"],
                "longbench_sha256": SAMPLE_SHA256["longbench"],
                "mmlu_sha256": SAMPLE_SHA256["mmlu"],
            },
        )
        (env_dir / "Dockerfile").write_text(
            base.read_text(encoding="utf-8") + "\n" + tail, encoding="utf-8"
        )
        place(self.upstream / "containers" / "locks" / "inference.txt", env_dir / "constraints.txt")
        for name in ("collect.sh", "agent_processes.sh", "download_model.py", "handoff.py"):
            place(TEMPLATE_DIR / "environment" / name, env_dir / name)
        for name in EVAL_FILES + SERVER_FILES:
            place(self.inference_dir / name, env_dir / "inference_eval" / name)
        place(DATA_DIR / "quality", env_dir / "inference_eval" / "baselines" / "quality")

        task = env_dir / "home" / "task"
        for name in ("mission.txt", "benchmark.txt", "scenario.json"):
            place(self.eval_dir / "tasks" / spec.scenario / name, task / name)
        place(self.eval_dir / "tasks" / "_shared" / "task_context", task)
        (task / "evaluate.py").write_text(
            self.heredoc('task/evaluate.py" <<'), encoding="utf-8"
        )
        site = task / ".local" / "lib" / "python3.10" / "site-packages"
        (site / "pyairports").mkdir(parents=True)
        (site / "pyairports" / "__init__.py").write_text("", encoding="utf-8")
        (site / "pyairports" / "airports.py").write_text(
            self.heredoc('pyairports/airports.py" <<'), encoding="utf-8"
        )
        (site / "sitecustomize.py").write_text(
            self.heredoc('sitecustomize.py" <<'), encoding="utf-8"
        )
        timer = self.upstream / "src" / "harbor_adapter" / "template" / "timer.sh"
        (task / "timer.sh").write_text(
            timer.read_text(encoding="utf-8").replace(
                "NUM_SECONDS=", f"NUM_SECONDS={round(float(self.num_hours) * 3600)}"
            ),
            encoding="utf-8",
        )

    def torch_baseline_packages(self) -> list[str]:
        """Return the packages that upstream's torch baseline container installs under its lock."""
        definition = (self.upstream / "containers" / "inference_baselines_torch.def").read_text(
            encoding="utf-8"
        )
        install = re.search(r"uv pip install [^\n]*\\\n((?:[ \t]+\S+==\S+(?: \\)?\n)+)", definition)
        packages = install[1].replace("\\", "").split() if install else []
        if not {"torch", "transformers"} <= {package.split("==")[0] for package in packages}:
            raise RuntimeError("containers/inference_baselines_torch.def: no package list found")
        return packages

    def write_solution(self, solution_dir: Path) -> None:
        solution_dir.mkdir(parents=True)
        values = {
            "vllm_version": VLLM_VERSION,
            "torch_packages": " ".join(self.torch_baseline_packages()),
        }
        for name in ("solve.sh", "pytorch_reference.sh"):
            (solution_dir / name).write_text(
                render((TEMPLATE_DIR / "solution" / name).read_text(encoding="utf-8"), values),
                encoding="utf-8",
            )
            (solution_dir / name).chmod(0o755)
        place(TEMPLATE_DIR / "solution" / "pytorch_provenance.py", solution_dir / "pytorch_provenance.py")
        place(
            self.upstream / "src" / "starting_points" / "vllm_running" / "start_server.sh",
            solution_dir / "start_server.sh",
        )
        place(
            self.upstream / "containers" / "locks" / "inference_baselines_vllm.txt",
            solution_dir / "vllm-constraints.txt",
        )
        # Upstream's vLLM baseline runs with these shims; see solve.sh.
        place(
            self.inference_dir / "runtime_shims" / "sitecustomize.py",
            solution_dir / "vllm_runtime_shims.py",
        )
        place(
            self.upstream / "containers" / "locks" / "inference_baselines_torch.txt",
            solution_dir / "torch-constraints.txt",
        )
        for name in REFERENCE_FILES:
            place(self.inference_dir / name, solution_dir / "ib" / "src" / "eval" / "inference" / name)

    def write_tests(self, spec: TaskSpec, tests_dir: Path) -> None:
        tests_dir.mkdir(parents=True)
        for name in ("test.sh", "write_reward.py", "record_environment.py"):
            place(TEMPLATE_DIR / "tests" / name, tests_dir / name)
        (tests_dir / "test.sh").chmod(0o755)
        place(
            self.upstream / "src" / "harbor_adapter" / "template" / "tests" / "snapshot.py",
            tests_dir / "snapshot.py",
        )
        (tests_dir / "valid_eval_metrics.py").write_text(
            self.heredoc("<<'PY_METRICS'", "PY_METRICS"), encoding="utf-8"
        )
        ib = tests_dir / "ib"
        for name in EVAL_FILES + REWARD_FILES:
            place(self.inference_dir / name, ib / "src" / "eval" / "inference" / name)
        for name in ("evaluate.py", "scenario.json", "mission.txt", "benchmark.txt"):
            place(
                self.eval_dir / "tasks" / spec.scenario / name,
                ib / "src" / "eval" / "tasks" / spec.scenario / name,
            )
        judge = self.upstream / "src" / "disallowed_usage_judge"
        for name in JUDGE_FILES:
            place(judge / name, ib / "src" / "disallowed_usage_judge" / name)
        # The judge reviews a copy under JUDGE_HOME, because the agent's home directory stays
        # in this sandbox. Only the three paths in the prompt change.
        prompt = (judge / "prompt.txt").read_text(encoding="utf-8")
        if prompt.count("/home/agent") != 3:
            raise RuntimeError("judge prompt.txt: expected three /home/agent paths")
        (ib / "src" / "disallowed_usage_judge" / "prompt.txt").write_text(
            prompt.replace("/home/agent", JUDGE_HOME), encoding="utf-8"
        )

    def write_manifest(self, spec: TaskSpec, task_dir: Path) -> None:
        """Write what the task pins to tests/manifest.json; the verifier copies it to its record."""
        config = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
        quality_seed = self.settings["INFERENCE_BENCH_QUALITY_SEED"]
        pinned = [
            "environment/Dockerfile",
            "environment/constraints.txt",
            "solution/vllm-constraints.txt",
            "solution/torch-constraints.txt",
            *sorted(
                str(path.relative_to(task_dir))
                for path in (task_dir / "environment" / "inference_eval" / "baselines" / "quality").glob("*.json")
            ),
        ]
        manifest = {
            "task": spec.task_id,
            "scenario": spec.scenario,
            "base_model": spec.base_model,
            "model_revision": MODEL_REVISIONS[spec.base_model],
            "seeds": {
                "development": spec.agent_seed,
                "evaluation": spec.eval_seed,
                "quality": quality_seed,
            },
            "num_hours": self.num_hours,
            # Both sandboxes ask for this; environment.json says whether they got it.
            "gpus": config["environment"]["gpus"],
            "gpu_types": config["environment"]["gpu_types"],
            "timeouts_sec": {
                "build": config["environment"]["build_timeout_sec"],
                "healthcheck": config["environment"]["healthcheck"]["timeout_sec"],
                "agent": config["agent"]["timeout_sec"],
                "collect": config["verifier"]["collect"][0]["timeout_sec"],
                "verifier": config["verifier"]["timeout_sec"],
            },
            "upstream": {"repository": UPSTREAM_REPO, "commit": self.upstream_commit},
            "oracle": {"vllm": VLLM_VERSION, "pytorch_reference": self.torch_baseline_packages()},
            "samples_sha256": {
                f"longbench_v2/{quality_seed}_{self.settings['INFERENCE_BENCH_LONGBENCH_N']}/samples.jsonl": SAMPLE_SHA256["longbench"],
                f"mmlu_pro/{quality_seed}_{self.settings['INFERENCE_BENCH_QUALITY_MMLUPRO_N']}/samples.jsonl": SAMPLE_SHA256["mmlu"],
            },
            "files_sha256": {name: sha256(task_dir / name) for name in pinned},
        }
        (task_dir / "tests" / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
