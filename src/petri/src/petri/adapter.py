"""
Adapter class for generating Harbor tasks from inspect_petri.

Implement run() to load the upstream dataset and write Harbor tasks into self.output_dir.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

INSPECT_PETRI_REPO = "https://github.com/meridianlabs-ai/inspect_petri.git"
INSPECT_PETRI_REVISION = "0727facedcd8fe21984700f9a2bc4a0589ee0a85"
SEEDS_DIR = "src/inspect_petri/_seeds/default"

DEFAULT_DATASET_CACHE_DIR = Path.home() / ".cache" / "harbor" / "petri"
DEFAULT_AUDITOR_MODEL = "anthropic/claude-sonnet-4-6"
DEFAULT_JUDGE_MODEL = "anthropic/claude-opus-4-6"

TASK_TEMPLATE_DIR = Path(__file__).parent / "task-template"

AGENT_TIMEOUT_SEC = 1800


def _render_template(path: Path, substitutions: dict[str, str]) -> None:
    """Replace each `token -> value` pair in `substitutions` within the file at `path`."""
    content = path.read_text()
    for token, value in substitutions.items():
        content = content.replace(token, value)

    path.write_text(content)


def _git_clone(repo_url: str, revision: str | None, destination: Path, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            return destination

        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Cloning {repo_url} to {destination}")
    subprocess.run(["git", "clone", "--quiet", repo_url, str(destination)], check=True)

    if revision:
        subprocess.run(["git", "-C", str(destination), "checkout", "--quiet", revision], check=True)

    return destination


class PetriAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        dataset_cache_dir: Path = DEFAULT_DATASET_CACHE_DIR,
        auditor_model: str = DEFAULT_AUDITOR_MODEL,
        judge_model: str = DEFAULT_JUDGE_MODEL,
        **kwargs,
    ):
        """
        Initialize the adapter.

        Args:
            output_dir: The directory to write the generated tasks to.
            limit: The maximum number of tasks to generate.
            overwrite: Whether to overwrite existing tasks.
            task_ids: The task IDs to generate.
            dataset_cache_dir: Where to clone the GitHub repo.
            auditor_model: Model the auditor uses to run the audit.
            judge_model: Model the verifier uses to judge the audit.
            **kwargs: Additional arguments.
        """
        self.output_dir = output_dir
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = {t.lower() for t in task_ids} if task_ids else None
        self.dataset_cache_dir = Path(dataset_cache_dir)
        self.auditor_model = auditor_model
        self.judge_model = judge_model

    def run(self) -> None:
        """
        Iterate over the default seeds and generate Harbor tasks in self.output_dir.

        <output-dir>/
        ├── <task-id-1>/
        │   ├── environment/
        │   │   ├── auditor_server.py
        │   │   ├── chat.py
        │   │   ├── docker-compose.yaml
        │   │   ├── Dockerfile
        │   │   ├── Dockerfile.auditor
        │   │   └── <seed>.md
        │   ├── solution/
        │   │   └── solve.sh
        │   ├── tests/
        │   │   ├── Dockerfile
        │   │   ├── judge.py
        │   │   └── test.sh
        │   ├── instruction.md
        │   └── task.toml
        └── ...
        """
        repo_dir = _git_clone(INSPECT_PETRI_REPO, INSPECT_PETRI_REVISION, self.dataset_cache_dir / "inspect_petri", self.overwrite)
        seed_files = sorted((repo_dir / SEEDS_DIR).glob("*.md"), key=lambda p: p.name)

        if self.task_ids:
            seed_files = [s for s in seed_files if self._task_id(s) in self.task_ids]

        if self.limit is not None:
            seed_files = seed_files[:self.limit]

        for seed_file in seed_files:
            self._generate_task(seed_file)

    def _task_id(self, seed_file: Path) -> str:
        """Return a seed's task_id (e.g., `ai_consciousness_gentle_probe`)."""
        return re.sub(r"[^a-z0-9_-]", "-", seed_file.stem.lower())

    def _generate_task(self, seed_file: Path) -> None:
        """Generate one Harbor task from a single seed file (e.g., `_seeds/default/ai_consciousness_gentle_probe`)."""
        task_id = self._task_id(seed_file)

        out_dir = self.output_dir / task_id
        if out_dir.exists():
            if not self.overwrite:
                logger.debug(f"Skipping {task_id}: already exists at {out_dir}")
                return

            shutil.rmtree(out_dir)

        shutil.copytree(TASK_TEMPLATE_DIR, out_dir)
        shutil.copy2(seed_file, out_dir / "environment" / seed_file.name)

        _render_template(
            out_dir / "environment" / "Dockerfile.auditor",
            {
                "{inspect_petri_revision}": INSPECT_PETRI_REVISION,
                "{seed_file}": seed_file.name,
            },
        )
        _render_template(
            out_dir / "tests" / "Dockerfile",
            { "{inspect_petri_revision}": INSPECT_PETRI_REVISION },
        )
        _render_template(
            out_dir / "environment" / "docker-compose.yaml",
            { "{auditor_model}": self.auditor_model },
        )
        _render_template(
            out_dir / "task.toml",
            {
                "{task_id}": task_id,
                "{agent_timeout_sec}": str(AGENT_TIMEOUT_SEC),
                "{judge_model}": self.judge_model,
            },
        )

        logger.debug(f"Generated task {task_id} at {out_dir}")
