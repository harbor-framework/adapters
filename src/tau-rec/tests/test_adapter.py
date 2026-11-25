from __future__ import annotations

import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

import pytest
from conftest import ADAPTER_DIR, ROOT, generate
from tau_rec_adapter import adapter as adapter_module
from tau_rec_adapter import main as main_module
from tau_rec_adapter.adapter import TAU_REC_COMMIT, TauRecAdapter
from tau_rec_adapter.main import main


def run_main(argv: list[str]) -> None:
    main(["--tau-rec-root", str(ROOT), *argv])


SIDECAR = "movie-runtime"
SIDECAR_TRACE = "/var/lib/tau-rec/trace.json"
PIN = "8b4c3e6823add74f6c209fff864e2eae6849880c"
PYTHON_BASE = (
    "FROM python:3.12-slim@sha256:"
    "5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"
)


def test_generates_60_tasks(tmp_path):
    paths = generate(tmp_path)
    assert len(paths) == 60
    for p in paths:
        for f in [
            "task.toml",
            "instruction.md",
            "environment/Dockerfile",
            "environment/constraints.txt",
            "environment/docker-compose.yaml",
            "environment/runtime-server/task_config.json",
            "solution/solve.sh",
            "solution/oracle_plan.json",
            "tests/Dockerfile",
            "tests/test.sh",
            "tests/config.json",
        ]:
            assert (p / f).exists(), (p, f)
        assert json.loads((p / "tests/config.json").read_text()) == {"task_id": p.name}
        cfg = tomllib.loads((p / "task.toml").read_text())
        assert cfg["task"]["name"] == f"tau-rec/tau-rec__{p.name}"
        assert cfg["environment"]["mcp_servers"][0] == {
            "name": SIDECAR,
            "transport": "streamable-http",
            "url": f"http://{SIDECAR}:8000/mcp",
        }
    assert "<policy>" in (paths[0] / "instruction.md").read_text()
    assert not list(tmp_path.rglob("{*}"))  # every placeholder rendered


def test_cli_flags(tmp_path):  # --task-ids, --limit, --overwrite
    run_main(["--output-dir", str(tmp_path), "--task-ids", "task_001", "task_002"])
    assert sorted(os.listdir(tmp_path)) == ["task_001", "task_002"]
    with pytest.raises(SystemExit):  # exists, no --overwrite
        run_main(["--output-dir", str(tmp_path), "--task-ids", "task_001"])
    run_main(["--output-dir", str(tmp_path), "--task-ids", "task_001", "--overwrite"])
    assert len(generate(tmp_path / "b", limit=5)) == 5


def test_images_pin_base_tools_and_commit(tmp_path):
    p = generate(tmp_path, ["task_001"])[0]
    dockerfiles = {
        "main": p / "environment/Dockerfile",
        "runtime": p / "environment/runtime-server/Dockerfile",
        "verifier": p / "tests/Dockerfile",
    }
    for name, df in dockerfiles.items():
        text = df.read_text()
        froms = [line for line in text.splitlines() if line.startswith("FROM ")]
        assert froms == [PYTHON_BASE], name
        if name == "main":
            continue
        # tau-Rec from the tag, the build fails unless it is the pinned commit.
        assert "git clone --depth 1 --branch v2.1.0" in text, name
        assert f'test "$(git -C /opt/tau-rec rev-parse HEAD)" = {PIN}' in text, name
        assert "uv sync --frozen --project /opt/tau-rec" in text, name
        assert '"uv==0.13.8"' in text, name
    # Packages beyond the lock are installed under the captured constraints.
    assert '-c /tmp/constraints.txt "mcp==2.3.0"' in dockerfiles["main"].read_text()
    assert '-c /tmp/constraints.txt "fastmcp==4.1.2"' in (
        dockerfiles["runtime"].read_text()
    )
    pins = (p / "environment/constraints.txt").read_text().splitlines()
    pins = [line for line in pins if line and not line.startswith("#")]
    assert pins and all("==" in line and not line.startswith("-e") for line in pins), (
        pins
    )
    assert {"mcp==2.3.0", "fastmcp==4.1.2", "httpx2==2.16.0"} <= set(pins)


def test_task_env_requires_only_openai_api_key(tmp_path):
    # Harbor refuses to start a trial when a ``${VAR}`` template has no default
    # and VAR is unset on the host; only the user-simulator key is mandatory.
    import re

    p = generate(tmp_path, ["task_001"])[0]
    cfg = tomllib.loads((p / "task.toml").read_text())
    required = {
        m.group(1)
        for value in cfg["environment"]["env"].values()
        if (m := re.fullmatch(r"\$\{([^}:]+)(:-.*)?\}", value)) and m.group(2) is None
    }
    assert required == {"OPENAI_API_KEY"}
    # The scorer makes no model calls: the verifier gets no keys at all.
    assert "env" not in cfg["verifier"]
    assert "env" not in cfg["verifier"]["environment"]


def test_verifier_is_separate_and_reads_only_the_sidecar_artifact(tmp_path):
    """C2: the authoritative trace lives in the sidecar's own filesystem and
    reaches a separate verifier as a Harbor artifact; nothing is shared with
    main."""
    import yaml

    p = generate(tmp_path, ["task_001"])[0]
    cfg = tomllib.loads((p / "task.toml").read_text())
    assert cfg["artifacts"] == [{"source": SIDECAR_TRACE, "service": SIDECAR}]
    assert cfg["verifier"]["environment_mode"] == "separate"
    compose = yaml.safe_load((p / "environment/docker-compose.yaml").read_text())
    assert set(compose["services"]) == {"main", SIDECAR}
    assert "volumes" not in compose  # no named volume to share
    for name, service in compose["services"].items():
        assert "volumes" not in service, name
    assert compose["services"]["main"]["depends_on"] == {
        SIDECAR: {"condition": "service_healthy"}
    }
    test_sh = (p / "tests/test.sh").read_text()
    assert SIDECAR_TRACE in test_sh and "/logs/agent" not in test_sh
    assert test_sh.startswith("#!/bin/bash\n") and "set -euo pipefail" in test_sh
    # The grader runs with an absolute interpreter, never ``python`` from PATH.
    assert "PYTHON=/opt/tau-rec/.venv/bin/python" in test_sh
    assert "exec python" not in test_sh and "$(python" not in test_sh
    # The verifier image bundles tests/ itself (Harbor does not upload it).
    assert "COPY . /tests/" in (p / "tests/Dockerfile").read_text()


# Agent-visible text must not name the benchmark (checklist 14b).
BENCHMARK_NAME = re.compile(r"tau[-_ ]?rec|τ", re.IGNORECASE)


def test_main_image_and_agent_visible_files_carry_no_gold_or_benchmark_name(
    tmp_path,
):
    """C1/I2: the agent's container is built from environment/Dockerfile alone
    (plus constraints.txt); instruction.md and the MCP server entry are what an
    agent is shown. None of them carries gold data or names the benchmark."""
    paths = generate(tmp_path)
    answers = json.loads((ROOT / "data" / "answers.json").read_text())
    for p in paths:
        main_df = (p / "environment/Dockerfile").read_text()
        copies = re.findall(r"^(?:COPY|ADD)\s+(.*)$", main_df, re.MULTILINE)
        assert copies == ["constraints.txt /tmp/constraints.txt"], copies
        assert "git clone" not in main_df and "/opt/" not in main_df
        assert "ENV" not in main_df  # no benchmark env vars
        cfg = tomllib.loads((p / "task.toml").read_text())
        visible = {
            "environment/Dockerfile": main_df,
            "environment/constraints.txt": (
                p / "environment/constraints.txt"
            ).read_text(),
            "instruction.md": (p / "instruction.md").read_text(),
            "mcp_servers": json.dumps(cfg["environment"]["mcp_servers"]),
        }
        gold = {
            *answers[p.name]["reachable_solutions"],
            *answers[p.name]["constraint_solutions"],
        }
        for name, text in visible.items():
            assert not BENCHMARK_NAME.search(text), (p.name, name)
            assert p.name not in text, (p.name, name)  # the upstream task id
            assert not any(item in text for item in gold), (p.name, name)
            assert "answers" not in text, (p.name, name)
        assert "simulated" not in visible["instruction.md"]


def test_run_writes_under_output_dir(tmp_path):
    """Harbor's adapter contract: __init__(output_dir, limit, overwrite,
    task_ids, ...) and run() writing under self.output_dir."""
    out = tmp_path / "nested" / "out"  # created by run()
    adapter = TauRecAdapter(out, limit=2, tau_rec_root=ROOT)
    assert adapter.output_dir == out
    paths = adapter.run()
    assert paths == [out / "task_001", out / "task_002"]
    assert sorted(os.listdir(out)) == ["task_001", "task_002"]
    with pytest.raises(ValueError, match="task_999"):
        TauRecAdapter(out, task_ids=["task_999"], tau_rec_root=ROOT).run()


def test_default_output_dir_is_datasets_tau_rec(tmp_path, monkeypatch):
    repo_root = ADAPTER_DIR.parents[1]
    assert main_module.DEFAULT_OUTPUT_DIR == repo_root / "datasets" / "tau-rec"
    # main() without --output-dir writes to DEFAULT_OUTPUT_DIR.
    monkeypatch.setattr(main_module, "DEFAULT_OUTPUT_DIR", tmp_path / "default")
    run_main(["--task-ids", "task_003"])
    assert os.listdir(tmp_path / "default") == ["task_003"]


def test_root_comes_from_env_when_not_given(tmp_path, monkeypatch):
    monkeypatch.setenv("TAU_REC_ROOT", str(ROOT))
    main(["--output-dir", str(tmp_path), "--limit", "1"])
    assert os.listdir(tmp_path) == ["task_001"]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def test_rejects_a_checkout_not_at_the_pinned_commit(tmp_path):
    fake = tmp_path / "tau-rec"
    (fake / "data" / "tasks").mkdir(parents=True)
    (fake / "data" / "tasks" / "task_001.json").write_text("{}")
    # Not a git checkout at all.
    with pytest.raises(ValueError, match="not a git checkout"):
        TauRecAdapter(tmp_path / "out", tau_rec_root=fake)
    # A git checkout at another commit.
    _git(fake, "init", "-q")
    _git(fake, "add", ".")
    _git(fake, "commit", "-q", "-m", "not v2.1.0")
    with pytest.raises(ValueError, match=TAU_REC_COMMIT):
        TauRecAdapter(tmp_path / "out", tau_rec_root=fake)
    with pytest.raises(SystemExit) as exit_info:
        main(["--output-dir", str(tmp_path / "out"), "--tau-rec-root", str(fake)])
    assert "pinned to tau-Rec v2.1.0" in str(exit_info.value.code)
    assert not (tmp_path / "out").exists()
    # Not a tau-Rec checkout.
    with pytest.raises(ValueError, match="no data/tasks"):
        TauRecAdapter(tmp_path / "out", tau_rec_root=tmp_path / "nowhere")
    # The real pinned checkout passes.
    assert adapter_module.checkout_commit(ROOT) == TAU_REC_COMMIT


def test_clones_the_pinned_tag_when_no_root_is_given(tmp_path, monkeypatch):
    """No --tau-rec-root and no $TAU_REC_ROOT: shallow-clone v2.1.0 into the
    adapter cache, then verify it like any other checkout."""
    monkeypatch.delenv("TAU_REC_ROOT", raising=False)
    monkeypatch.setattr(adapter_module, "ADAPTER_ROOT", tmp_path)
    clones, verified = [], []

    def fake_run(command, check):
        clones.append(command)
        Path(command[-1]).mkdir(parents=True)

    monkeypatch.setattr(adapter_module.subprocess, "run", fake_run)
    monkeypatch.setattr(adapter_module, "verify_checkout", verified.append)
    adapter_module.resolve_tau_rec_root()
    cache = (tmp_path / ".cache" / "tau-rec").resolve()
    assert clones == [
        [
            "git", "clone", "--depth", "1", "--branch", "v2.1.0",
            "https://github.com/nbharaths/tau-rec", str(cache),
        ]
    ]  # fmt: skip
    assert verified == [cache]
    # An existing cache is reused (and still verified), not re-cloned.
    adapter_module.resolve_tau_rec_root()
    assert len(clones) == 1 and verified == [cache, cache]
