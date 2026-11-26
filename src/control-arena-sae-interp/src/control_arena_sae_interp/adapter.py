"""Generate Harbor tasks from the SAE samples shipped with ControlArena."""

import hashlib
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir

from control_arena import EvalMode
from control_arena.settings.sae_interp_sabotage.setting import SAEInterpSetting
from filelock import FileLock
from inspect_ai.dataset import Sample

TEMPLATE = Path(__file__).with_name("task-template")


def instruction_for(sample: Sample) -> str:
    """Only these two upstream fields belong in the agent-visible task."""
    if not isinstance(sample.input, str) or not sample.metadata:
        raise ValueError("Expected a text SAE sample with setting metadata")
    return sample.metadata["setting_description"].rstrip() + "\n\n" + sample.input + "\n"


def _write_json(path: Path, data: dict) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


class ControlArenaSAEInterpAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids

    def run(self) -> list[Path]:
        if self.limit is not None and self.limit < 0:
            raise ValueError("--limit must be nonnegative")
        samples = SAEInterpSetting().get_dataset(EvalMode.HONEST)
        cases = {}
        for index, sample in enumerate(samples):
            instruction = instruction_for(sample)
            digest = hashlib.sha256(sample.input.encode("utf-8")).hexdigest()
            slug = f"sae-interp-{digest[:12]}"
            if slug in cases:
                raise ValueError(f"Duplicate SAE task ID: {slug}")
            cases[slug] = (index, digest, instruction, sample.metadata["main_task_name"])

        selected = list(cases)
        if self.task_ids is not None:
            requested = {name.removeprefix("control-arena/") for name in self.task_ids}
            unknown = requested.difference(cases)
            if unknown:
                raise ValueError(f"Unknown task IDs: {', '.join(sorted(unknown))}")
            selected = [name for name in selected if name in requested]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Serialize generation for this destination without adding a file to the dataset.
        lock_id = hashlib.sha256(bytes(self.output_dir.resolve())).hexdigest()
        with FileLock(Path(gettempdir()) / f"harbor-sae-{lock_id}.lock"):
            return [self._write_task(slug, *cases[slug]) for slug in selected[: self.limit]]

    def _write_task(self, slug: str, index: int, digest: str, instruction: str, label: str) -> Path:
        destination = self.output_dir / slug
        if destination.is_symlink() or destination.is_junction():
            raise ValueError(f"Existing path is a link: {destination}")
        if destination.exists():
            case_file = destination / "tests" / "case.json"
            if not case_file.is_file():
                raise ValueError(f"Existing path is not a generated SAE task: {destination}")
            previous_case = json.loads(case_file.read_text(encoding="utf-8"))
            if previous_case.get("prompt_sha256") != digest:
                raise ValueError(f"Existing SAE task identity differs: {destination}")
            if not self.overwrite:
                return destination

        with TemporaryDirectory(dir=self.output_dir, prefix=".sae-") as temporary:
            workspace = Path(temporary)
            staged = workspace / "new"
            shutil.copytree(TEMPLATE, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for filename, token, content in (
                ("task.toml", "{task_id}", slug),
                ("instruction.md", "{instruction}\n", instruction),
            ):
                path = staged / filename
                template = path.read_text(encoding="utf-8")
                if template.count(token) != 1:
                    raise ValueError(f"Expected one {token!r} in {filename}")
                path.write_text(template.replace(token, content), encoding="utf-8", newline="\n")
            _write_json(staged / "tests/case.json", {"source_index": index, "prompt_sha256": digest})
            _write_json(staged / "solution/submission.json", {"interpretation": label})
            # Linux task scripts may have been checked out with Windows line endings.
            for script in staged.rglob("*.sh"):
                script.write_text(script.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
                script.chmod(0o755)
            previous = workspace / "previous"
            if destination.exists():
                destination.rename(previous)
            try:
                staged.rename(destination)
            except OSError:
                if previous.exists():
                    previous.rename(destination)
                raise
        return destination
