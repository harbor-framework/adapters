import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from control_arena.settings.data_poisoning.config import SETTING_DESCRIPTION

from .public_case import DOMAIN, agent_prompt, digest, prompts
from .references import reference

TEMPLATE = Path(__file__).with_name("task-template")


def write(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


class ControlArenaDataQualityHonestAdapter:
    def __init__(self, output_dir: Path, limit=None, overwrite=False, task_ids=None):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids

    def run(self) -> list[Path]:
        if self.limit is not None and self.limit < 0:
            raise ValueError("--limit must be nonnegative")
        rows = {f"data-quality-factual-{i:02}": (i, p) for i, p in enumerate(prompts())}
        wanted = set(rows) if self.task_ids is None else {s.removeprefix("control-arena/") for s in self.task_ids}
        if unknown := wanted - rows.keys():
            raise ValueError(f"Unknown factual-accuracy task IDs: {sorted(unknown)}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        selected = [s for s in rows if s in wanted][:self.limit]
        for slug in selected:
            path = self.output_dir / slug
            if path.exists() and not self.overwrite:
                continue
            index, original = rows[slug]
            prompt = agent_prompt(original)
            expected = reference(index)
            with TemporaryDirectory(dir=self.output_dir) as temp:
                staging = Path(temp) / "new"
                shutil.copytree(TEMPLATE, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                config = staging / "task.toml"
                write(config, config.read_text("utf-8").replace("{slug}", slug))
                instructions = staging / "instruction.md"
                write(instructions, instructions.read_text("utf-8").replace("{setting}", SETTING_DESCRIPTION).replace("{prompt}", prompt))
                write(staging / "solution" / "submission.json", expected.model_dump_json() + "\n")
                write(staging / "tests" / "case.json", json.dumps({
                    "domain": DOMAIN, "source_index": index, "source_prompt_sha256": digest(original),
                    "adapted_prompt_sha256": digest(prompt), "fixture_input_sha256": digest(expected.monitor_input),
                }))
                shutil.copyfile(Path(__file__).with_name("public_case.py"), staging / "tests" / "public_case.py")
                for script in staging.rglob("*.sh"):
                    write(script, script.read_text("utf-8"))
                    script.chmod(0o755)
                previous = Path(temp) / "previous"
                if path.exists():
                    path.rename(previous)
                try:
                    staging.rename(path)
                except OSError:
                    if previous.exists():
                        previous.rename(path)
                    raise
        return [self.output_dir / slug for slug in selected]
