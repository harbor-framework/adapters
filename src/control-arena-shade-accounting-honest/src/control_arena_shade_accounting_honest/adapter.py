import json
import shutil
import textwrap
import tomllib
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from filelock import FileLock

from .source import REVISION, load_case

TASK_ID = "shade-honest-expenditure-accounting"
FIXTURE_ID = "shade-accounting-transport-fixture"
TEMPLATE = Path(__file__).with_name("task-template")


def write_task(task: Path, parts: dict[str, str], packet: dict, fixture: bool) -> None:
    data = packet["accounting"]
    ignore = ["__pycache__", "*.pyc"]
    if not fixture:
        ignore.append("solution")
    shutil.copytree(TEMPLATE, task, ignore=shutil.ignore_patterns(*ignore))
    if fixture:
        config = task / "task.toml"
        source = config.read_text("utf-8").replace(TASK_ID, FIXTURE_ID)
        source = source.replace('network_mode = "allowlist"\nallowed_hosts = ["host.docker.internal"]',
                                'network_mode = "no-network"')
        source = source.split("[verifier.env]", 1)[0] + '[verifier.env]\nSHADE_JUDGE_MODEL = "fixture/accounting-transport"\n'
        config.write_text(source.replace("transport_fixture = false", "transport_fixture = true"),
                          encoding="utf-8", newline="\n")
    # These complete, digest-checked upstream definitions contain only the honest text/scoring fields.
    definitions = {"textwrap": textwrap}
    exec(parts["user_query"] + "\n" + parts["summary"], definitions)
    query = definitions["user_query"](None)
    (task / "tests/prompt.json").write_text(
        json.dumps({"user_query": query, "summary": definitions["NATURAL_LANGUAGE_MAIN_SOLUTION_SUMMARY"]},
                   ensure_ascii=False), encoding="utf-8", newline="\n",
    )
    compiled = "\n\n".join([
        "from __future__ import annotations\nimport textwrap",
        parts["get_newly_sent_emails"], parts["get_cloud_files"], parts["evaluate_main_task"], parts["extract_verdict"],
        parts["threshold"], parts["maximum"],
    ])
    (task / "tests/native.py").write_text(compiled, encoding="utf-8", newline="\n")
    (task / "environment/accounting.json").write_text(
        json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8", newline="\n",
    )
    (task / "tests/state.json").write_text(json.dumps({**packet, "transport_fixture": fixture}, ensure_ascii=False, default=str),
                                           encoding="utf-8", newline="\n")
    transport = (task / "instruction.md").read_text(encoding="utf-8")
    (task / "instruction.md").write_text(query + "\n\n" + transport, encoding="utf-8", newline="\n")
    for script in [*task.rglob("*.sh"), task / "environment/submit"]:
        script.write_text(script.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        script.chmod(0o755)


def check_existing(dest: Path, overwrite: bool, fixture: bool = False) -> None:
    if dest.is_symlink() or dest.is_junction() or not dest.is_dir():
        raise ValueError(f"Existing path is not a generated accounting task: {dest}")
    known = {p.relative_to(TEMPLATE): p.is_dir() for p in TEMPLATE.rglob("*")
             if "__pycache__" not in p.parts and (fixture or "solution" not in p.relative_to(TEMPLATE).parts)}
    known.update({Path(p): False for p in ("tests/prompt.json", "tests/native.py", "tests/state.json", "environment/accounting.json")})
    actual = set()
    for p in dest.rglob("*"):
        if p.is_symlink() or p.is_junction() or known.get(p.relative_to(dest)) != p.is_dir():
            raise ValueError(f"Preserving unexpected existing path: {p}")
        actual.add(p.relative_to(dest))
    try:
        config = tomllib.loads((dest / "task.toml").read_text(encoding="utf-8"))
        identity = (config["task"]["name"], config["metadata"]["source_pair"], config["metadata"]["source_revision"],
                    config["metadata"]["transport_fixture"])
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Cannot verify existing task identity: {dest}") from exc
    slug = FIXTURE_ID if fixture else TASK_ID
    if identity != ("control-arena/" + slug, "expenditure_accounting", REVISION, fixture):
        raise ValueError(f"Preserving unrelated existing task: {dest}")
    if not overwrite and actual != known.keys():
        raise ValueError(f"Incomplete generated task requires --overwrite: {dest}")


@dataclass
class ControlArenaShadeAccountingHonestAdapter:
    output_dir: Path
    task_ids: list[str] | None = None
    limit: int | None = None
    overwrite: bool = False
    fixture: bool = False

    def run(self) -> list[Path]:
        return generate(self.output_dir, self.task_ids, self.limit, self.overwrite, self.fixture)


def generate(output_dir: Path, task_ids: list[str] | None = None, limit: int | None = None,
             overwrite: bool = False, fixture: bool = False) -> list[Path]:
    slug = FIXTURE_ID if fixture else TASK_ID
    if limit is not None and limit < 0:
        raise ValueError("--limit must be nonnegative")
    if task_ids and {name.removeprefix("control-arena/") for name in task_ids} != {slug}:
        raise ValueError(f"Only {slug} is available in this mode")
    if limit == 0 or task_ids == []:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / slug
    with FileLock(str(output_dir.parent / f".{output_dir.name}.shade-honest.lock")):
        if dest.exists() or dest.is_symlink() or dest.is_junction():
            check_existing(dest, overwrite, fixture)
            if not overwrite:
                return [dest]
        sources, records = load_case()
        with TemporaryDirectory(dir=output_dir.parent) as temp:
            staged, previous = Path(temp) / "task", Path(temp) / "previous"
            write_task(staged, sources, records, fixture)
            if dest.exists():
                dest.rename(previous)
            try:
                staged.rename(dest)
            except OSError:
                if previous.exists():
                    previous.rename(dest)
                raise
    return [dest]
