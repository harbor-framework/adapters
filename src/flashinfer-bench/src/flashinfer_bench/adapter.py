"""Package immutable upstream records; never rewrite definitions or scoring."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

UPSTREAM_REVISION = "15618a67e8d7b7f49ca61b5ba3b9f26a876d0bee"
DATASET_REVISION = "da915083d4c7c5e61aa3005e3d17ae488e0fc71c"
DATASET_URL = "https://huggingface.co/datasets/flashinfer-ai/flashinfer-trace"
TEMPLATE = Path(__file__).parent / "task-template"


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def source_repository(path: Path | None) -> Path:
    if path is not None:
        return path.resolve()
    repo = Path.home() / ".cache/harbor-flashinfer-bench/trace"
    if not (repo / ".git").exists():
        repo.mkdir(parents=True, exist_ok=True)
        git(repo, "init", "--quiet")
        git(repo, "remote", "add", "origin", DATASET_URL)
        git(repo, "fetch", "--depth", "1", "origin", DATASET_REVISION)
    return repo


def task_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class FlashInferBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        source: Path | None = None,
        *,
        limit: int | None = None,
        task_ids: list[str] | None = None,
        overwrite: bool = False,
        target_gpu: str = "B200",
    ):
        self.output_dir = Path(output_dir).resolve()
        self.limit, self.task_ids, self.overwrite = limit, task_ids, overwrite
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive")
        self.target_gpu = target_gpu
        self.repo = source_repository(source)

    def read(self, path: str) -> bytes:
        return git(self.repo, "show", f"{DATASET_REVISION}:{path}")

    def inventory(self):
        paths = (
            git(self.repo, "ls-tree", "-r", "--name-only", DATASET_REVISION)
            .decode()
            .splitlines()
        )
        definitions, workloads, baselines = {}, defaultdict(list), defaultdict(list)
        for path in paths:
            if path.startswith("definitions/") and path.endswith(".json"):
                record = json.loads(self.read(path))
                definitions[record["name"]] = path
            elif path.startswith("workloads/") and path.endswith(".jsonl"):
                rows = [
                    json.loads(line)
                    for line in self.read(path).splitlines()
                    if line.strip()
                ]
                workloads[rows[0]["definition"]].append((path, rows))
            elif path.startswith("solutions/") and path.endswith(".json"):
                record = json.loads(self.read(path))
                if record["author"] == "baseline":
                    baselines[record["definition"]].append(path)
        eligible, excluded = {}, {}
        for name, path in sorted(definitions.items()):
            if not workloads[name]:
                excluded[name] = "no released workloads"
            elif len(baselines[name]) != 1:
                excluded[name] = (
                    f"expected exactly one baseline; found {len(baselines[name])}"
                )
            else:
                eligible[name] = (path, workloads[name], baselines[name][0])
        return eligible, excluded

    def run(self):
        eligible, excluded = self.inventory()
        ids = {task_id(name): name for name in eligible}
        ids.update({name: name for name in eligible})
        selected = (
            sorted({ids[name] for name in self.task_ids})
            if self.task_ids
            else list(eligible)
        )
        selected = selected[: self.limit]
        selected_ids = {task_id(name) for name in selected}
        existing_ids = {p.parent.name for p in self.output_dir.glob("*/task.toml")}
        if existing_ids - selected_ids:
            raise ValueError(
                "Output contains unselected tasks; use a fresh output directory "
                "so scope.json describes the entire generated dataset"
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "scope.json").unlink(missing_ok=True)
        for name in selected:
            dest = self.output_dir / task_id(name)
            if self.overwrite and dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(TEMPLATE, dest)
            self.render(dest, name, eligible[name])
        report = {
            "upstream_revision": UPSTREAM_REVISION,
            "dataset_revision": DATASET_REVISION,
            "eligible": list(eligible),
            "excluded": excluded,
            "selected": selected,
        }
        (self.output_dir / "scope.json").write_text(json.dumps(report, indent=2) + "\n")
        return report

    def render(self, task: Path, name: str, entry):
        definition_path, workload_files, baseline_path = entry
        files = [definition_path, *(p for p, _ in workload_files)]
        blobs = set()
        uuids = []
        for _, rows in workload_files:
            for row in rows:
                uuids.append(row["workload"]["uuid"])
                for value in row["workload"]["inputs"].values():
                    if value["type"] == "safetensors":
                        path = Path(value["path"]).as_posix()
                        blobs.add(path)
        blob_manifest = {}
        for path in sorted(blobs):
            _, oid, size = self.read(path).decode().splitlines()
            blob_manifest[path] = {
                "sha256": oid.split(":")[1],
                "size": int(size.split()[1]),
            }
        for path in files:
            data = self.read(path)
            for root in (task / "environment/data", task / "tests/data"):
                dest = root / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
        baseline = self.read(baseline_path)
        (task / "tests/baseline.json").write_bytes(baseline)
        oracle = json.loads(baseline)
        oracle.update(name="harbor_reference_oracle", author="harbor-oracle")
        (task / "solution/solution.json").write_text(json.dumps(oracle) + "\n")
        manifest = {
            "definition": name,
            "upstream_revision": UPSTREAM_REVISION,
            "dataset_revision": DATASET_REVISION,
            "target_gpu": self.target_gpu,
            "blobs": blob_manifest,
            "workload_uuids": uuids,
        }
        for part in ("environment", "tests"):
            (task / part / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n"
            )
        replacements = {
            "TASK_ID": task_id(name),
            "DEFINITION": name,
            "TARGET_GPU": self.target_gpu,
            "UPSTREAM_REVISION": UPSTREAM_REVISION,
            "VERIFIER_TIMEOUT": str(max(1800, len(uuids) * 2 * 300 + 600)),
        }
        for path in (
            task / "task.toml",
            task / "instruction.md",
            task / "environment/Dockerfile",
        ):
            text = path.read_text()
            for key, value in replacements.items():
                text = text.replace("@@" + key + "@@", value)
            path.write_text(text)
        runtime = Path(__file__).parent / "runtime"
        shutil.copytree(
            runtime,
            task / "environment/runtime",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copytree(
            runtime,
            task / "tests/runtime",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        for path in task.rglob("*.sh"):
            path.chmod(0o755)
