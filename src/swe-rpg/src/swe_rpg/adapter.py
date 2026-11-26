"""SWE-RPG adapter: one Harbor task per benchmark instance.

Each task gives the agent a repository at the issue's base commit and the
issue text. The agent edits the repository. After it stops, its changes are
recorded as one patch and graded in a separate verifier container with the
task's own rebuild and test commands and its hidden tests.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

UPSTREAM_REPO = "https://github.com/Xin-Zhou-smu/SWE-RPG-Bench"
UPSTREAM_CODE_REVISION = "688ed7918cbcabe6c9d9b9f393fad1053b286dd9"
DATA_URL = (
    "https://raw.githubusercontent.com/Xin-Zhou-smu/SWE-RPG-Bench/"
    f"{UPSTREAM_CODE_REVISION}/data/benchmark.jsonl"
)
DATA_SHA256 = "90c3f55fe74a111daad93d017d38a834136411678f0f9b03e0193cd076ef35a2"
CACHE_DIR = Path.home() / ".cache" / "swe-rpg-adapter"

TEMPLATE_DIR = Path(__file__).parent / "task-template"
PARITY_TASK_IDS_FILE = Path(__file__).parent / "parity_task_ids.txt"
SPLITS = ("full", "parity")

# Extra image build steps for single tasks, added to the agent image and the
# verifier image alike. Each entry is (reason, shell command).
IMAGE_FIXUPS: dict[str, tuple[str, str]] = {
    "junit-team__junit-framework-4474": (
        "The published image keeps the junit-<random> result directories of an\n"
        "# earlier Gradle test run. On Modal sandboxes (gVisor), the first run of\n"
        "# each Gradle test task deletes its old directory and then fails with\n"
        "# \"Could not read path\" on the deleted file, so the tests never run. In\n"
        "# plain Docker the same task deletes the directory and runs normally.\n"
        "# Removing the directories while the image is built avoids the failure.",
        "find {working_dir} -type d -path '*/build/test-results/*' -name 'junit-*' -prune -exec rm -r {} +",
    ),
}


@dataclass
class Instance:
    instance_id: str
    name: str
    repo: str
    base_commit: str
    language: str
    working_dir: str
    docker_image: str
    issues: list[dict]
    patch: str
    test_patch: str
    rebuild_cmds: list[str]
    test_cmds: list[str]
    print_cmds: list[str]
    log_parser: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]


def task_name(instance_id: str) -> str:
    return instance_id.lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command_script(commands: list[str]) -> str:
    """Same script shape as the original evaluator's `_write_command`."""
    text = " ; ".join(str(command) for command in commands)
    return "#!/usr/bin/env bash\nset +e\n" + (text if text.strip() else ":") + "\n"


def issue_text(issues: list[dict]) -> str:
    """The original input request: each linked issue's title and body."""
    blocks = []
    for issue in issues:
        title = (issue.get("issue_title") or "").strip()
        body = (issue.get("issue_body") or "").replace("\r\n", "\n").strip()
        blocks.append(f"# {title}\n\n{body}".strip())
    return "\n\n---\n\n".join(blocks)


class SweRpgAdapter:
    """Converts SWE-RPG instances into Harbor task directories."""

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "full",
        data_file: Path | None = None,
    ):
        if split not in SPLITS:
            raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.split = split
        self.data_file = Path(data_file) if data_file else None

    def _ensure_data(self) -> Path:
        path = self.data_file or CACHE_DIR / f"benchmark-{UPSTREAM_CODE_REVISION[:12]}.jsonl"
        if not path.is_file():
            if self.data_file is not None:
                raise FileNotFoundError(f"Data file not found: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(".part")
            logger.info("Downloading %s", DATA_URL)
            try:
                with urllib.request.urlopen(DATA_URL, timeout=300) as response, partial.open("wb") as out:
                    shutil.copyfileobj(response, out)
                partial.replace(path)
            except (urllib.error.URLError, OSError) as exc:
                partial.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Could not download {DATA_URL}: {exc}. Download it yourself and pass --data-file."
                ) from exc
        actual = _sha256(path)
        if actual != DATA_SHA256:
            raise RuntimeError(f"{path} has SHA256 {actual}, expected {DATA_SHA256}")
        return path

    def _load(self) -> list[Instance]:
        instances = []
        with self._ensure_data().open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if "@sha256:" not in row["docker_image"]:
                    raise ValueError(f"{row['instance_id']}: image is not pinned by digest")
                instances.append(
                    Instance(
                        instance_id=row["instance_id"],
                        name=task_name(row["instance_id"]),
                        repo=row["repo"],
                        base_commit=row["base_commit"],
                        language=row["pl"],
                        working_dir=row["working_dir"],
                        docker_image=row["docker_image"],
                        issues=row["issues"],
                        patch=row["patch"],
                        test_patch=row["test_patch"],
                        rebuild_cmds=row.get("rebuild_cmds") or [],
                        test_cmds=row.get("test_cmds") or [],
                        print_cmds=row.get("print_cmds") or [],
                        log_parser=row["log_parser"],
                        fail_to_pass=row["FAIL_TO_PASS"],
                        pass_to_pass=row["PASS_TO_PASS"],
                    )
                )
        names = [i.name for i in instances]
        if len(set(names)) != len(names):
            raise ValueError("Task names are not unique")
        unknown = set(IMAGE_FIXUPS) - set(names)
        if unknown:
            raise ValueError(f"IMAGE_FIXUPS names unknown tasks: {sorted(unknown)}")
        return sorted(instances, key=lambda i: i.name)

    def _load_parity_names(self) -> list[str]:
        try:
            lines = PARITY_TASK_IDS_FILE.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise RuntimeError(f"Cannot read parity task list {PARITY_TASK_IDS_FILE}: {exc}") from exc
        return [line.strip() for line in lines if line.strip() and not line.startswith("#")]

    def _select(self, instances: list[Instance]) -> list[Instance]:
        if self.split == "parity":
            wanted = set(self._load_parity_names())
            unknown = wanted - {i.name for i in instances}
            if unknown:
                raise ValueError(f"Parity task list names unknown tasks: {sorted(unknown)}")
            instances = [i for i in instances if i.name in wanted]
        if self.task_ids:
            wanted = {t.lower() for t in self.task_ids}
            instances = [i for i in instances if i.name in wanted]
            if not instances:
                raise ValueError(f"No task matches --task-ids {self.task_ids}")
        if self.limit is not None:
            instances = instances[: self.limit]
        return instances

    def run(self) -> None:
        selected = self._select(self._load())
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        for instance in selected:
            task_dir = self.output_dir / instance.name
            if task_dir.exists():
                if not self.overwrite:
                    logger.info("Skipping existing task %s", instance.name)
                    continue
                shutil.rmtree(task_dir)
            self._write_task(instance, task_dir)
            written += 1
        logger.info("Generated %d tasks in %s", written, self.output_dir)

    def _write_task(self, inst: Instance, task_dir: Path) -> None:
        (task_dir / "environment").mkdir(parents=True)
        (task_dir / "solution").mkdir()
        tests = task_dir / "tests"
        tests.mkdir()

        values = {
            "task_name": inst.name,
            "instance_id": inst.instance_id,
            "repo": inst.repo,
            "base_commit": inst.base_commit,
            "language": inst.language,
            "working_dir": inst.working_dir,
            "docker_image": inst.docker_image,
            "upstream_code_revision": UPSTREAM_CODE_REVISION,
            "upstream_data_sha256": DATA_SHA256,
        }

        fixup = IMAGE_FIXUPS.get(inst.name)
        fixup_block = ""
        if fixup:
            reason, command = fixup
            fixup_block = f"# {reason}\nRUN {command.replace('{working_dir}', inst.working_dir)}\n\n"

        def render(name: str, **extra: str) -> str:
            text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
            text = text.replace("{image_fixup}\n\n", fixup_block)
            for key, value in {**values, **extra}.items():
                text = text.replace("{" + key + "}", value)
            return text

        (task_dir / "task.toml").write_text(render("task.toml"), encoding="utf-8")
        # The issue text goes in last, so braces inside it are never treated as placeholders.
        instruction = render("instruction.md").replace("{issue_text}", issue_text(inst.issues))
        (task_dir / "instruction.md").write_text(instruction.rstrip() + "\n", encoding="utf-8")
        (task_dir / "environment" / "Dockerfile").write_text(render("environment/Dockerfile"), encoding="utf-8")

        solve = task_dir / "solution" / "solve.sh"
        solve.write_text(render("solution/solve.sh"), encoding="utf-8")
        solve.chmod(0o755)
        (task_dir / "solution" / "gold.patch").write_text(inst.patch, encoding="utf-8")

        (tests / "Dockerfile").write_text(render("tests/Dockerfile"), encoding="utf-8")
        test_sh = tests / "test.sh"
        test_sh.write_text(render("tests/test.sh"), encoding="utf-8")
        test_sh.chmod(0o755)
        shutil.copy2(TEMPLATE_DIR / "tests" / "grade.py", tests / "grade.py")
        (tests / "test.patch").write_text(inst.test_patch, encoding="utf-8")
        (tests / "rebuild.sh").write_text(_command_script(inst.rebuild_cmds), encoding="utf-8")
        (tests / "run_tests.sh").write_text(_command_script(inst.test_cmds), encoding="utf-8")
        (tests / "print.sh").write_text(_command_script(inst.print_cmds), encoding="utf-8")
        (tests / "log_parser.py").write_text(inst.log_parser, encoding="utf-8")
        (tests / "expected.json").write_text(
            json.dumps(
                {
                    "instance_id": inst.instance_id,
                    "FAIL_TO_PASS": inst.fail_to_pass,
                    "PASS_TO_PASS": inst.pass_to_pass,
                }
            ),
            encoding="utf-8",
        )
