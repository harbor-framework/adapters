"""Export pinned Bash prompts and their upstream public pytest files in honest mode."""

import hashlib
import json
import shutil
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir

from filelock import FileLock

TEMPLATE = Path(__file__).with_name("task-template")
# Identifier sorting, Python class-name checks, and string component extraction.
CASE_IDS = (256989, 409382, 604648)


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def generate(output_dir: Path, task_ids: list[str] | None = None, limit: int | None = None,
             overwrite: bool = False, oracle_dir: Path | None = None) -> list[Path]:
    if limit is not None and limit < 0:
        raise ValueError("--limit must be nonnegative")
    slugs = {f"bash-{index}": index for index in CASE_IDS}
    wanted = set(slugs) if task_ids is None else {name.removeprefix("control-arena/") for name in task_ids}
    if unknown := wanted.difference(slugs):
        raise ValueError(f"Unknown task IDs: {sorted(unknown)}")
    selected = [slug for slug in slugs if slug in wanted][:limit]
    dist = distribution("control-arena")
    if dist.version != "20.1.1":
        raise ValueError("Generation requires control-arena==20.1.1")
    source = dist.locate_file("control_arena/settings/bash/bash_tasks.json")
    rows = {row["task_id"]: row for row in json.loads(Path(source).read_text(encoding="utf-8"))}
    if oracle_dir is not None:
        for slug in selected:
            if not (oracle_dir / f"{slugs[slug]}.sh").is_file():
                raise ValueError(f"Missing private oracle for {slug}")

    output_dir.mkdir(parents=True, exist_ok=True)
    lock_key = hashlib.sha256(bytes(output_dir.resolve())).hexdigest()
    with FileLock(Path(gettempdir()) / f"control-arena-bash-{lock_key}.lock"):
        for slug in selected:
            row = rows[slugs[slug]]
            destination = output_dir / slug
            identity = {"setting": "bash", "mode": "honest", "source_id": slugs[slug], "version": dist.version}
            if destination.is_symlink() or destination.is_junction():
                raise ValueError(f"Existing path is a link: {destination}")
            if destination.exists():
                marker = destination / "tests/case.json"
                if not marker.is_file() or json.loads(marker.read_text()) != identity:
                    raise ValueError(f"Existing path is not the expected generated task: {destination}")
                if not overwrite:
                    if oracle_dir is not None and not (destination / "solution/solution.sh").is_file():
                        raise ValueError(f"Use --overwrite to add the private oracle to {slug}")
                    continue
            with TemporaryDirectory(dir=output_dir) as tmp:
                stage = Path(tmp) / "new"
                shutil.copytree(TEMPLATE, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                config = stage / "task.toml"
                _write(config, config.read_text(encoding="utf-8").replace("{task_id}", slug))
                prompt = stage / "instruction.md"
                _write(prompt, prompt.read_text(encoding="utf-8").replace("{instruction}", row["task_description"]))
                for folder in ("environment", "tests"):
                    _write(stage / folder / "test_task.py", row["task_verifiable"])
                _write(stage / "tests/case.json", json.dumps(identity) + "\n")
                if oracle_dir is None:
                    shutil.rmtree(stage / "solution")
                else:
                    _write(stage / "solution/solution.sh", (oracle_dir / f"{slugs[slug]}.sh").read_text(encoding="utf-8"))
                for script in stage.rglob("*.sh"):
                    _write(script, script.read_text(encoding="utf-8"))
                    script.chmod(0o755)
                previous = Path(tmp) / "old"
                if destination.exists():
                    destination.rename(previous)
                try:
                    stage.rename(destination)
                except OSError:
                    if previous.exists():
                        previous.rename(destination)
                    raise
    return [output_dir / slug for slug in selected]
