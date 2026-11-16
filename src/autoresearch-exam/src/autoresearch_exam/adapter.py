"""AutoResearchExam adapter: convert ARE v1.0 tasks into ARE v1.1 Harbor tasks.

ARE v1.0 tasks run under a custom Harbor trial loop (the AutoResearchExam-Terminus
harness). v1.1 moves that loop into the task itself, so any Harbor agent can run it:

- A `grader` sidecar serves an MCP `submit` tool and scores each submission on the
  validation split. Its score is shown to the agent.
- A `test-grader` sidecar, on a private network the agent cannot reach, scores the
  same snapshot on the held-out test split.
- The final verifier reads the grader's ledger and reports AUARC over the run.

The task's own instruction, environment and grading code are reused unchanged.

Source: https://github.com/bespokelabsai/AutoResearchExam (tag v1.0)
"""

from __future__ import annotations

import logging
import shutil
import tomllib
from pathlib import Path

import tomli_w

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "task-template"

BUDGET_SEC = 86400  # research budget, also the AUARC horizon

# Paths (relative to tests/, or absolute) removed from the val grader's image. Its output
# reaches the agent, so it never holds the test split or the private grader.
VAL_STRIP_DEFAULT = ["hidden_data/final"]
VAL_STRIP = {
    "budgeted-covtype-dual-market-open": ["hidden_data/final", "prepare_hidden_data.py"],
    "ties-merging-clip-vitl14-eight-task-merge": ["hidden_data/final", "/opt/eval/final"],
    # Both splits are cut from one data file at grading time. The task's own grader
    # keeps it root-only while candidate code runs as the agent user, as in v1.0.
    "fast-adv-budgeted-pgd50-robust-cifar10": [],
    "sae-sparse-dict-nmse-frontier": [],
}

GRADER_GPU = """
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              # GPU 0 is shared with the agent (works on any 1-GPU host). On a host with a
              # spare GPU, export ARE_GRADER_GPU=1 to give grading its own, as in ARE 1.0.
              device_ids: ["${ARE_GRADER_GPU:-0}"]
              capabilities: [gpu]"""


class AutoResearchExamAdapter:
    def __init__(self, source_dir: Path, output_dir: Path):
        self.source_dir = source_dir
        self.output_dir = output_dir

    def task_ids(self) -> list[str]:
        return sorted(p.name for p in self.source_dir.iterdir() if (p / "task.toml").is_file())

    def run(self, task_ids: list[str], overwrite: bool = False) -> int:
        unknown = [t for t in task_ids if not (self.source_dir / t / "task.toml").is_file()]
        if unknown:
            raise SystemExit(f"unknown task(s): {', '.join(unknown)}")
        count = 0
        for task_id in task_ids:
            out = self.output_dir / task_id
            if out.exists():
                if not overwrite:
                    logger.info("skip %s (exists; pass --overwrite)", task_id)
                    continue
                shutil.rmtree(out)
            try:
                self.convert(self.source_dir / task_id, out)
            except BaseException:
                shutil.rmtree(out, ignore_errors=True)  # never leave a partial task behind
                raise
            count += 1
        return count

    def convert(self, src: Path, out: Path) -> None:
        cfg = tomllib.loads((src / "task.toml").read_text())
        env = cfg.get("environment", {})
        grader_env = {**env, **cfg.get("verifier", {}).get("environment", {})}
        grade_timeout = int(cfg.get("verifier", {}).get("timeout_sec", 1800))
        gpus = int(env.get("gpus", 0) or 0)
        (artifact,) = [a if isinstance(a, str) else a["source"] for a in cfg["artifacts"]]

        out.mkdir(parents=True)
        for item in src.iterdir():  # README.md, hints/, environment/
            if item.name in ("tests", "task.toml", "instruction.md"):
                continue
            if item.is_dir():
                shutil.copytree(item, out / item.name)
            else:
                shutil.copy2(item, out / item.name)

        # Both graders run the task's own grading code, from its original tests/ folder.
        ctx = out / "environment" / "are-grader-ctx"
        shutil.copytree(src / "tests", ctx)
        shutil.copytree(TEMPLATE_DIR / "environment" / "are-grader-ctx" / "are", ctx / "are")
        val_strip = VAL_STRIP.get(src.name, VAL_STRIP_DEFAULT)
        tail = (TEMPLATE_DIR / "environment" / "are-grader-ctx" / "Dockerfile.are").read_text()
        (ctx / "Dockerfile.are").write_text(
            (src / "tests" / "Dockerfile").read_text()
            + tail.format(val_strip=" ".join(p if p.startswith("/") else f"/tests/{p}" for p in val_strip))
        )
        # Keep the grader context, which holds hidden data, out of the agent's build context.
        shutil.copy(TEMPLATE_DIR / "environment" / ".dockerignore", out / "environment" / ".dockerignore")

        compose = (TEMPLATE_DIR / "environment" / "docker-compose.yaml").read_text()
        (out / "environment" / "docker-compose.yaml").write_text(compose.format(
            budget=BUDGET_SEC,
            artifact=artifact,
            grade_timeout=grade_timeout,
            grader_cpus=f"{float(grader_env.get('cpus', 2)):g}",
            grader_mem=int(grader_env.get("memory_mb", 4096)),
            grader_gpu=GRADER_GPU if gpus else "",
        ))

        shutil.copytree(TEMPLATE_DIR / "tests", out / "tests")
        shutil.copytree(TEMPLATE_DIR / "solution", out / "solution")

        protocol = (TEMPLATE_DIR / "instruction.md").read_text()
        instruction = (src / "instruction.md").read_text().rstrip("\n")
        (out / "instruction.md").write_text(protocol.replace("{{ instruction }}", instruction))

        (out / "task.toml").write_text(tomli_w.dumps(self.task_toml(src.name, cfg, grade_timeout)))

    @staticmethod
    def task_toml(task_id: str, cfg: dict, grade_timeout: int) -> dict:
        are = tomllib.loads((TEMPLATE_DIR / "task.toml").read_text())

        are["task"]["name"] = are["task"]["name"].format(task_id=task_id)
        task = {**cfg["task"], **are["task"]}
        metadata = {**cfg.get("metadata", {}), **are["metadata"], "budget_seconds": BUDGET_SEC}
        verifier = are["verifier"]
        # The test queue can lag the val queue; leave room for two full test grades.
        verifier["collect"][0]["timeout_sec"] = max(3600.0, 2.0 * grade_timeout)

        agent = {**cfg.get("agent", {}), "timeout_sec": float(BUDGET_SEC)}
        if agent.get("network_mode") == "allowlist" and "grader" not in agent["allowed_hosts"]:
            agent["allowed_hosts"] = [*agent["allowed_hosts"], "grader"]

        env = {k: v for k, v in cfg.get("environment", {}).items() if k not in ("allowed_hosts", "mcp_servers")}
        env.update(are["environment"])

        out = {"schema_version": cfg["schema_version"]} if "schema_version" in cfg else {}
        out.update(artifacts=are["artifacts"], task=task, metadata=metadata, verifier=verifier,
                   agent=agent, environment=env)
        return out
