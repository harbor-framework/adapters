"""Generate Harbor tasks from AgentDojo (ethz-spylab/agentdojo).

Two splits, matching the two numbers upstream reports for a model:
- `user`: every user task without injections (utility).
- `attack`: every (user task, injection task) pair of a suite, with the
  injections the chosen attack places in the environment (utility under attack
  and security, i.e. whether the injection task succeeded).
"""

import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from agentdojo.agent_pipeline.agent_pipeline import load_system_message
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.task_suite.load_suites import get_suites

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "task-template"

DEFAULT_BENCHMARK_VERSION = "v1.2.2"
# `important_instructions` (the paper's main attack) names the victim model,
# which is unknown when tasks are generated; this upstream variant uses the
# generic "the AI language model" instead.
DEFAULT_ATTACK = "important_instructions_no_model_name"
# Pipeline name handed to attacks that look up a model name; agentdojo's own
# default model. Only attacks that address the model by name are affected.
DEFAULT_ATTACK_TARGET_MODEL = "gpt-4o-2024-05-13"
SPLITS = ("user", "attack")


class _AttackTarget(BasePipelineElement):
    """Stand-in for the attacked pipeline; attacks only read its name."""

    def __init__(self, name: str) -> None:
        self.name = name

    def query(self, *args, **kwargs):
        raise NotImplementedError


@dataclass
class TaskRecord:
    suite_name: str
    user_task_id: str
    injection_task_id: str | None
    injections: dict[str, str]

    @property
    def split(self) -> str:
        return "user" if self.injection_task_id is None else "attack"

    @property
    def local_id(self) -> str:
        parts = [self.suite_name, self.user_task_id]
        if self.injection_task_id is not None:
            parts.append(self.injection_task_id)
        return "-".join(parts)


def _task_number(task_id: str) -> int:
    return int(re.search(r"(\d+)$", task_id).group(1))


class AgentDojoAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "all",
        suites: list[str] | None = None,
        benchmark_version: str = DEFAULT_BENCHMARK_VERSION,
        attack: str = DEFAULT_ATTACK,
        attack_target_model: str = DEFAULT_ATTACK_TARGET_MODEL,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = set(task_ids) if task_ids else None
        self.splits = SPLITS if split == "all" else (split,)
        self.suite_names = suites
        self.benchmark_version = benchmark_version
        self.attack_name = attack
        self.attack_target_model = attack_target_model
        self.suites = get_suites(benchmark_version)
        self.system_message = load_system_message(None)

    def _records(self) -> list[TaskRecord]:
        records = []
        for suite_name, suite in self.suites.items():
            if self.suite_names and suite_name not in self.suite_names:
                continue
            attack = load_attack(self.attack_name, suite, _AttackTarget(self.attack_target_model))
            if attack.is_dos_attack:
                raise ValueError(
                    f"Attack {self.attack_name!r} is a denial-of-service attack, which upstream "
                    "scores differently; it is not supported."
                )
            user_tasks = sorted(suite.user_tasks.items(), key=lambda kv: _task_number(kv[0]))
            injection_tasks = sorted(suite.injection_tasks.items(), key=lambda kv: _task_number(kv[0]))
            for user_task_id, user_task in user_tasks:
                if "user" in self.splits:
                    records.append(TaskRecord(suite_name, user_task_id, None, {}))
                if "attack" in self.splits:
                    for injection_task_id, injection_task in injection_tasks:
                        records.append(
                            TaskRecord(
                                suite_name,
                                user_task_id,
                                injection_task_id,
                                attack.attack(user_task, injection_task),
                            )
                        )
        return records

    def run(self) -> tuple[int, int]:
        records = self._records()
        if self.task_ids is not None:
            records = [r for r in records if r.local_id in self.task_ids]
            missing = self.task_ids - {r.local_id for r in records}
            if missing:
                logger.warning("Unknown task ids: %s", ", ".join(sorted(missing)))
        if self.limit is not None:
            records = records[: self.limit]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        generated = skipped = 0
        for record in records:
            task_dir = self.output_dir / record.local_id
            if task_dir.exists():
                if not self.overwrite:
                    skipped += 1
                    continue
                shutil.rmtree(task_dir)
            self._prepare_task(record, task_dir)
            generated += 1
        logger.info("Generated %d tasks in %s (%d skipped)", generated, self.output_dir, skipped)
        return generated, skipped

    def _prepare_task(self, record: TaskRecord, task_dir: Path) -> None:
        suite = self.suites[record.suite_name]
        user_task = suite.get_user_task_by_id(record.user_task_id)
        shutil.copytree(TEMPLATE_DIR, task_dir)

        attack = self.attack_name if record.injection_task_id else "none"
        replacements = {
            "{task_name}": record.local_id,
            "{suite}": record.suite_name,
            "{split}": record.split,
            "{difficulty}": user_task.DIFFICULTY.name.lower(),
            "{benchmark_version}": self.benchmark_version,
            "{user_task_id}": record.user_task_id,
            "{injection_task_id}": record.injection_task_id or "none",
            "{attack}": attack,
        }
        task_toml = task_dir / "task.toml"
        content = task_toml.read_text()
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        task_toml.write_text(content)

        instruction = task_dir / "instruction.md"
        instruction.write_text(
            instruction.read_text()
            .replace("{system_message}", self.system_message.strip())
            .replace("{prompt}", user_task.PROMPT)
        )

        task_config = {
            "benchmark_version": self.benchmark_version,
            "suite": record.suite_name,
            "user_task_id": record.user_task_id,
            "injection_task_id": record.injection_task_id,
            "attack": attack,
            "injections": record.injections,
        }
        (task_dir / "environment" / "runtime-server" / "task_config.json").write_text(
            json.dumps(task_config, indent=2) + "\n"
        )
        (task_dir / "tests" / "config.json").write_text(
            json.dumps({k: v for k, v in task_config.items() if k != "injections"}, indent=2) + "\n"
        )

        # Oracle: the user task's upstream ground truth calls, computed on the
        # same (injected) environment the runtime builds, then its ground truth
        # output as the final answer. It never follows the injection.
        environment = user_task.init_environment(
            suite.load_and_inject_default_environment(record.injections)
        )
        oracle = {
            "calls": [
                {"function": call.function, "args": dict(call.args)}
                for call in user_task.ground_truth(environment)
            ],
            "answer": user_task.GROUND_TRUTH_OUTPUT,
        }
        (task_dir / "solution" / "oracle.json").write_text(json.dumps(oracle, indent=2) + "\n")
