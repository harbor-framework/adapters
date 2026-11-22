"""Generate isolated tasks without copying hidden data into the agent image."""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path

from .source import UPSTREAM_COMMIT, UPSTREAM_URL, archive_source, validate_source

PACKAGE = Path(__file__).parent
TEMPLATE = PACKAGE / "task-template"


class BizAgentBenchAdapter:
    def __init__(self, output_dir: Path, source_dir: Path, *, task_ids=None,
                 limit=None, overwrite=False, model_config: Path | None = None,
                 oracle_dir: Path | None = None):
        self.output_dir = Path(output_dir).resolve()
        self.source_dir = Path(source_dir).resolve()
        self.task_ids = task_ids
        self.limit = limit
        self.overwrite = overwrite
        self.model_config = model_config
        self.oracle_dir = oracle_dir

    def run(self) -> list[Path]:
        validate_source(self.source_dir)
        manifest = json.loads((self.source_dir / "payment/data/manifest.json").read_text("utf-8"))
        tasks = sorted(manifest["tasks"], key=lambda row: row["number"])
        known = {row["id"] for row in tasks}
        if self.task_ids:
            unknown = set(self.task_ids) - known
            if unknown:
                raise ValueError(f"Unknown task IDs: {sorted(unknown)}")
            tasks = [row for row in tasks if row["id"] in self.task_ids]
        if self.limit is not None:
            if self.limit < 1:
                raise ValueError("--limit must be positive")
            tasks = tasks[:self.limit]
        config = json.loads((self.model_config or self.source_dir / "configs/model.example.json").read_text("utf-8"))
        for role in ("agent", "user"):
            if any(key in config[role] for key in ("api_key", "dummy_api_key")):
                raise ValueError("Use api_key_env, never embed credentials in model config")
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", config[role]["api_key_env"]):
                raise ValueError("Invalid credential environment variable name")
        timeout = config["episode_timeout_seconds"]
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Invalid episode timeout")
        if type(config["max_errors"]) is not int or config["max_errors"] < 1:
            raise ValueError("Invalid native error threshold")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for row in tasks:
            target = self.output_dir / self.task_name(row["id"])
            if target.exists():
                if not self.overwrite:
                    raise FileExistsError(f"Task exists: {row['id']}; use --overwrite")
                if not (target / "source.json").is_file() or target.is_symlink():
                    raise ValueError(f"Refusing to replace unrelated directory {target}")
        generated = []
        with tempfile.TemporaryDirectory(dir=self.output_dir) as staging:
            snapshot = Path(staging) / "upstream.tar"
            digest = archive_source(self.source_dir, snapshot)
            for row in tasks:
                task_id = row["id"]
                name = self.task_name(task_id)
                target = self.output_dir / name
                task = Path(staging) / name
                shutil.copytree(TEMPLATE, task)
                runtime = task / "environment/runtime"
                shutil.copy2(snapshot, runtime / "upstream.tar")
                shutil.copy2(PACKAGE / "runtime.py", runtime / "runtime.py")
                shutil.copy2(PACKAGE / "requirements.txt", runtime / "requirements.txt")
                (runtime / "private.json").write_text(json.dumps({
                    "task_id": task_id, "config": config,
                    "upstream_commit": UPSTREAM_COMMIT, "archive_sha256": digest,
                }, indent=2) + "\n", encoding="utf-8")
                for path in (task / "task.toml", task / "tests/test.sh", task / "instruction.md",
                             task / "environment/docker-compose.yaml"):
                    content = (path.read_text("utf-8").replace("@TASK_NAME@", name)
                               .replace("@AGENT_TIMEOUT@", str(float(timeout + 120)))
                               .replace("@EPISODE_TIMEOUT@", str(timeout))
                               .replace("@USER_KEY_ENV@", config["user"]["api_key_env"]))
                    path.write_text(content, encoding="utf-8", newline="\n")
                (task / "source.json").write_text(json.dumps({
                    "repo": UPSTREAM_URL, "commit": UPSTREAM_COMMIT,
                    "archive_sha256": digest, "task_id": task_id,
                    "model_config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
                }, indent=2) + "\n", encoding="utf-8")
                for filename in ("upstream.tar", "requirements.txt"):
                    shutil.copy2(runtime / filename, task / "tests" / filename)
                shutil.copy2(task / "source.json", task / "tests" / "source.json")
                oracle = self.oracle_dir / f"{task_id}.json" if self.oracle_dir else None
                if oracle and oracle.is_file():
                    shutil.copy2(oracle, task / "solution/trajectory.json")
                if target.exists():
                    if target.resolve().parent != self.output_dir or target.is_symlink():
                        raise ValueError(f"Task path escapes the output directory: {target}")
                    shutil.rmtree(target)
                shutil.move(str(task), str(target))
                generated.append(target)
        return generated

    @staticmethod
    def task_name(task_id: str) -> str:
        return "bizagentbench-" + re.sub(r"[^a-z0-9]+", "-", task_id.lower()).strip("-")
