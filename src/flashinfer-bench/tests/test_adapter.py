import hashlib
import json
import tomllib
from pathlib import Path

import pytest

from flashinfer_bench import adapter


@pytest.fixture
def source(monkeypatch, tmp_path):
    definition = {"name": "rmsnorm_h128", "reference": "def run(x): return x"}
    workload = {
        "definition": definition["name"],
        "workload": {"uuid": "one", "inputs": {"x": {"type": "random"}}},
        "solution": None,
        "evaluation": None,
    }
    baseline = {
        "name": "baseline_kernel",
        "definition": definition["name"],
        "author": "baseline",
        "sources": [{"path": "main.py", "content": "def run(x): return x"}],
    }
    files = {
        "definitions/rms.json": json.dumps(definition).encode(),
        "workloads/rms.jsonl": (json.dumps(workload) + "\n").encode(),
        "solutions/baseline/rms.json": json.dumps(baseline).encode(),
    }

    def git(repo, *args):
        if args[0] == "ls-tree":
            return "\n".join(files).encode()
        if args[0] == "show":
            return files[args[1].split(":", 1)[1]]
        raise AssertionError(args)

    monkeypatch.setattr(adapter, "git", git)
    monkeypatch.setattr(adapter, "source_repository", lambda path: tmp_path)
    return files


def test_lossless_inputs_stable_names_and_no_baseline_in_image(source, tmp_path):
    out = tmp_path / "out"
    report = adapter.FlashInferBenchAdapter(out).run()
    task = out / "rmsnorm-h128"
    config = tomllib.loads((task / "task.toml").read_text())
    assert config["version"] == "1.0"
    assert config["task"]["name"] == "flashinfer-ai/flashinfer-bench--rmsnorm-h128"
    assert config["environment"]["gpus"] == 1
    assert config["verifier"]["environment_mode"] == "separate"
    assert config["artifacts"] == ["/workspace/solution.json"]
    for relative in ("definitions/rms.json", "workloads/rms.jsonl"):
        assert (task / "environment/data" / relative).read_bytes() == source[relative]
        assert (task / "tests/data" / relative).read_bytes() == source[relative]
    assert not list((task / "environment").rglob("baseline.json"))
    assert not list(task.rglob("*.pyc"))
    assert (task / "tests/baseline.json").read_bytes() == source[
        "solutions/baseline/rms.json"
    ]
    before = {
        str(p.relative_to(task)): p.read_bytes() for p in task.rglob("*") if p.is_file()
    }
    adapter.FlashInferBenchAdapter(out, overwrite=True).run()
    assert before == {
        str(p.relative_to(task)): p.read_bytes() for p in task.rglob("*") if p.is_file()
    }
    assert report["selected"] == ["rmsnorm_h128"]


def test_explicit_exclusions(source, tmp_path):
    source["solutions/baseline/duplicate.json"] = source["solutions/baseline/rms.json"]
    eligible, excluded = adapter.FlashInferBenchAdapter(tmp_path / "out").inventory()
    assert not eligible
    assert "found 2" in excluded["rmsnorm_h128"]
    source.pop("workloads/rms.jsonl")
    _, excluded = adapter.FlashInferBenchAdapter(tmp_path / "out").inventory()
    assert excluded["rmsnorm_h128"] == "no released workloads"


def test_unknown_task_and_existing_output_fail(source, tmp_path):
    out = tmp_path / "out"
    with pytest.raises(KeyError, match="no-such-task"):
        adapter.FlashInferBenchAdapter(out, task_ids=["no-such-task"]).run()
    assert not out.exists()
    adapter.FlashInferBenchAdapter(out, task_ids=["rmsnorm-h128"]).run()
    with pytest.raises(FileExistsError):
        adapter.FlashInferBenchAdapter(out).run()
    with pytest.raises(ValueError, match="positive"):
        adapter.FlashInferBenchAdapter(out, limit=-1)


def test_pinned_blob_manifest(source, tmp_path):
    path = "blob/workloads/tensor.safetensors"
    digest = hashlib.sha256(b"tensor").hexdigest()
    source[path] = (
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{digest}\nsize 6\n".encode()
    )
    w = json.loads(source["workloads/rms.jsonl"])
    w["workload"]["inputs"]["x"] = {
        "type": "safetensors",
        "path": path,
        "tensor_key": "x",
    }
    source["workloads/rms.jsonl"] = json.dumps(w).encode()
    adapter.FlashInferBenchAdapter(tmp_path / "out").run()
    manifest = json.loads(
        (tmp_path / "out/rmsnorm-h128/tests/manifest.json").read_text()
    )
    assert manifest["blobs"] == {path: {"sha256": digest, "size": 6}}


def test_multiple_definitions_stop_on_first_generation_error(
    source, tmp_path, monkeypatch
):
    for size in (256, 512):
        for path, data in list(source.items()):
            if path.endswith(("rms.json", "rms.jsonl")):
                source[path.replace("rms.", f"rms{size}.")] = data.replace(
                    b"rmsnorm_h128", f"rmsnorm_h{size}".encode()
                )
    out = tmp_path / "out"
    job = adapter.FlashInferBenchAdapter(out, overwrite=True)
    assert job.run()["selected"] == ["rmsnorm_h128", "rmsnorm_h256", "rmsnorm_h512"]
    for size in (128, 256, 512):
        assert (out / f"rmsnorm-h{size}/task.toml").is_file()
    calls = []
    render = job.render

    def fail_second(task, name, entry):
        calls.append(name)
        if name == "rmsnorm_h256":
            raise OSError("disk write failed for rmsnorm_h256")
        render(task, name, entry)

    monkeypatch.setattr(job, "render", fail_second)
    with pytest.raises(OSError, match="disk write failed for rmsnorm_h256"):
        job.run()
    assert calls == ["rmsnorm_h128", "rmsnorm_h256"]
    assert not (out / "scope.json").exists()


def test_scope_cannot_silently_exclude_existing_tasks(source, tmp_path):
    out = tmp_path / "out"
    adapter.FlashInferBenchAdapter(out).run()
    old_scope = (out / "scope.json").read_bytes()
    leftover = out / "other-task"
    leftover.mkdir()
    (leftover / "task.toml").write_text('[task]\nname = "example/other-task"\n')
    with pytest.raises(ValueError, match="unselected tasks"):
        adapter.FlashInferBenchAdapter(out, overwrite=True).run()
    assert (out / "scope.json").read_bytes() == old_scope
    assert (leftover / "task.toml").exists()


def test_broken_destination_symlink_is_rejected(source, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "rmsnorm-h128").symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError):
        adapter.FlashInferBenchAdapter(out, overwrite=True).run()
    assert (out / "rmsnorm-h128").is_symlink()


def test_harbor_resolves_fresh_verifier_and_transfers_submission(source, tmp_path):
    """Exercise real Harbor config/artifact handling without starting Docker."""
    pytest.importorskip("harbor")
    import asyncio
    import logging

    from harbor.models.task.config import TaskConfig
    from harbor.models.task.paths import TaskPaths
    from harbor.models.task.verifier_mode import resolve_verifier_environment_definition
    from harbor.trial.artifact_handler import ArtifactHandler

    out = tmp_path / "out"
    adapter.FlashInferBenchAdapter(out).run()
    task = out / "rmsnorm-h128"
    config = TaskConfig.model_validate(tomllib.loads((task / "task.toml").read_text()))
    resolved = resolve_verifier_environment_definition(config, TaskPaths(task))
    assert resolved is not None
    assert resolved.directory == task / "environment"
    assert not resolved.bundled_tests  # Harbor must upload the pristine tests/.
    assert resolved.config == config.environment
    assert resolved.config is not config.environment
    artifacts = tmp_path / "artifacts"
    (artifacts / "workspace").mkdir(parents=True)
    (artifacts / "workspace/solution.json").write_text('{"submission": true}')
    # Undeclared files must not be uploaded into the verifier's runtime.
    (artifacts / "workspace/flashinfer_bench.py").write_text("raise RuntimeError()")
    uploads = {}

    class Environment:
        async def ensure_dirs(self, *args, **kwargs):
            pass

        async def upload_file(self, source_path, target_path):
            uploads[target_path] = source_path.read_text()

    asyncio.run(
        ArtifactHandler(
            artifacts=config.artifacts, logger=logging.getLogger(__name__)
        ).upload_artifacts(
            Environment(),
            artifacts_dir=artifacts,
            source_artifacts_dir=Path("/logs/artifacts"),
            target_artifacts_dir=Path("/logs/artifacts"),
        )
    )
    assert uploads == {"/workspace/solution.json": '{"submission": true}'}
