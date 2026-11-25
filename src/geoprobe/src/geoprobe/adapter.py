"""Generate isolated agent/verifier tasks from the content-locked catalog."""
import json
from pathlib import Path
import re
import shutil
from string import Template
import tempfile

from .sources import ARENA_COMMIT, DATASET_COMMIT, HARBOR_COMMIT, load_cases, safe_relative, sha256
from .upstream.open_loop_media import write_transport_frame

PACKAGE = Path(__file__).parent
AUTHORS = ["Haojian Huang", "Pukun Zhao", "Zexi Li", "Yehang Zhang", "Yangkai Wei", "Wenqian Li",
           "Han Yang", "Kaiwen Zhou", "Ying-Cong Chen", "Yinchuan Li"]


def task_id(sample_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", sample_id.lower()).strip("-")


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


class GeoProbeAdapter:
    def __init__(self, output_dir: Path, data_root: Path, limit: int | None = None,
                 overwrite: bool = False, task_ids: list[str] | None = None):
        self.output_dir = Path(output_dir).resolve()
        self.data_root = Path(data_root).resolve()
        self.limit, self.overwrite, self.task_ids = limit, overwrite, task_ids

    def run(self) -> list[Path]:
        cases = load_cases(self.data_root)
        ids = [task_id(case["sample_id"]) for case in cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Task-name sanitization collision")
        if self.task_ids:
            wanted = set(self.task_ids)
            known = set(ids) | {case["sample_id"] for case in cases}
            if wanted - known:
                raise ValueError(f"Unknown task IDs: {sorted(wanted - known)}")
            cases = [case for case in cases if case["sample_id"] in wanted or task_id(case["sample_id"]) in wanted]
        if self.limit is not None:
            cases = cases[:self.limit]
        # Validate the complete selected closure before writing any task.
        for case in cases:
            for image in case["images"]:
                path = self.data_root / safe_relative(image["path"])
                if sha256(path) != image["sha256"]:
                    raise ValueError(f"Image checksum mismatch: {path}")
            target = self.output_dir / task_id(case["sample_id"])
            if target.is_symlink():
                raise ValueError(f"Refusing task symlink: {target}")
            if target.exists() and (not self.overwrite or not (target / "geoprobe-source.json").is_file()):
                raise ValueError(f"Task already exists; --overwrite only replaces generated GeoProbe tasks: {target}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for case in cases:
            with tempfile.TemporaryDirectory(prefix=".geoprobe-", dir=self.output_dir) as scratch:
                staged = Path(scratch) / "task"
                self._write_task(case, staged)
                target = self.output_dir / task_id(case["sample_id"])
                if target.exists():
                    shutil.rmtree(target)
                staged.rename(target)
        shutil.copyfile(PACKAGE / "metric.py", self.output_dir / "metric.py")
        return [self.output_dir / task_id(case["sample_id"]) for case in cases]

    def _write_task(self, case: dict, directory: Path) -> None:
        shutil.copytree(PACKAGE / "task-template", directory)
        name = task_id(case["sample_id"])
        environment, tests = directory / "environment", directory / "tests"
        public = {key: case[key] for key in ("benchmark", "sample_id", "task_family", "answer_type", "answer_schema", "units", "question")}
        public["public_context"] = case.get("public_context", {})
        public["images"] = []
        image_lines = []
        transport_receipt = []
        for i, item in enumerate(case["images"]):
            source = self.data_root / safe_relative(item["path"])
            relative = Path("data") / safe_relative(item["path"])
            destination = environment / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            public["images"].append(dict(item))
            frame, native, size = write_transport_frame(source, environment / "frames", i)
            if tuple(native) != (item["width"], item["height"]):
                raise ValueError(f"Image dimension mismatch: {source}")
            image_lines.append(f"- /workspace/frames/{frame.name}: {item['role']}; native {native[0]}×{native[1]}, attachment {size[0]}×{size[1]}")
            transport_receipt.append({"path": f"frames/{frame.name}", "sha256": sha256(frame)})
        # No GT, provenance, native score, or oracle material enters this build context.
        # The native loader consumes one JSON object per line.
        (environment / "data/catalog.jsonl").write_text(json.dumps(public, ensure_ascii=False) + "\n")
        dump(environment / "public-task.json", public)
        shutil.copyfile(PACKAGE / "public_runner.py", environment / "run_public.py")
        values = {
            "task_id": name, "authors": ", ".join("{ name = " + json.dumps(author) + " }" for author in AUTHORS),
            "protocol": case["benchmark"], "sample_id": case["sample_id"], "question": case["question"],
            "image_manifest": "\n".join(image_lines), "answer_schema": json.dumps(case["answer_schema"], ensure_ascii=False),
            "units": str(case["units"]), "arena_commit": ARENA_COMMIT,
        }
        for relative in ["task.toml", "instruction.md", "environment/Dockerfile"]:
            file = directory / relative
            file.write_text(Template(file.read_text()).substitute(values))
        private_package = tests / "geoprobe"
        private_package.mkdir()
        (private_package / "__init__.py").write_text("")
        for module in ["grader.py", "rewards.py"]:
            shutil.copyfile(PACKAGE / module, private_package / module)
        shutil.copytree(PACKAGE / "upstream", private_package / "upstream", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        dump(tests / "case.json", case)
        dump(directory / "solution/answer.json", case["gt"])
        dump(directory / "geoprobe-source.json", {
            "sample_id": case["sample_id"], "arena_commit": ARENA_COMMIT, "dataset_commit": DATASET_COMMIT,
            "harbor_compatibility_commit": HARBOR_COMMIT, "source_images": case["images"], "transport_images": transport_receipt,
        })
        for script in [directory / "solution/solve.sh", tests / "test.sh"]:
            script.chmod(0o755)
