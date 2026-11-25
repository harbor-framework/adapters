"""SWE-Bench-ProMax -> Harbor task directories.

Source data: the Hugging Face dataset ``swe-bench-promax/SWE-Bench-ProMax`` at ``HF_REVISION``:
``swe-bench-promax.json`` (170 instances) and ``eval.json`` (one official eval script per instance).

Each Harbor task runs the instance's published image directly (``[environment].docker_image``, pinned to
the digest in ``image_digests.json``), copies
the official eval script verbatim into ``tests/eval.sh`` and reproduces the original pass rule (see
``task-template/tests/test.sh``).
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

HF_REPO = "swe-bench-promax/SWE-Bench-ProMax"
HF_REVISION = "b6f4fd65a18c0875ee410b1dcc32246c099ec03b"
TEMPLATE_DIR = Path(__file__).parent / "task-template"
# Docker Hub digest of each task image (the `<instance_id>-harbor-adapted` tag), so a later push to the
# tag cannot change an existing task.
IMAGE_DIGESTS: dict[str, str] = json.loads((Path(__file__).parent / "image_digests.json").read_text())

# Instance ids left out of the adapted dataset, with the reason. Empty: every task's empty patch fails
# and its reference patch passes (checked with the original harness and with `harbor run`).
EXCLUDED: dict[str, str] = {}


@dataclass
class ProMaxRecord:
    instance_id: str
    repo: str
    language: str
    problem_statement: str
    patch: str
    image_name: str
    eval_script: str
    base_commit: str


def load_records(data_dir: Path | None = None) -> list[ProMaxRecord]:
    if data_dir is None:
        from huggingface_hub import hf_hub_download

        inst = hf_hub_download(HF_REPO, "swe-bench-promax.json", repo_type="dataset", revision=HF_REVISION)
        ev = hf_hub_download(HF_REPO, "eval.json", repo_type="dataset", revision=HF_REVISION)
    else:
        inst, ev = data_dir / "swe-bench-promax.json", data_dir / "eval.json"
    rows = json.loads(Path(inst).read_text(encoding="utf-8"))
    evals = json.loads(Path(ev).read_text(encoding="utf-8"))
    return [
        ProMaxRecord(
            instance_id=r["instance_id"],
            repo=r["repo"],
            language=r["language"],
            problem_statement=r["problem_statement"],
            patch=r["patch"],
            image_name=pinned_image(r["image_name"], r["instance_id"]),
            eval_script=evals[r["instance_id"]]["eval_script"],
            base_commit=r["base_commit"],
        )
        for r in rows
    ]


def pinned_image(image_name: str, instance_id: str) -> str:
    """`repo:<id>` -> `repo:<id>-harbor-adapted@sha256:...` when the digest is known."""
    digest = IMAGE_DIGESTS.get(instance_id)
    if digest is None:
        return image_name
    repo = image_name.rsplit(":", 1)[0]
    return f"{repo}:{instance_id}-harbor-adapted@{digest}"


def task_name(instance_id: str) -> str:
    """Registry-safe task name: lowercase; anything other than [a-z0-9._-] becomes a hyphen."""
    return re.sub(r"[^a-z0-9._-]+", "-", instance_id.lower()).strip("-._")


def _render(text: str, **repls: str) -> str:
    # plain replacement: patches and statements contain braces, so str.format is unsafe
    for k, v in repls.items():
        text = text.replace("{" + k + "}", v)
    return text


class SWEBenchProMaxAdapter:
    def __init__(
        self,
        output_dir: Path,
        task_ids: list[str] | None = None,
        limit: int | None = None,
        overwrite: bool = False,
        data_dir: Path | None = None,
        languages: list[str] | None = None,
        agent_timeout: float = 7200.0,
        verifier_timeout: float = 7800.0,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.task_ids = task_ids
        self.limit = limit
        self.overwrite = overwrite
        self.data_dir = data_dir
        self.languages = [l.lower() for l in languages] if languages else None
        self.agent_timeout = agent_timeout
        self.verifier_timeout = verifier_timeout

    def selected(self) -> list[ProMaxRecord]:
        recs = [r for r in load_records(self.data_dir) if r.instance_id not in EXCLUDED]
        if self.task_ids:
            want = set(self.task_ids)
            recs = [r for r in recs if r.instance_id in want]
        if self.languages:
            recs = [r for r in recs if r.language.lower() in self.languages]
        return recs[: self.limit] if self.limit else recs

    def generate_task(self, rec: ProMaxRecord) -> Path:
        out = self.output_dir / rec.instance_id
        if out.exists():
            if not self.overwrite:
                return out
            shutil.rmtree(out)
        for sub in ("environment", "solution", "tests"):
            (out / sub).mkdir(parents=True, exist_ok=True)
        t = TEMPLATE_DIR
        lang = rec.language.lower()
        (out / "task.toml").write_text(
            _render(
                (t / "task.toml").read_text(),
                instance_id=rec.instance_id,
                task_name=task_name(rec.instance_id),
                base_commit=rec.base_commit,
                language=lang,
                repo=rec.repo,
                docker_image=rec.image_name,
                agent_timeout=f"{self.agent_timeout:.1f}",
                verifier_timeout=f"{self.verifier_timeout:.1f}",
            )
        )
        (out / "instruction.md").write_text(
            _render((t / "instruction.md").read_text(), problem_statement=rec.problem_statement.strip())
        )
        (out / "environment" / "Dockerfile").write_text(
            _render((t / "environment" / "Dockerfile").read_text(), docker_image=rec.image_name)
        )
        solve = out / "solution" / "solve.sh"
        solve.write_text(_render((t / "solution" / "solve.sh").read_text(), patch=rec.patch.rstrip("\n")))
        test = out / "tests" / "test.sh"
        shutil.copy(t / "tests" / "test.sh", test)
        (out / "tests" / "eval.sh").write_text(rec.eval_script)
        for p in (solve, test, out / "tests" / "eval.sh"):
            p.chmod(0o755)
        return out

    def run(self) -> None:
        recs = self.selected()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for r in recs:
            self.generate_task(r)
        print(f"Generated {len(recs)} tasks under {self.output_dir} (excluded: {len(EXCLUDED)})")
