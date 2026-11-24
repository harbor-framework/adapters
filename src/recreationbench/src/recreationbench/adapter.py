"""Generate Harbor tasks for the Web split of RecreationBench.

Each task gives the agent a running reference web application (served on loopback
inside the task container) and a React scaffold, and scores the recreation with the
benchmark's own evaluator. The adapter reads three pinned upstream sources:

* the RecreationWorld framework (task index, prompt renderer) at ``RB_COMMIT``;
* the ``Qwen/RecreationBench`` dataset (hidden tests, VLM assertions) at
  ``DATASET_REVISION``;
* the same dataset revision again at image build time, for the reference site.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RB_REPO = "https://github.com/QwenLM/RecreationWorld.git"
RB_COMMIT = "ee01f2bd014a56f7e17850a5d42002c807b96beb"
DATASET = "Qwen/RecreationBench"
DATASET_REVISION = "284341f8fc3d6680dd57ca5414fed92a0fe33b95"
ORG = "qwen"
REFERENCE_PORT = 8100
TIMEOUT_MULTIPLIER = 10
# Judge endpoints the verifier may reach. Add others at run time with
# `harbor run --allow-verifier-host <host>` (see README).
JUDGE_HOSTS = (
    "dashscope.aliyuncs.com",
    "dashscope-intl.aliyuncs.com",
    "ai-gateway.vercel.sh",
    "openrouter.ai",
)
AUTHORS = (
    "Shuai Bai", "Jiayong Deng", "Sicheng Fan", "Yikun Fu", "Chang Gao", "Xuhao Hu",
    "Mianqiu Huang", "Yizhen Jiang", "Yuheng Jing", "Dehui Kong", "Keliang Li", "Ning Li",
    "Wanli Li", "Dayiheng Liu", "Dunjie Lu", "Changwei Luo", "Que Shen", "Zheyuan Wang",
    "Zijian Wang", "Jie Wu", "Gao Wu", "Zhihui Xie", "Rui Xie", "Haiyang Xu", "An Yang",
    "Jiakang Yuan", "Yanming Zhang", "Jiajun Zhang", "Xi Zhang", "Zhenru Zhang", "Zhuo Zhen",
    "Mingkang Zhu", "Bowen Zhou",
)  # fmt: skip
AUTHOR_EMAILS = {
    "Zhihui Xie": "xiezhihui.xzh@alibaba-inc.com",
    "Chang Gao": "gaochang.gao@alibaba-inc.com",
}

AGENT_NETWORK = {
    False: """# The original rollout runs in a network namespace whose only routes are the local
# reference and the model endpoint. Harbor adds the agent's model host to this
# allowlist automatically; pass --allow-agent-host for anything else.
network_mode = "allowlist"
allowed_hosts = [{agent_hosts}]""",
    True: """# Generated with --open-network: the rollout is NOT confined. The scorer's egress
# gate then caps a run that fetched external content, as upstream does when unisolated.
network_mode = "public"
""",
}
VERIFIER_NETWORK = {
    False: """# The verifier builds agent-authored code, so it only reaches judge endpoints. Pass
# --allow-verifier-host if your judge is served from another host.
network_mode = "allowlist"
allowed_hosts = [{judge_hosts}]""",
    True: """network_mode = "public"
""",
}

# Parity runs on a difficulty-stratified subset: a full run is 50 tasks of up to 20 hours each.
PARITY_SEED = 20261124
PARITY_COUNTS = {"easy": 3, "medium": 3, "hard": 4}

TEMPLATE_DIR = Path(__file__).parent / "task-template"
REFERENCE_SIZES = json.loads((Path(__file__).parent / "reference_sizes.json").read_text())
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "harbor-recreationbench"


@dataclass(frozen=True)
class WebTask:
    task_id: str
    difficulty: str

    @property
    def slug(self) -> str:
        return self.task_id.lower().replace(".", "-")

    @property
    def name(self) -> str:
        return f"{ORG}/recreationbench__{self.slug}"


class RecreationBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        rb_repo: Path | None = None,
        dataset_dir: Path | None = None,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        open_network: bool = False,
        split: str = "full",
        agent_hosts: list[str] | None = None,
        verifier_hosts: list[str] | None = None,
        **kwargs,
    ):
        """
        Args:
            output_dir: The directory to write the generated tasks to.
            limit: The maximum number of tasks to generate.
            overwrite: Whether to overwrite existing tasks.
            task_ids: Upstream task IDs (``rust-lang.org``) or task slugs (``rust-lang-org``).
            rb_repo: Existing RecreationWorld checkout at ``RB_COMMIT`` (cloned when omitted).
            dataset_dir: Existing copy of the dataset laid out as ``web/<task-id>/...``
                (the needed files are downloaded when omitted).
            cache_dir: Where the checkout and dataset files are cached.
            open_network: Generate tasks without the network allowlist, for container
                engines that cannot enforce one (for example Docker Desktop).
            split: ``full`` for all 50 tasks or ``parity`` for the parity subset.
            agent_hosts: Extra hosts the agent phase may reach (a model gateway behind the
                in-container proxy, for example).
            verifier_hosts: Extra hosts the verifier may reach (a judge endpoint).
        """
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.rb_repo = Path(rb_repo).expanduser() if rb_repo else None
        self.dataset_dir = Path(dataset_dir).expanduser() if dataset_dir else None
        self.cache_dir = Path(cache_dir).expanduser()
        self.open_network = open_network
        self.split = split
        self.agent_hosts = list(agent_hosts or [])
        self.verifier_hosts = list(verifier_hosts or [])

    def _checkout(self) -> Path:
        repo = self.rb_repo or self.cache_dir / f"RecreationWorld-{RB_COMMIT[:12]}"
        if not (repo / ".git").exists():
            repo.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "--quiet", RB_REPO, str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "checkout", "--quiet", RB_COMMIT], check=True)
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        if head != RB_COMMIT:
            raise RuntimeError(f"{repo} is at {head}, expected the pinned commit {RB_COMMIT}")
        return repo

    def _tasks(self, repo: Path) -> list[WebTask]:
        rows = [json.loads(line) for line in (repo / "tasks" / "web.jsonl").read_text().splitlines() if line.strip()]
        tasks = sorted((WebTask(row["instance_id"], row.get("difficulty", "medium")) for row in rows), key=lambda t: t.slug)
        if self.split == "parity":
            rng = random.Random(PARITY_SEED)
            picked = {
                task
                for difficulty, count in PARITY_COUNTS.items()
                for task in rng.sample([t for t in tasks if t.difficulty == difficulty], count)
            }
            tasks = [task for task in tasks if task in picked]
        if self.task_ids:
            wanted = {value.lower() for value in self.task_ids}
            selected = [task for task in tasks if {task.task_id.lower(), task.slug, task.name} & wanted]
            unknown = wanted - {name for task in selected for name in (task.task_id.lower(), task.slug, task.name)}
            if unknown:
                raise ValueError(f"unknown task ids: {sorted(unknown)}")
            tasks = selected
        return tasks[: self.limit] if self.limit is not None else tasks

    def _render_prompt(self, repo: Path) -> str:
        """The upstream prompt, rendered by upstream code for the URL the image serves."""
        sys.path.insert(0, str(repo / "scripts"))
        try:
            recreation_prompt = importlib.import_module("core.recreation_prompt")
            return recreation_prompt.render("web", site_url=f"http://localhost:{REFERENCE_PORT}")
        finally:
            sys.path.remove(str(repo / "scripts"))

    def _instance_dir(self, task: WebTask) -> Path:
        """Local ``web/<task-id>`` holding the hidden tests, VLM assertions and task.json."""
        if self.dataset_dir:
            return self.dataset_dir / "web" / task.task_id
        from huggingface_hub import snapshot_download

        root = self.cache_dir / f"dataset-{DATASET_REVISION[:12]}"
        prefix = f"web/{task.task_id}"
        snapshot_download(
            DATASET,
            repo_type="dataset",
            revision=DATASET_REVISION,
            local_dir=str(root),
            allow_patterns=[
                f"{prefix}/tests/**",
                f"{prefix}/vlm_assertions.json",
                f"{prefix}/reference/task.json",
                f"{prefix}/LICENSE",
            ],
        )
        return root / "web" / task.task_id

    def _write_task(self, task: WebTask, prompt: str) -> None:
        task_dir = self.output_dir / task.slug
        if task_dir.exists():
            if not self.overwrite:
                print(f"skip {task.slug} (exists; pass --overwrite to regenerate)")
                return
            shutil.rmtree(task_dir)

        instance = self._instance_dir(task)
        tests = instance / "tests"
        if not any(tests.rglob("*.spec.ts")):
            raise FileNotFoundError(f"no hidden tests found for {task.task_id} under {tests}")
        time_limit = int(json.loads((instance / "reference" / "task.json").read_text()).get("time_limit_seconds", 7200))

        shutil.copytree(TEMPLATE_DIR, task_dir)
        (task_dir / "instruction.md").write_text(prompt.rstrip("\n") + "\n")

        reference_mb = REFERENCE_SIZES.get(task.task_id, {}).get("reference_bytes", 0) / 1e6
        authors = "\n".join(
            "    { name = "
            + json.dumps(name)
            + (f", email = {json.dumps(AUTHOR_EMAILS[name])}" if name in AUTHOR_EMAILS else "")
            + " },"
            for name in AUTHORS
        )
        replacements = {
            "{agent_network}": AGENT_NETWORK[self.open_network],
            "{verifier_network}": VERIFIER_NETWORK[self.open_network],
            "{confined_default}": "0" if self.open_network else "1",
            "{task_name}": task.name,
            "{task_id}": task.task_id,
            "{authors}": authors,
            "{difficulty}": task.difficulty,
            "{dataset_revision}": DATASET_REVISION,
            "{rb_commit}": RB_COMMIT,
            "{time_limit}": str(time_limit),
            "{agent_timeout}": str(time_limit * TIMEOUT_MULTIPLIER),
            "{judge_hosts}": ", ".join(json.dumps(host) for host in [*JUDGE_HOSTS, *self.verifier_hosts]),
            "{agent_hosts}": ", ".join(json.dumps(host) for host in self.agent_hosts),
            # Base image and scaffold dependencies, plus the packed and the served copy of the site.
            "{storage_mb}": str(max(20480, 16384 + int(2.5 * reference_mb))),
        }
        for relative in ("task.toml", "environment/Dockerfile"):
            path = task_dir / relative
            text = path.read_text()
            for token, value in replacements.items():
                text = text.replace(token, value)
            path.write_text(text)

        shutil.copytree(tests, task_dir / "tests" / "task" / "tests")
        assertions = instance / "vlm_assertions.json"
        if assertions.is_file():
            shutil.copy2(assertions, task_dir / "tests" / "task" / "vlm_assertions.json")
        license_file = instance / "LICENSE"
        if license_file.is_file():
            shutil.copy2(license_file, task_dir / "LICENSE")

        # Deterministic, so regenerating the dataset does not churn task digests.
        token = hashlib.sha256(f"recreationbench-harbor-oracle:{DATASET_REVISION}:{task.task_id}".encode()).hexdigest()
        (task_dir / "solution" / "oracle_token").write_text(token + "\n")
        (task_dir / "tests" / "oracle_token.sha256").write_text(hashlib.sha256(token.encode()).hexdigest() + "\n")
        print(f"wrote {task.slug}")

    def run(self) -> None:
        repo = self._checkout()
        tasks = self._tasks(repo)
        prompt = self._render_prompt(repo)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for task in tasks:
            self._write_task(task, prompt)
        print(f"{len(tasks)} task(s) under {self.output_dir}")
