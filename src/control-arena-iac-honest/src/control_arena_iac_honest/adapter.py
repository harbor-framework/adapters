"""Generate only the five honest IaC tasks shipped in the pinned ControlArena wheel."""

import ast
import hashlib
import inspect
import json
import shutil
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir

from control_arena.settings.iac.config import SETTING_DESCRIPTION
from control_arena.settings.iac.objectives import main_objectives
from control_arena.settings.iac_fast.config import SETTING_DESCRIPTION as FAST_DESCRIPTION
from control_arena.settings.iac_fast.objectives import main_objectives as fast_objectives
from control_arena.settings.iac_fast.scorers import _parse_junit_xml_for_marker
from filelock import FileLock

PIN = "20.1.1"
OBJECTIVES = (
    "add_interpretability_ou", "create_billing_alarm", "tag_security_policies",
    "org_config_aggregator", "enforce_mandatory_tags_scp",
)
PROJECT_FILES = ("README.md", "cdk.json", "cdk.context.json", "pyproject.toml")
TEMPLATE = Path(__file__).with_name("task-template")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


class ControlArenaIaCHonestAdapter:
    def __init__(self, output_dir: Path, limit: int | None = None, overwrite: bool = False,
                 task_ids: list[str] | None = None, setting: str = "iac"):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        if setting not in ("iac", "iac_fast"):
            raise ValueError("Expected iac or iac_fast")
        self.setting = setting

    def run(self) -> list[Path]:
        release = distribution("control-arena")
        if release.version != PIN or set(main_objectives) != set(OBJECTIVES) or fast_objectives != main_objectives:
            raise ValueError("The installed release differs from the reviewed IaC objective list")
        if self.limit is not None and self.limit < 0:
            raise ValueError("--limit must be nonnegative")
        source = Path(release.locate_file("control_arena/settings"))
        prefix = self.setting.replace("_", "-") + "-honest-"
        slugs = {name: prefix + name.replace("_", "-") for name in OBJECTIVES}
        aliases = {alias: name for name, slug in slugs.items()
                   for alias in (name, slug, "control-arena/" + slug)}
        requested = set(OBJECTIVES)
        if self.task_ids is not None:
            unknown = set(self.task_ids).difference(aliases)
            if unknown:
                raise ValueError(f"Unknown honest IaC objectives: {sorted(unknown)}")
            requested = {aliases[key] for key in self.task_ids}
        names = [name for name in OBJECTIVES if name in requested][: self.limit]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        lock = hashlib.sha256(bytes(self.output_dir.resolve())).hexdigest()
        with FileLock(Path(gettempdir()) / f"harbor-iac-{lock}.lock"):
            return [self._generate(name, slugs[name], source) for name in names]

    def _generate(self, name: str, slug: str, source: Path) -> Path:
        destination = self.output_dir / slug
        identity = {"control_arena": PIN, "mode": "honest", "setting": self.setting, "objective": name}
        if destination.exists() or destination.is_symlink() or destination.is_junction():
            marker = destination / "tests/source.json"
            if (not marker.is_file() or marker.resolve() != self.output_dir.resolve() / slug / "tests/source.json"
                    or json.loads(marker.read_text(encoding="utf-8")) != identity):
                raise ValueError(f"Destination belongs to another task: {destination}")
            if not self.overwrite:
                return destination
        with TemporaryDirectory(dir=self.output_dir, prefix=".iac-") as temp:
            stage = Path(temp) / "new"
            shutil.copytree(TEMPLATE, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            repo = stage / "environment/repo"
            repo.mkdir()
            baseline = source / ("iac_fast/docker/setting" if self.setting == "iac_fast" else "iac/setting")
            for filename in PROJECT_FILES:
                shutil.copyfile(baseline / filename, repo / filename)
            for module in (baseline / "core_infrastructure").rglob("*.py"):
                target = repo / module.relative_to(baseline)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(module, target)
            for filename in ("conftest.py", f"test_{name}.py"):
                shutil.copyfile(baseline / "tests" / filename, stage / "tests" / filename)
            shutil.copyfile(source / "iac/tasks/QA" / name / "solution.patch", stage / "solution/reference.patch")
            write(stage / "tests/source.json", json.dumps(identity) + "\n")
            description = SETTING_DESCRIPTION
            if self.setting == "iac_fast":
                description = FAST_DESCRIPTION
                # Bundle only the release's pure positive-marker XML parser.
                # Drop its docstring, which references unrelated task names.
                function = ast.parse(inspect.getsource(_parse_junit_xml_for_marker)).body[0]
                function.body = function.body[1:]
                parser = "from defusedxml import ElementTree\n\n" + ast.unparse(function) + "\n"
                write(stage / "tests/fast_junit.py", parser)
            write(
                stage / "instruction.md",
                description + "\n\n" + main_objectives[name].strip()
                + "\n\nHarbor collects /repo/core_infrastructure for verification. Make the CDK changes in that package.\n",
            )
            config = stage / "task.toml"
            write(config, config.read_text(encoding="utf-8").replace("{task_id}", slug)
                  .replace("{setting}", self.setting))
            for script in stage.rglob("*.sh"):
                write(script, script.read_text(encoding="utf-8"))
                script.chmod(0o755)
            previous = Path(temp) / "previous"
            if destination.exists():
                destination.rename(previous)
            try:
                stage.rename(destination)
            except OSError:
                if previous.exists():
                    previous.rename(destination)
                raise
        return destination
