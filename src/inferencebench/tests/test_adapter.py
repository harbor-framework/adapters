"""Tests that run without a GPU, a container runtime, or API keys.

uv run --with pytest --with pytest-asyncio --with harbor==0.25.0 pytest tests/
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tomllib
import types
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from inferencebench import adapter as adapter_module
from inferencebench import score
from inferencebench.adapter import InferenceBenchAdapter

TEMPLATE = Path(__file__).parents[1] / "src" / "inferencebench" / "task-template"
FIRST_TASK = "inferencebench-a-mistral-7b-21-1337"
SCENARIO_TASKS = {
    "a": "inference_scenario_a_input_heavy",
    "b": "inference_scenario_b_output_heavy",
    "c": "inference_scenario_c_high_load",
    "d": "inference_scenario_d_general",
}
PLACEHOLDER = re.compile(r"(?<!\$)\{[a-z_]+\}")
# The scripts target bash 5 with GNU tools. These stand-ins let the harnesses below also run
# under bash 3.2 with BSD tools.
SHELL_COMPAT = """
if ! type mapfile > /dev/null 2>&1; then
    mapfile() { local line; lines=(); while IFS= read -r line || [ -n "${line}" ]; do lines+=("${line}"); done; }
fi
if [ "$(uname)" = Darwin ]; then
    stat() { case "$2" in %s) /usr/bin/stat -f %z "$3" ;; %a) /usr/bin/stat -f %Lp "$3" ;; esac; }
fi
"""


@pytest.fixture(scope="module")
def tasks(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("tasks")
    InferenceBenchAdapter(output).run()
    return output


@pytest.fixture(scope="module")
def upstream(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The pinned upstream checkout that the adapter uses by default."""
    return InferenceBenchAdapter(tmp_path_factory.mktemp("unused")).upstream


def shell_function(script: str, name: str) -> str:
    """Return the source of one top-level function of a shell script."""
    start = script.index(f"\n{name}() {{\n") + 1
    return script[start : script.index("\n}\n", start) + 3]


def bash(harness: str, check: bool = False, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", harness], check=check, capture_output=True, text=True, **kwargs)


def test_generates_twelve_tasks_with_stable_unique_names(tasks: Path) -> None:
    names = sorted(
        tomllib.loads((path / "task.toml").read_text())["task"]["name"] for path in tasks.iterdir()
    )
    assert len(set(names)) == 12
    assert names[0] == "aisa-group/inferencebench-a-mistral-7b-21-1337"
    assert names[-1] == "aisa-group/inferencebench-d-mistral-7b-999-777"


def test_limit_and_task_ids(tmp_path: Path) -> None:
    InferenceBenchAdapter(tmp_path / "limit", limit=2).run()
    assert len(list((tmp_path / "limit").iterdir())) == 2
    task_id = "inferencebench-c-mistral-7b-248-428"
    InferenceBenchAdapter(tmp_path / "ids", task_ids=[task_id]).run()
    assert [path.name for path in (tmp_path / "ids").iterdir()] == [task_id]
    with pytest.raises(ValueError):
        InferenceBenchAdapter(tmp_path / "bad", task_ids=["nope"]).run()


def test_no_unrendered_placeholders(tasks: Path) -> None:
    for name in (
        "task.toml",
        "environment/Dockerfile",
        "solution/solve.sh",
        "solution/pytorch_reference.sh",
        "instruction.md",
    ):
        placeholders = set(PLACEHOLDER.findall((TEMPLATE / name).read_text()))
        assert placeholders, name
        for task in tasks.iterdir():
            left = placeholders & set(PLACEHOLDER.findall((task / name).read_text()))
            assert not left, (task.name, name, left)


def test_a_failed_generation_leaves_no_partial_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = InferenceBenchAdapter(tmp_path, task_ids=[FIRST_TASK])
    monkeypatch.setattr(adapter, "write_tests", Mock(side_effect=RuntimeError("disk full")))
    with pytest.raises(RuntimeError):
        adapter.run()
    assert list(tmp_path.iterdir()) == []
    InferenceBenchAdapter(tmp_path, task_ids=[FIRST_TASK]).run()
    assert (tmp_path / FIRST_TASK / "tests" / "test.sh").is_file()


@pytest.mark.parametrize("value", ["0", "0.0001", "-1", "nan", "inf", "2h", " 2", ""])
def test_the_time_budget_must_be_a_positive_number(tmp_path: Path, value: str) -> None:
    with pytest.raises(ValueError):
        InferenceBenchAdapter(tmp_path, num_hours=value)


def test_task_config(tasks: Path) -> None:
    config = tomllib.loads((tasks / "inferencebench-b-mistral-7b-248-428" / "task.toml").read_text())
    assert config["environment"]["gpus"] == 1
    assert config["environment"]["gpu_types"] == ["H100!", "H100"]
    assert config["verifier"]["env"]["ANTHROPIC_BASE_URL"] == "${ANTHROPIC_BASE_URL:-}"
    assert config["agent"]["user"] == "agent"
    assert config["agent"]["timeout_sec"] == 7200.0
    assert config["verifier"]["environment_mode"] == "shared"
    assert config["environment"]["env"]["INFERENCE_BENCH_DATASET_SEED"] == "248"
    assert config["environment"]["env"]["BASH_MAX_TIMEOUT_MS"] == "36000000"
    assert config["verifier"]["env"]["INFERENCE_BENCH_DATASET_SEED"] == "428"
    assert config["verifier"]["env"]["INFERENCE_BENCH_JUDGE"] == "${INFERENCE_BENCH_JUDGE:-required}"
    assert config["verifier"]["collect"][0]["command"].startswith("/bin/bash ")
    healthcheck = config["environment"]["healthcheck"]["command"]
    # The evaluator's tokenizer cache, which test.sh requires.
    assert "python3 /usr/local/lib/inferencebench/download_model.py && " in healthcheck
    assert 'EVAL_HUB = "/opt/ib_eval_hf/hub"\n' in (TEMPLATE / "environment" / "download_model.py").read_text()
    assert "EVAL_HF=/opt/ib_eval_hf\n" in (TEMPLATE / "tests" / "test.sh").read_text()
    # The model repository is pinned to a commit, and the task says which.
    revision = config["environment"]["env"]["INFERENCE_BENCH_MODEL_REVISION"]
    assert re.fullmatch(r"[0-9a-f]{40}", revision)
    assert config["metadata"]["model_revision"] == revision
    assert config["metadata"]["upstream_commit"] == adapter_module.UPSTREAM_COMMIT
    # User agent can never write a reward, whether or not the verifier's scripts run.
    assert "chown root:root /logs/verifier && chmod 700 /logs/verifier && date +%s > /timer_start" in healthcheck


def test_agent_image_has_no_evaluation_seed_or_verifier_files(tasks: Path) -> None:
    env = tasks / FIRST_TASK / "environment"
    assert "1337" not in (env / "Dockerfile").read_text()
    for path in (env / "home").rglob("*"):
        if path.is_file():
            assert "1337" not in path.read_text(errors="ignore"), path
    assert not list(env.rglob("test.sh"))
    assert not list(env.rglob("solve.sh"))


def test_root_commands_do_not_resolve_through_the_agents_directory(tasks: Path) -> None:
    dockerfile = (tasks / FIRST_TASK / "environment" / "Dockerfile").read_text()
    final_path = [line for line in dockerfile.splitlines() if line.startswith("ENV PATH=")][-1]
    assert final_path.index("/usr/bin") < final_path.index("/home/agent/.local/bin")
    # No later ENV line may reorder it.
    assert dockerfile.rindex('ENV PATH="') == dockerfile.index(final_path)
    for name in ("environment/collect.sh", "tests/test.sh"):
        script = (tasks / FIRST_TASK / name).read_text()
        assert 'export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' in script
        assert "cd /\n" in script
        # Both stop the agent's processes with the helper that the image ships.
        assert "source /usr/local/lib/inferencebench/agent_processes.sh\n" in script
    assert "COPY agent_processes.sh download_model.py /usr/local/lib/inferencebench/\n" in dockerfile
    # Files that Harbor uploads with the host user's uid do not belong to user agent.
    assert "--uid 1000 agent" in dockerfile
    assert dockerfile.index("usermod -u 64321 agent") < dockerfile.rindex("chown -R agent:agent /home/agent")


def test_the_verifier_takes_over_its_files_before_it_uses_them(tasks: Path) -> None:
    script = (tasks / FIRST_TASK / "tests" / "test.sh").read_text()
    main = script[script.index('echo "=== InferenceBench verifier') :]
    steps = [
        "kill_agent_processes ||",
        'chown root:root "${LOGS}" && chmod 700 "${LOGS}"',
        "chown -R -h root:root /tests && chmod -R go-rwx /tests",
        '[ -f "${STATE}/complete" ]',
        'no_reward "INFERENCE_BENCH_JUDGE must be required or off',
        'source "${IB}/src/disallowed_usage_judge/judge.sh"',
        # A GPU that does not answer cannot hold up the verifier.
        '/usr/bin/timeout --kill-after=10s 300s \\\n    python3 -I /tests/record_environment.py "${LOGS}/environment.json"',
        "run_judge",
        'python3 /tests/snapshot.py "${TASK}" "${LOGS}/task"',
        'chmod -R a-s,go-w "${LOGS}/task"',
        'if [ "${JUDGE_STATE}" = no_credential ]; then',
        "elif start_server; then",
        "stop_server ||",
        'PYTHONPATH="${IB}:${PYTHONPATH}" python3 /tests/write_reward.py',
        # Whatever write_reward.py did, a trial without a valid judge has no reward file.
        'rm -f "${LOGS}/reward.json" "${LOGS}/reward.txt"\n    echo "[ungraded]',
    ]
    positions = [main.index(step) for step in steps]
    assert positions == sorted(positions)
    # The agent's launcher and the judge cannot gain privileges from a set-user-ID file.
    assert script.count("/usr/bin/setpriv --no-new-privs --reuid=agent --regid=agent --clear-groups") == 2
    assert "eval_seed" not in script


def test_judge_prompt_points_at_the_copy(tasks: Path) -> None:
    prompt = (tasks / FIRST_TASK / "tests" / "ib" / "src" / "disallowed_usage_judge" / "prompt.txt").read_text()
    assert "/home/agent" not in prompt
    assert "mounted read-only at /var/lib/ib_judge/task" in prompt
    assert "Write /var/lib/ib_judge/contamination_judgement.txt" in prompt
    assert f"JUDGE_HOME={adapter_module.JUDGE_HOME}\n" in (tasks / FIRST_TASK / "tests" / "test.sh").read_text()


def test_scripts_parse(tasks: Path) -> None:
    task = tasks / FIRST_TASK
    for name in (
        "environment/collect.sh",
        "environment/agent_processes.sh",
        "tests/test.sh",
        "solution/solve.sh",
        "solution/pytorch_reference.sh",
    ):
        subprocess.run(["bash", "-n", str(task / name)], check=True)


def test_oracle_loads_upstreams_vllm_shims(tasks: Path) -> None:
    task = tasks / FIRST_TASK
    shims = (task / "solution" / "vllm_runtime_shims.py").read_text()
    # vLLM 0.11.0 reads this attribute, and transformers 5 no longer has it.
    assert "all_special_tokens_extended" in shims
    site = "home/task/.local/lib/python3.10/site-packages/sitecustomize.py"
    assert f"cat /solution/vllm_runtime_shims.py >> /home/agent/{site.removeprefix('home/')}\n" in (
        task / "solution" / "solve.sh"
    ).read_text()
    # The launcher puts this directory first on PYTHONPATH.
    assert "/home/agent/task/.local/lib/python3.10/site-packages:" in (task / "solution" / "start_server.sh").read_text()
    compile((task / "environment" / site).read_text() + shims, "sitecustomize.py", "exec")


def test_the_healthcheck_caches_the_pinned_revision_under_the_models_name(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def snapshot_download(model, revision, cache_dir, ignore_patterns):
        calls.append((model, revision, cache_dir, ignore_patterns))
        snapshot = Path(cache_dir or tmp_path / "agent") / "models--org--name" / "snapshots" / revision
        snapshot.mkdir(parents=True)
        return str(snapshot)

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=snapshot_download))
    spec = importlib.util.spec_from_file_location("download_model", TEMPLATE / "environment" / "download_model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "EVAL_HUB", str(tmp_path / "evaluator"))
    revision = adapter_module.MODEL_REVISIONS["mistralai/Mistral-7B-Instruct-v0.3"]
    monkeypatch.setenv("INFERENCE_BENCH_BASE_MODEL", "org/name")
    monkeypatch.setenv("INFERENCE_BENCH_MODEL_REVISION", revision)
    module.main()
    # The agent's cache gets every file, and the evaluator's cache everything but the weights.
    assert calls == [
        ("org/name", revision, None, None),
        ("org/name", revision, str(tmp_path / "evaluator"), module.WEIGHTS),
    ]
    assert "*.safetensors" in module.WEIGHTS
    # A lookup by name reads refs/main, as after a download of the main branch.
    for cache in ("agent", "evaluator"):
        assert (tmp_path / cache / "models--org--name" / "refs" / "main").read_text() == revision


def test_the_manifest_records_what_the_task_pins(tasks: Path) -> None:
    task = tasks / "inferencebench-c-mistral-7b-999-777"
    manifest = json.loads((task / "tests" / "manifest.json").read_text())
    assert manifest["task"] == task.name
    assert manifest["seeds"] == {"development": "999", "evaluation": "777", "quality": "248"}
    assert manifest["upstream"]["commit"] == adapter_module.UPSTREAM_COMMIT
    assert manifest["model_revision"] == adapter_module.MODEL_REVISIONS[manifest["base_model"]]
    assert manifest["timeouts_sec"]["agent"] == 7200.0 and manifest["timeouts_sec"]["verifier"] == 43200.0
    assert len(manifest["files_sha256"]) == 5
    for name, digest in manifest["files_sha256"].items():
        assert hashlib.sha256((task / name).read_bytes()).hexdigest() == digest, name
    # The image build checks the same sample checksums.
    dockerfile = (task / "environment" / "Dockerfile").read_text()
    for name, digest in manifest["samples_sha256"].items():
        assert f'echo "{digest}  {name}" | sha256sum -c -' in dockerfile
    # The agent's image does not get the manifest, which names the evaluation seed.
    assert not list((task / "environment").rglob("manifest.json"))


def test_another_checkout_is_recorded_under_its_own_commit(tmp_path: Path, upstream: Path) -> None:
    copy = tmp_path / "upstream"
    adapter_module.shutil.copytree(upstream, copy, ignore=adapter_module.shutil.ignore_patterns(".git"))
    adapter = InferenceBenchAdapter(tmp_path / "tasks", task_ids=[FIRST_TASK], upstream_dir=copy)
    assert adapter.upstream_commit == "unknown"
    assert InferenceBenchAdapter(tmp_path / "tasks", upstream_dir=upstream).upstream_commit == adapter_module.UPSTREAM_COMMIT


def git_repository(path: Path) -> str:
    path.mkdir(parents=True)
    (path / "src").mkdir()
    (path / "src" / "run_task.sh").write_text("#!/bin/bash\n")
    for command in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "x"],
    ):
        subprocess.run(command, cwd=path, check=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True, check=True).stdout.strip()


def test_a_modified_checkout_is_not_recorded_as_its_commit(tmp_path: Path) -> None:
    commit = git_repository(tmp_path / "repo")
    assert adapter_module.checkout_commit(tmp_path / "repo") == commit
    (tmp_path / "repo" / "src" / "new.py").write_text("")
    assert adapter_module.checkout_commit(tmp_path / "repo") == f"{commit}-dirty"
    (tmp_path / "repo" / "src" / "new.py").unlink()
    (tmp_path / "repo" / "src" / "run_task.sh").write_text("changed\n")
    assert adapter_module.checkout_commit(tmp_path / "repo") == f"{commit}-dirty"
    # A directory inside a checkout is not a checkout of its own.
    assert adapter_module.checkout_commit(tmp_path / "repo" / "src") == "unknown"


def test_the_cached_checkout_must_be_the_pinned_commit(tmp_path: Path) -> None:
    found = git_repository(tmp_path / adapter_module.UPSTREAM_COMMIT)
    with pytest.raises(RuntimeError, match=f"found {found}"):
        adapter_module.fetch_upstream(tmp_path)


def test_the_environment_record_survives_a_machine_without_the_sandbox(tasks: Path, tmp_path: Path) -> None:
    """Every probe may fail, and no credential is copied."""
    output = tmp_path / "environment.json"
    env = {
        "PATH": os.environ["PATH"],
        "INFERENCE_BENCH_BASE_MODEL": "mistralai/Mistral-7B-Instruct-v0.3",
        "INFERENCE_BENCH_DATASET_SEED": "1337",
        "INFERENCE_BENCH_PROXY_API_KEY": "sk-secret",
        "ANTHROPIC_API_KEY": "sk-secret",
        "CLAUDE_CODE_OAUTH_TOKEN": "sk-secret",
        "HF_TOKEN": "hf-secret",
        "NUM_HOURS": "2",
        "JUDGE_MODEL": "claude-sonnet-4-6",
        "JUDGE_ATTEMPTS": "3",
        "JUDGE_TIMEOUT": "15m",
        "EVAL_DEADLINE": "1800000000",
        "MODAL_REGION": "us-east",
    }
    script = tasks / FIRST_TASK / "tests" / "record_environment.py"
    subprocess.run([sys.executable, "-I", str(script), str(output)], env=env, check=True, capture_output=True)
    text = output.read_text()
    assert "secret" not in text
    record = json.loads(text)
    assert record["environment_variables"] == {
        "INFERENCE_BENCH_BASE_MODEL": "mistralai/Mistral-7B-Instruct-v0.3",
        "INFERENCE_BENCH_DATASET_SEED": "1337",
        "NUM_HOURS": "2",
    }
    assert record["provider"] == {"MODAL_REGION": "us-east"}
    assert record["judge"]["model"] == "claude-sonnet-4-6" and record["judge"]["timeout"] == "15m"
    assert record["timing"]["evaluation_deadline_unix"] == 1800000000
    assert record["image"]["python"] == sys.version.split()[0]
    # None of these exists on the machine that runs the tests.
    for missing in (record["task"], record["evaluator_model"], record["agent_model_cache"]):
        assert set(missing) == {"error"}


def test_the_environment_record_reads_the_model_caches(tasks: Path, tmp_path: Path, monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location("record_environment", tasks / FIRST_TASK / "tests" / "record_environment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    revision = "c" * 40
    monkeypatch.setenv("INFERENCE_BENCH_BASE_MODEL", "org/name")
    for cache in ("evaluator", "agent"):
        root = tmp_path / cache / "models--org--name"
        (root / "snapshots" / revision).mkdir(parents=True)
        (root / "blobs").mkdir()
    root = tmp_path / "evaluator" / "models--org--name"
    (root / "refs").mkdir()
    (root / "refs" / "main").write_text(revision)
    (root / "blobs" / "abc123").write_text("{}")
    (root / "snapshots" / revision / "tokenizer.json").symlink_to("../../blobs/abc123")
    # Something that is not a commit, in the cache that the agent can write.
    (tmp_path / "agent" / "models--org--name" / "snapshots" / "not-a-commit").mkdir()
    site = tmp_path / "site"
    for name in ("vllm-0.11.0.dist-info", "torch-2.8.0+cu128.dist-info", "$(reboot).dist-info", "vllm"):
        (site / name).mkdir(parents=True)
    monkeypatch.setattr(module, "EVAL_HUB", tmp_path / "evaluator")
    monkeypatch.setattr(module, "AGENT_HUB", tmp_path / "agent")
    monkeypatch.setattr(module, "AGENT_SITE", site)
    assert module.evaluator_model() == {"revision": revision, "files": {"tokenizer.json": "abc123"}}
    assert module.agent_model_cache() == {"snapshots": [revision]}
    assert module.server_python_packages() == {"torch": "2.8.0+cu128", "vllm": "0.11.0"}
    # A listing reads at most MAX_ENTRIES names, however many the agent made.
    monkeypatch.setattr(module, "MAX_ENTRIES", 2)
    assert len(module.server_python_packages()) <= 2
    assert module.tree_sha256(site) == {"files": 0, "sha256": hashlib.sha256().hexdigest()}


def test_the_environment_record_parses_what_nvidia_smi_prints(tasks: Path, tmp_path: Path, monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location("record_environment", tasks / FIRST_TASK / "tests" / "record_environment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fake = tmp_path / "nvidia-smi"
    fake.write_text(
        "#!/bin/bash\n"
        'if [ $# -gt 0 ]; then echo "0, NVIDIA H100 80GB HBM3, 81559, 550.54.15, 96.00.89.00.01"; exit 0; fi\n'
        'echo "| NVIDIA-SMI 550.54.15    Driver Version: 550.54.15    CUDA Version: 12.4     |"\n'
    )
    fake.chmod(0o755)
    monkeypatch.setattr(module, "NVIDIA_SMI", ("/nonexistent/nvidia-smi", str(fake)))
    assert module.gpus() == {
        "devices": [
            {
                "index": "0",
                "name": "NVIDIA H100 80GB HBM3",
                "memory_total_mib": "81559",
                "driver_version": "550.54.15",
                "vbios_version": "96.00.89.00.01",
            }
        ],
        "driver_cuda_version": "12.4",
    }
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("processor\t: 0\nmodel name\t: Intel(R) Xeon(R) Platinum 8480+\nprocessor\t: 1\n")
    assert module.search(r"^model name\s*:\s*(.+)$", str(cpuinfo)) == "Intel(R) Xeon(R) Platinum 8480+"
    assert module.search(r"^MemTotal:\s*(\d+) kB$", str(cpuinfo)) is None


def test_the_pytorch_reference_follows_upstreams_torch_baseline(tasks: Path, upstream: Path) -> None:
    solution = tasks / FIRST_TASK / "solution"
    script = (solution / "pytorch_reference.sh").read_text()
    # The package list and its lock are those of upstream's torch baseline container.
    definition = (upstream / "containers" / "inference_baselines_torch.def").read_text()
    packages = re.search(r"--constraint /solution/torch-constraints\.txt (.+)\n", script)[1].split()
    assert "torch==2.10.0" in packages and "transformers==5.2.0" in packages and len(packages) == 9
    assert all(f"        {package}" in definition for package in packages)
    assert (solution / "torch-constraints.txt").read_bytes() == (
        upstream / "containers" / "locks" / "inference_baselines_torch.txt"
    ).read_bytes()
    # Upstream's server and procedure, unchanged, at the concurrency upstream uses for torch.
    for name in adapter_module.REFERENCE_FILES:
        assert (solution / "ib" / "src" / "eval" / "inference" / name).read_bytes() == (
            upstream / "src" / "eval" / "inference" / name
        ).read_bytes()
    assert "-m src.eval.inference.servers.transformers_openai_server " in script
    assert "-m src.eval.inference.precompute_quality_baseline " in script
    assert "--backend torch" in script and "--concurrency 1\n" in script
    assert '"--concurrency", "1" if backend == "torch"' in (
        upstream / "src" / "eval" / "inference" / "precompute_all_baselines.py"
    ).read_text()
    # The questions are the cached set whose checksum the image build verifies.
    assert (
        'SAMPLES="/opt/inference_eval/baselines/samples/mmlu_pro/'
        '${INFERENCE_BENCH_QUALITY_SEED}_${INFERENCE_BENCH_QUALITY_MMLUPRO_N}/samples.jsonl"'
    ) in script
    assert 'INFERENCE_BENCH_QUALITY_MMLUPRO_SAMPLES_FILE="${SAMPLES}"' in script
    # The packages go into a virtual environment of their own, with the user install turned off,
    # and the server and the procedure run with its Python.
    assert script.index("unset PIP_USER PYTHONUSERBASE\n") < script.index('python3 -m venv "${VENV}"\n')
    assert '"${PY}" -m pip install' in script and '"${PY}" -m pip freeze' in script
    assert '"${PY}" -u -m src.eval.inference.servers.transformers_openai_server' in script
    assert '"${PY}" -u -m src.eval.inference.precompute_quality_baseline' in script
    assert script.index('"${PY}" /solution/pytorch_provenance.py') < script.index("transformers_openai_server")


def test_the_pytorch_reference_stops_on_cuda_libraries_from_elsewhere(tasks: Path) -> None:
    spec = importlib.util.spec_from_file_location("provenance", tasks / FIRST_TASK / "solution" / "pytorch_provenance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    venv = "/tmp/ib_pytorch_reference"
    site = f"{venv}/lib/python3.10/site-packages/nvidia"
    maps = "\n".join(
        f"7f0000000000-7f0000001000 r-xp 00000000 fd:01 1234                       {path}"
        for path in (
            f"{site}/cublas/lib/libcublas.so.12",
            f"{site}/cublas/lib/libcublasLt.so.12",
            f"{site}/cudnn/lib/libcudnn.so.9",
            f"{site}/cudnn/lib/libcudnn_graph.so.9",
            f"{site}/cuda_runtime/lib/libcudart.so.12",
            "/usr/lib/x86_64-linux-gnu/libcuda.so.535.104.05",
            f"{site}/cublas/lib/libcublas.so.12",
        )
    )
    libraries = module.cuda_libraries(maps)
    assert [path.rsplit("/", 1)[1] for path in libraries] == [
        "libcublas.so.12",
        "libcublasLt.so.12",
        "libcudart.so.12",
        "libcudnn.so.9",
    ]
    assert module.foreign(libraries, venv) == []
    # cuBLAS from the base image's CUDA toolkit instead of the locked wheel.
    system = "/usr/local/cuda/lib64/libcublas.so.12"
    assert module.foreign([*libraries, system], venv) == [system]
    assert module.foreign([f"{venv}-other/lib/libcublas.so.12"], venv) == [f"{venv}-other/lib/libcublas.so.12"]


@pytest.mark.parametrize(("oracle", "status"), [("bogus", 2), ("pytorch-reference", 127)])
def test_the_oracle_variant_is_chosen_before_anything_is_installed(tasks: Path, tmp_path: Path, oracle, status) -> None:
    # A stand-in for python3 shows whether solve.sh got as far as installing vLLM.
    (tmp_path / "python3").write_text(f"#!/bin/bash\ntouch '{tmp_path}/installed'\n")
    (tmp_path / "python3").chmod(0o755)
    script = (tasks / FIRST_TASK / "solution" / "solve.sh").read_text()
    assert "exec /bin/bash /solution/pytorch_reference.sh" in script
    script = script.replace("exec /bin/bash /solution/pytorch_reference.sh", "exit 127")
    result = bash(script, env={"PATH": f"{tmp_path}:{os.environ['PATH']}", "INFERENCE_BENCH_ORACLE": oracle})
    assert result.returncode == status
    assert not (tmp_path / "installed").exists()


def run_kill_helper(alive_passes: int, state: str = "S") -> subprocess.CompletedProcess:
    helper = (TEMPLATE / "environment" / "agent_processes.sh").read_text()
    # Do not signal anything on the machine that runs the tests.
    helper = helper.replace("/usr/bin/env -i /usr/bin/setpriv", "true")
    return bash(
        f"""
count=$(mktemp)
ps() {{ echo x >> "$count"; [ "$(wc -l < "$count")" -gt {alive_passes} ] || echo "{state}"; }}
pkill() {{ :; }}
sleep() {{ :; }}
{helper}
kill_agent_processes
echo "rc=$? passes=$(wc -l < "$count" | tr -d ' ')"
"""
    )


def test_stopping_the_agents_processes_is_checked_and_retried() -> None:
    assert run_kill_helper(0).stdout.splitlines()[-1] == "rc=0 passes=1"
    assert run_kill_helper(3).stdout.splitlines()[-1] == "rc=0 passes=4"
    assert run_kill_helper(3, state="Z").stdout.splitlines()[-1] == "rc=0 passes=1"
    failed = run_kill_helper(10**6).stdout.splitlines()
    assert failed[0] == "processes of user agent survived 40 kill passes:"
    assert failed[-1].startswith("rc=1 ")


def test_restore_tmp_puts_back_names_that_start_with_a_dot(tmp_path: Path) -> None:
    script = (TEMPLATE / "tests" / "test.sh").read_text()
    restore = shell_function(script, "restore_tmp")
    restore = restore.replace('"/tmp/', '"${DEST}/').replace(" /tmp/ ", ' "${DEST}/" ')
    saved, dest = tmp_path / "state" / "tmp", tmp_path / "dest"
    (saved / ".venv").mkdir(parents=True)
    (saved / ".venv" / "python").write_text("new")
    (saved / "engine").mkdir()
    (dest / ".venv").mkdir(parents=True)
    (dest / ".venv" / "stale").write_text("old")
    result = bash(f"STATE={tmp_path / 'state'}; DEST={dest}; chown() {{ :; }}\n{restore}\nrestore_tmp", check=True)
    assert result.returncode == 0
    assert sorted(path.name for path in dest.iterdir()) == [".venv", "engine"]
    assert [path.name for path in (dest / ".venv").iterdir()] == ["python"]


def run_judge(
    tasks: Path, root: Path, fake_judge: str, credential: bool = True, killable: bool = True, mode: str = "required"
) -> subprocess.CompletedProcess:
    """Run test.sh's judge step in a scratch tree with a stand-in for the judge CLI."""
    script = (tasks / FIRST_TASK / "tests" / "test.sh").read_text()
    home = root / "home" / "agent"
    (home / "task").mkdir(parents=True)
    (home / "task" / "start_server.sh").write_text("#!/bin/bash\nexec python3 -m vllm.entrypoints.openai.api_server\n")
    (home / ".local").mkdir()
    (home / ".local" / "installed").write_text("the agent's packages")
    home.chmod(0o750)
    for name in ("state", "logs", "bin"):
        (root / name).mkdir()
    judge = root / "bin" / "claude"
    judge.write_text(f"#!/bin/bash\ncat > '{root}/prompt'\n{{ pwd; ls -A \"$HOME\"; }} >> '{root}/view'\n{fake_judge}\n")
    judge.chmod(0o755)
    functions = shell_function(script, "verdict_files_valid") + shell_function(script, "run_judge")
    for tool in (
        '/usr/bin/timeout --signal=TERM --kill-after=30s "${JUDGE_TIMEOUT}"',
        "/usr/bin/setpriv --no-new-privs --reuid=agent --regid=agent --clear-groups",
    ):
        assert tool in functions
        functions = functions.replace(tool, "/usr/bin/env")
    ib = tasks / FIRST_TASK / "tests" / "ib"
    return bash(
        f"""
{SHELL_COMPAT}
AGENT_HOME={home}; TASK={home}/task; JUDGE_HOME={root}/judge; STATE={root}/state; LOGS={root}/logs; IB={ib}
SCENARIO={SCENARIO_TASKS["a"]}; INFERENCE_BENCH_BASE_MODEL=mistralai/Mistral-7B-Instruct-v0.3
JUDGE_STATE=no_credential; JUDGE_NOTE=""; JUDGE_ATTEMPTS=3; JUDGE_TIMEOUT=15m; JUDGE_MODE={mode}
PATH="{root}/bin:$PATH"
AGENT_ENV=("HOME={home}" "PATH=$PATH")
unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_BASE_URL
{"ANTHROPIC_API_KEY=key" if credential else ""}
chown() {{ :; }}
kill_agent_processes() {{ return {0 if killable else 1}; }}
restore_tmp() {{ :; }}
log() {{ echo "log: $*"; }}
no_reward() {{ echo "no reward: $*"; exit 3; }}
source "$IB/src/disallowed_usage_judge/judge.sh"
{functions}
run_judge
echo "judge=$JUDGE_STATE note=$JUDGE_NOTE"
"""
    )


CLEAN_VERDICTS = (
    'echo "no contamination detected" > "$HOME/contamination_judgement.txt"\n'
    'echo "only allowed use detected" > "$HOME/disallowed_model_judgement.txt"'
)


def test_the_judge_reviews_a_copy_and_the_agents_home_is_reopened(tasks: Path, tmp_path: Path) -> None:
    result = run_judge(tasks, tmp_path, CLEAN_VERDICTS)
    assert result.stdout.splitlines()[-1] == "judge=valid note=", result.stdout + result.stderr
    home = tmp_path / "home" / "agent"
    # The judge worked in its own home, with only the copy of the task directory in it.
    assert (tmp_path / "view").read_text().split() == [str(tmp_path / "judge"), "task"]
    assert "mounted read-only at /var/lib/ib_judge/task" in (tmp_path / "prompt").read_text()
    assert "## Contents of `start_server.sh`" in (tmp_path / "prompt").read_text()
    assert (tmp_path / "logs" / "contamination_judgement.txt").read_text() == "no contamination detected\n"
    assert (tmp_path / "logs" / "disallowed_model_judgement.attempt-1.txt").read_text() == "only allowed use detected\n"
    # Afterwards the copy is gone, and the agent's home has its mode and its content back.
    assert not (tmp_path / "judge").exists()
    assert home.stat().st_mode & 0o777 == 0o750
    assert sorted(path.name for path in home.iterdir()) == [".local", "task"]


@pytest.mark.parametrize(
    "fake_judge",
    [
        "exit 1",
        # A verdict with an explanation is not one of the two allowed lines.
        CLEAN_VERDICTS + '\necho "because ..." >> "$HOME/disallowed_model_judgement.txt"',
        # run_task.sh exits with the judge's status, whatever the judge wrote.
        CLEAN_VERDICTS + "\nexit 1",
    ],
)
def test_a_judge_without_two_valid_verdicts_leaves_the_trial_ungraded(tasks: Path, tmp_path: Path, fake_judge: str) -> None:
    result = run_judge(tasks, tmp_path, fake_judge)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[-1] == "judge=failed note=the judge produced no valid verdict in 3 attempts"
    assert len((tmp_path / "view").read_text().split()) == 3 * 2
    # What each attempt wrote is kept, but not under the names that write_reward.py reads.
    logs = sorted(path.name for path in (tmp_path / "logs").iterdir())
    assert "contamination_judgement.txt" not in logs and "disallowed_model_judgement.txt" not in logs
    assert ("contamination_judgement.attempt-3.txt" in logs) == ("contamination" in fake_judge)
    home = tmp_path / "home" / "agent"
    assert home.stat().st_mode & 0o777 == 0o750
    assert sorted(path.name for path in home.iterdir()) == [".local", "task"]


def test_a_judge_that_recovers_is_valid(tasks: Path, tmp_path: Path) -> None:
    flaky = f'[ -f "{tmp_path}/second" ] || {{ touch "{tmp_path}/second"; exit 1; }}\n' + CLEAN_VERDICTS
    result = run_judge(tasks, tmp_path, flaky)
    assert result.stdout.splitlines()[-1] == "judge=valid note="
    assert (tmp_path / "logs" / "contamination_judgement.attempt-2.txt").is_file()
    assert not (tmp_path / "logs" / "contamination_judgement.attempt-1.txt").exists()


def test_without_a_credential_the_judge_does_not_run(tasks: Path, tmp_path: Path) -> None:
    result = run_judge(tasks, tmp_path, CLEAN_VERDICTS, credential=False)
    assert result.stdout.splitlines()[-1] == (
        "judge=no_credential note=no judge credential (ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN)"
    )
    assert not (tmp_path / "prompt").exists()


def test_a_diagnostic_run_does_not_start_the_judge(tasks: Path, tmp_path: Path) -> None:
    result = run_judge(tasks, tmp_path, CLEAN_VERDICTS, mode="off")
    assert result.stdout.splitlines()[-1] == "judge=off note=diagnostic run: INFERENCE_BENCH_JUDGE=off"
    assert not (tmp_path / "prompt").exists()
    assert list((tmp_path / "logs").iterdir()) == []


def test_a_judge_that_cannot_be_stopped_ends_the_trial(tasks: Path, tmp_path: Path) -> None:
    result = run_judge(tasks, tmp_path, CLEAN_VERDICTS, killable=False)
    assert result.returncode == 3
    assert result.stdout.splitlines()[-1] == "no reward: could not stop the judge's processes"
    assert (tmp_path / "home" / "agent").stat().st_mode & 0o777 == 0o750


@pytest.mark.parametrize(("mode", "accepted"), [("required", True), ("off", True), ("of", False), ("", True)])
def test_the_judge_mode_must_be_known(tasks: Path, mode: str, accepted: bool) -> None:
    script = (tasks / FIRST_TASK / "tests" / "test.sh").read_text()
    start = script.index('case "${JUDGE_MODE}" in')
    check = script[start : script.index("esac\n", start) + 5]
    default = script[script.index('JUDGE_MODE="') :].split("\n", 1)[0]
    result = bash(f'INFERENCE_BENCH_JUDGE="{mode}"\n{default}\nno_reward() {{ echo "no reward: $*"; exit 3; }}\n{check}echo ok')
    assert (result.stdout.strip() == "ok") == accepted, result.stdout
    if not accepted:
        assert result.stdout.startswith("no reward: INFERENCE_BENCH_JUDGE must be required or off, not 'of'")


def run_verifier_end(tasks: Path, logs: Path, judge: str) -> list[str]:
    """Run test.sh from the evaluation to the end, with a reward writer that always writes a reward."""
    script = (tasks / FIRST_TASK / "tests" / "test.sh").read_text()
    end = script[script.index('cd "${IB}" || no_reward') :]
    harness = f"""
LOGS={logs}; IB={logs}; SCENARIO=x; INFERENCE_BENCH_SERVER_URL=u; PYTHONPATH=
JUDGE_STATE={judge}; JUDGE_NOTE="the reason"; FINAL_EVAL_RC=1
log() {{ echo "log: $*"; }}
no_reward() {{ echo "no reward: $*"; exit 3; }}
start_server() {{ echo "server started"; }}
run_eval_with_retry() {{ echo "evaluated"; FINAL_EVAL_RC=0; }}
stop_server() {{ return 0; }}
python3() {{ echo "write_reward.py ${{*:2}}"; echo '{{"reward": 30.3}}' > "$LOGS/reward.json"; }}
{end}
"""
    result = bash(harness)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.splitlines()


@pytest.mark.parametrize("judge", ["valid", "failed", "off", "no_credential"])
def test_only_a_valid_judge_leaves_a_reward(tasks: Path, tmp_path: Path, judge: str) -> None:
    lines = run_verifier_end(tasks, tmp_path, judge)
    assert (tmp_path / "reward.json").exists() == (judge == "valid")
    assert (lines[-1].startswith("[ungraded] the reason")) == (judge != "valid")
    # Without a credential the trial can never be graded, so the server is not measured.
    assert ("evaluated" in lines) == (judge != "no_credential")
    writer = next(line for line in lines if line.startswith("write_reward.py "))
    assert writer.split()[3:5] == (["not_run", judge] if judge == "no_credential" else ["0", judge])


def test_a_server_that_outlives_its_launcher_is_not_accepted(tasks: Path, tmp_path: Path) -> None:
    script = (tasks / FIRST_TASK / "tests" / "test.sh").read_text()
    functions = "".join(shell_function(script, name) for name in ("supervisor_alive", "start_server"))
    # The supervisor's command line fails at once here (no user agent), like a launcher that
    # exits; the stand-in endpoint keeps answering, like a server that the launcher detached.
    for name in ("task", "ib", "logs"):
        (tmp_path / name).mkdir()
    (tmp_path / "task" / "start_server.sh").write_text("#!/bin/bash\n")
    result = bash(
        f"""
TASK={tmp_path}/task; IB={tmp_path}/ib; LOGS={tmp_path}/logs; STUB_MARKER=none
AGENT_ENV=(); SERVER_PID=""; WATCHER_PID=""; INFERENCE_BENCH_SERVER_WAIT_S=20; INFERENCE_BENCH_SERVER_URL=u
stop_server() {{ return 0; }}
restore_tmp() {{ return 0; }}
watch_supervisor() {{ :; }}
server_ready() {{ sleep 1; return 0; }}
log() {{ echo "$*"; }}
{functions}
start_server
echo "rc=$?"
"""
    )
    assert result.stdout.splitlines() == [
        f"starting the eval server via {tmp_path}/task/start_server.sh",
        "eval server exited before becoming ready",
        "rc=1",
    ]


def run_retry_loop(
    tasks: Path, logs: Path, seconds_left: int, evaluator_rc: int, call: str = "run_eval_with_retry 3"
) -> tuple[str, list[str]]:
    """Run test.sh's retry functions with stand-ins for the server and the evaluator."""
    script = (tasks / FIRST_TASK / "tests" / "test.sh").read_text()
    functions = script[script.index("run_eval_attempt() {") : script.index('echo "=== InferenceBench verifier')]
    # run_eval_attempt sends the evaluator's output to EVAL_LOG, so the stand-in reports on fd 3.
    # The stand-in writes metrics that valid_eval_metrics.py (python3 here) rejects.
    harness = f"""
exec 3>&1
EVAL_DEADLINE=$(( $(date +%s) + {seconds_left} ))
LOGS={logs}; SCENARIO=x; EVAL_LOG=/dev/null; IB=/nonexistent; INFERENCE_BENCH_SERVER_URL=u
INFERENCE_BENCH_QUALITY_TAU=0.95; EVAL_HF=/nonexistent; EVAL_ATTEMPT=0
supervisor_alive() {{ return 0; }}
server_ready() {{ return 0; }}
start_server() {{ return 0; }}
log() {{ :; }}
python3() {{ return 1; }}
timeout() {{ echo "limit=$3" >&3; echo "attempt $((EVAL_ATTEMPT + 1))" > "$LOGS/metrics.json"; return {evaluator_rc}; }}
{functions}
FINAL_EVAL_RC=1
{call}
echo "loop=$? final=$FINAL_EVAL_RC"
"""
    lines = bash(harness, check=True).stdout.splitlines()
    return lines[-1], lines[:-1]


def test_evaluation_attempts_are_limited_only_by_the_verifier_deadline(tasks: Path, tmp_path: Path) -> None:
    summary, attempts = run_retry_loop(tasks, tmp_path, seconds_left=30000, evaluator_rc=124)
    assert summary == "loop=1 final=124"
    assert len(attempts) == 3
    # vLLM's default settings need about 8600 s for scenario B.
    assert all(int(line.removeprefix("limit=")) > 8600 for line in attempts)


def test_no_evaluation_starts_after_the_verifier_deadline(tasks: Path, tmp_path: Path) -> None:
    summary, attempts = run_retry_loop(tasks, tmp_path, seconds_left=-1, evaluator_rc=0)
    assert summary == "loop=1 final=1"
    assert attempts == []


def test_an_attempt_at_the_deadline_never_runs_without_a_limit(tasks: Path, tmp_path: Path) -> None:
    # `timeout 0` would mean no limit at all.
    summary, attempts = run_retry_loop(tasks, tmp_path, seconds_left=0, evaluator_rc=0, call="run_eval_attempt")
    assert summary == "loop=124 final=1"
    assert attempts == []


def test_every_evaluation_attempt_keeps_its_metrics(tasks: Path, tmp_path: Path) -> None:
    summary, attempts = run_retry_loop(tasks, tmp_path, seconds_left=30000, evaluator_rc=0)
    # Each attempt ended with status 0 and metrics that are not valid, so all three ran.
    assert summary == "loop=1 final=1"
    assert len(attempts) == 3
    assert {path.name: path.read_text().strip() for path in tmp_path.iterdir()} == {
        "metrics.json": "attempt 3",
        "metrics.attempt-1.json": "attempt 1",
        "metrics.attempt-2.json": "attempt 2",
        "metrics.attempt-3.json": "attempt 3",
    }


def test_evaluation_deadline_leaves_time_to_write_the_reward(tasks: Path) -> None:
    task = tasks / FIRST_TASK
    limit = tomllib.loads((task / "task.toml").read_text())["verifier"]["timeout_sec"]
    assert "+ 41400 ))" in (task / "tests" / "test.sh").read_text()
    # One server start (900 s) can begin just before the deadline.
    assert limit - 41400 > 900


@pytest.fixture
def write_reward(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Load write_reward.py with a stand-in for upstream's primary_metric."""
    hpo = types.ModuleType("src.eval.inference.hpo_search_baselines")
    hpo.FAILURE_SCORE = 1e-6
    hpo.SCENARIO_TO_SHORT = {task: key for key, task in SCENARIO_TASKS.items()}
    hpo.primary_metric = lambda metrics, scenario: (metrics["primary"], "test")
    for name in ("src", "src.eval", "src.eval.inference"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, hpo.__name__, hpo)
    spec = importlib.util.spec_from_file_location("write_reward", TEMPLATE / "tests" / "write_reward.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_run(logs: Path, primary: float | None, *, speed=True, quality=True, flagged=False, judged=True) -> None:
    if primary is not None:
        (logs / "metrics.json").write_text(
            json.dumps(
                {"primary": primary, "speed_check": {"pass": speed}, "quality_check": {"pass": quality}}
            )
        )
    if judged:
        (logs / "contamination_judgement.txt").write_text(
            ("contamination detected" if flagged else "no contamination detected") + "\n"
        )
        (logs / "disallowed_model_judgement.txt").write_text("only allowed use detected\n")


def run_write_reward(module: types.ModuleType, monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr(sys, "argv", ["write_reward.py", *args])
    module.main()


@pytest.mark.parametrize(
    ("scenario", "primary", "expected"),
    [
        # Claude Sonnet 4.6: Table 12 in native units, Table 2 as speedups.
        ("a", 1 / 0.24207, 3.47),
        ("b", 1 / 0.00341, 12.03),
        ("c", 4.48, 33.93),
        ("d", 5.06, 3.01),
    ],
)
def test_baselines_reproduce_the_papers_table(write_reward, tmp_path, scenario, primary, expected) -> None:
    write_run(tmp_path, primary)
    rewards = write_reward.rewards_for(tmp_path, SCENARIO_TASKS[scenario], "0")
    assert rewards["valid"] == 1
    assert rewards["judge_valid"] == 1
    assert rewards["reward"] == pytest.approx(expected, abs=0.02)


@pytest.mark.parametrize(
    ("kwargs", "eval_rc"),
    [
        ({"quality": False}, "0"),
        ({"speed": False}, "0"),
        ({"flagged": True}, "0"),
        ({}, "1"),
    ],
)
def test_failed_runs_count_as_the_baseline(write_reward, tmp_path, kwargs, eval_rc) -> None:
    write_run(tmp_path, 100.0, **kwargs)
    rewards = write_reward.rewards_for(tmp_path, SCENARIO_TASKS["c"], eval_rc)
    assert rewards["reward"] == 1.0
    assert rewards["valid"] == 0
    assert rewards["judge_valid"] == 1
    assert rewards["contamination_detected"] == int(kwargs.get("flagged", False))


@pytest.mark.parametrize("primary", [float("inf"), float("nan"), 0.0, -1.0])
def test_a_measurement_that_is_not_a_positive_number_counts_as_the_baseline(write_reward, tmp_path, primary) -> None:
    write_run(tmp_path, primary)
    rewards = write_reward.rewards_for(tmp_path, SCENARIO_TASKS["c"], "0")
    assert (rewards["reward"], rewards["valid"], rewards["speedup"]) == (1.0, 0, 0.0)


def test_missing_metrics_count_as_the_baseline(write_reward, tmp_path) -> None:
    write_run(tmp_path, None)
    rewards = write_reward.rewards_for(tmp_path, SCENARIO_TASKS["a"], "1")
    assert rewards["reward"] == 1.0
    assert rewards["valid"] == 0
    assert rewards["speedup"] == 0


@pytest.mark.parametrize(
    ("judge", "note"),
    [
        ("off", "diagnostic run: INFERENCE_BENCH_JUDGE=off"),
        ("no_credential", "no judge credential"),
        ("failed", "the judge produced no valid verdict in 3 attempts"),
    ],
)
def test_a_run_without_a_valid_judge_gets_no_reward(write_reward, tmp_path, monkeypatch, capsys, judge, note) -> None:
    # The measurement passes every gate, and a reward file is left over from somewhere.
    write_run(tmp_path, 4.0, judged=False)
    (tmp_path / "reward.json").write_text('{"reward": 30.3}')
    (tmp_path / "reward.txt").write_text("30.3")
    run_write_reward(write_reward, monkeypatch, str(tmp_path), SCENARIO_TASKS["c"], "0", judge, note)
    assert not (tmp_path / "reward.json").exists() and not (tmp_path / "reward.txt").exists()
    ungraded = json.loads((tmp_path / "ungraded.json").read_text())
    assert "reward" not in ungraded and "valid" not in ungraded
    assert ungraded["status"] == "ungraded"
    assert (ungraded["judge"], ungraded["reason"], ungraded["judge_valid"]) == (judge, note, 0)
    assert (ungraded["evaluated"], ungraded["gates_passed"]) == (1, 1)
    assert ungraded["speedup"] == pytest.approx(4.0 / 0.132)
    assert capsys.readouterr().out.startswith("ungraded.json: ")


def test_a_run_that_was_not_evaluated_has_no_measurement(write_reward, tmp_path, monkeypatch) -> None:
    run_write_reward(write_reward, monkeypatch, str(tmp_path), SCENARIO_TASKS["b"], "not_run", "no_credential", "why")
    assert json.loads((tmp_path / "ungraded.json").read_text()) == {
        "status": "ungraded",
        "judge": "no_credential",
        "reason": "why",
        "judge_valid": 0,
        "evaluated": 0,
    }
    # A judged trial is always evaluated.
    write_run(tmp_path, 4.0)
    with pytest.raises(SystemExit):
        run_write_reward(write_reward, monkeypatch, str(tmp_path), SCENARIO_TASKS["b"], "not_run", "valid", "")
    assert not (tmp_path / "reward.json").exists() and not (tmp_path / "ungraded.json").exists()


def test_a_judged_run_gets_a_reward_and_no_ungraded_record(write_reward, tmp_path, monkeypatch) -> None:
    write_run(tmp_path, 4.0)
    (tmp_path / "ungraded.json").write_text("{}")
    run_write_reward(write_reward, monkeypatch, str(tmp_path), SCENARIO_TASKS["c"], "0", "valid", "")
    assert not (tmp_path / "ungraded.json").exists()
    rewards = json.loads((tmp_path / "reward.json").read_text())
    assert (rewards["valid"], rewards["judge_valid"]) == (1, 1)
    assert rewards["reward"] == pytest.approx(4.0 / 0.132)


@pytest.mark.parametrize("verdict", [None, b"disallowed use detected\nbecause ...\n", b"\xff\n"])
def test_a_judged_run_needs_two_valid_verdicts(write_reward, tmp_path, monkeypatch, verdict) -> None:
    write_run(tmp_path, 4.0)
    if verdict is None:
        (tmp_path / "disallowed_model_judgement.txt").unlink()
    else:
        (tmp_path / "disallowed_model_judgement.txt").write_bytes(verdict)
    with pytest.raises(SystemExit):
        write_reward.rewards_for(tmp_path, SCENARIO_TASKS["c"], "0")
    with pytest.raises(SystemExit):
        run_write_reward(write_reward, monkeypatch, str(tmp_path), SCENARIO_TASKS["c"], "0", "valid", "")
    assert not (tmp_path / "reward.json").exists()


@pytest.mark.parametrize("judge", ["skipped", "1", ""])
def test_an_unknown_judge_state_writes_nothing(write_reward, tmp_path, monkeypatch, judge) -> None:
    write_run(tmp_path, 4.0)
    with pytest.raises(SystemExit):
        run_write_reward(write_reward, monkeypatch, str(tmp_path), SCENARIO_TASKS["c"], "0", judge)
    assert not (tmp_path / "reward.json").exists() and not (tmp_path / "ungraded.json").exists()


def test_a_slower_valid_server_keeps_its_measured_speedup(write_reward, tmp_path) -> None:
    write_run(tmp_path, 0.066)
    rewards = write_reward.rewards_for(tmp_path, SCENARIO_TASKS["c"], "0")
    assert rewards["reward"] == pytest.approx(0.5)


def test_write_reward_runs_with_upstreams_metric_code(tasks: Path, tmp_path: Path) -> None:
    pytest.importorskip("requests")  # upstream's module imports it
    burst = {
        "request_count": 128,
        "success_count": 128,
        "ttft": {"p50": 0.672},
        "tpot": {"p50": 0.018},
        "generation_throughput_tokens_per_s": 55.0,
        "request_throughput_req_per_s": 0.05,
    }
    (tmp_path / "metrics.json").write_text(
        json.dumps({"profiles": {"burst": burst}, "speed_check": {"pass": True}, "quality_check": {"pass": True}})
    )
    tests_dir = tasks / FIRST_TASK / "tests"

    def run(*judge: str) -> None:
        subprocess.run(
            [sys.executable, str(tests_dir / "write_reward.py"), str(tmp_path), SCENARIO_TASKS["a"], "0", *judge],
            env={**os.environ, "PYTHONPATH": str(tests_dir / "ib")},
            check=True,
            capture_output=True,
        )

    run("no_credential", "no judge credential")
    assert not (tmp_path / "reward.json").exists()
    # 840 ms / 672 ms: the paper's "vLLM default" value for scenario A.
    assert json.loads((tmp_path / "ungraded.json").read_text())["speedup"] == pytest.approx(1.25)
    write_run(tmp_path, None)
    run("valid", "")
    rewards = json.loads((tmp_path / "reward.json").read_text())
    assert rewards["reward"] == pytest.approx(1.25)
    assert (rewards["valid"], rewards["judge_valid"]) == (1, 1)
    assert not (tmp_path / "ungraded.json").exists()


def write_trial(
    job: Path,
    scenario: str,
    pair: str,
    reward: float | None,
    agent: str = "claude-code",
    ungraded: dict | None = None,
    error: str | None = None,
    agent_env: dict | None = None,
    **extra,
) -> Path:
    trial = job / f"inferencebench-{scenario}-mistral-7b-{pair}__{agent}{len(list(job.iterdir()))}"
    trial.mkdir()
    result = {
        "task_name": f"aisa-group/inferencebench-{scenario}-mistral-7b-{pair}",
        "agent_info": {"name": agent, "model_info": {"name": "claude-sonnet-4-6"}},
        "verifier_result": None if reward is None else {"rewards": {"reward": reward, "valid": 1, "judge_valid": 1, **extra}},
        "exception_info": None if error is None else {"exception_type": error},
        "config": {"agent": {"name": agent, **({"env": agent_env} if agent_env else {})}},
    }
    (trial / "result.json").write_text(json.dumps(result))
    if ungraded is not None:
        (trial / "verifier").mkdir()
        (trial / "verifier" / "ungraded.json").write_text(json.dumps(ungraded))
    return trial


# Claude Sonnet 4.6 per-scenario means from Table 2.
PAPER_MEANS = {"a": 3.47, "b": 12.03, "c": 33.93, "d": 3.01}
SEED_OFFSETS = (("21-1337", -0.5), ("248-428", 0.0), ("999-777", 0.5))
UNGRADED = {"status": "ungraded", "judge": "no_credential", "reason": "no judge credential", "speedup": 12.0}


def write_job(job: Path, skip: tuple[str, str] | None = None, only: tuple[str, ...] = (), **kwargs) -> None:
    """Write a complete run, without the cell `skip`, or only the cells named in `only`."""
    job.mkdir(exist_ok=True)
    for scenario, value in PAPER_MEANS.items():
        for pair, offset in SEED_OFFSETS:
            if (scenario, pair) != skip and (not only or f"{scenario} {pair}" in only):
                write_trial(job, scenario, pair, value + offset, **kwargs)


def test_score_reproduces_the_papers_aggregate(tmp_path: Path) -> None:
    write_job(tmp_path)
    summary = score.summarize(score.load_trials(tmp_path))
    assert (summary["n_trials"], summary["n_graded"], summary["n_valid"]) == (12, 12, 12)
    assert summary["missing"] == summary["repeated"] == []
    assert summary["scenarios"]["a"]["mean"] == pytest.approx(3.47)
    assert summary["scenarios"]["a"]["sem"] == pytest.approx(0.2887, abs=0.001)
    assert summary["aggregate"]["mean"] == pytest.approx(8.08, abs=0.01)
    assert len(summary["aggregate"]["seed_pairs"]) == 3


def test_score_reads_only_harbors_trial_results(tmp_path: Path) -> None:
    write_job(tmp_path)
    trial = next(tmp_path.iterdir())
    forged = json.dumps(
        {"task_name": "inferencebench-a-mistral-7b-21-1337", "verifier_result": {"rewards": {"reward": 1000.0}}}
    )
    # Harbor copies what the agent wrote under /logs/agent and in its task directory to these places.
    for directory, content in (("agent", forged), ("verifier/task", forged), ("verifier/task/sweep", "[1, 2]")):
        (trial / directory).mkdir(parents=True, exist_ok=True)
        (trial / directory / "result.json").write_text(content)
    (tmp_path / "result.json").write_text("{}")  # Harbor's job-level result
    summary = score.summarize(score.load_trials(tmp_path))
    assert summary["n_trials"] == 12
    assert summary["aggregate"]["mean"] == pytest.approx(8.08, abs=0.01)


def test_score_counts_a_failed_judged_trial_as_the_baseline(tmp_path: Path) -> None:
    write_job(tmp_path, skip=("b", "248-428"))
    # The evaluation failed or the judge flagged the run: reward 1.0 and valid 0.
    write_trial(tmp_path, "b", "248-428", 1.0, valid=0)
    summary = score.summarize(score.load_trials(tmp_path))
    assert (summary["n_graded"], summary["n_valid"], summary["n_failed"]) == (12, 11, 1)
    assert summary["missing"] == []
    assert sorted(summary["scenarios"]["b"]["runs"]) == [1.0, 11.53, 12.53]
    assert "aggregate" in summary
    assert [row["note"] for row in summary["trials"] if row["status"] == "failed"] == ["counted as 1x"]


def test_score_lists_ungraded_trials_and_errors_instead_of_an_aggregate(tmp_path: Path) -> None:
    write_job(tmp_path, skip=("b", "248-428"))
    summary = score.summarize(score.load_trials(tmp_path))
    assert summary["missing"] == ["b 248:428"]
    # The verifier measured the server, but the judge returned no valid verdict.
    write_trial(tmp_path, "b", "248-428", None, ungraded=UNGRADED, error="RewardFileNotFoundError")
    # The verifier did not get that far.
    write_trial(tmp_path, "b", "248-428", None, error="VerifierTimeoutError")
    summary = score.summarize(score.load_trials(tmp_path))
    assert (summary["n_trials"], summary["n_graded"], summary["n_ungraded"], summary["n_errors"]) == (13, 11, 1, 1)
    assert summary["missing"] == ["b 248:428"]
    assert "aggregate" not in summary
    assert len(summary["scenarios"]["b"]["runs"]) == 2
    rows = {row["status"]: row for row in summary["trials"] if row["cell"] == "b 248:428"}
    assert (rows["ungraded"]["reward"], rows["ungraded"]["speedup"], rows["ungraded"]["note"]) == (
        None,
        12.0,
        "no judge credential",
    )
    assert rows["error"]["note"] == "VerifierTimeoutError"
    assert rows["ungraded"]["trial"].startswith(str(tmp_path))


def test_score_does_not_accept_a_reward_without_a_valid_judge(tmp_path: Path) -> None:
    # What the verifier of an earlier version of this adapter wrote for a run without the judge.
    write_job(tmp_path, judge_valid=0)
    summary = score.summarize(score.load_trials(tmp_path))
    assert (summary["n_graded"], summary["n_ungraded"]) == (0, 12)
    assert len(summary["missing"]) == 12
    assert summary["scenarios"] == {} and "aggregate" not in summary
    assert {row["note"] for row in summary["trials"]} == {"the reward was written without a valid judge verdict"}


def test_score_sets_aside_a_run_that_recomputes_the_quality_reference(tmp_path: Path) -> None:
    write_job(tmp_path, agent="oracle")
    # Judged by mistake: the reference leaves no server, so the verifier counted it as a failure.
    write_trial(
        tmp_path, "a", "21-1337", 1.0, agent="oracle", valid=0, agent_env={"INFERENCE_BENCH_ORACLE": "pytorch-reference"}
    )
    summary = score.summarize(score.load_trials(tmp_path))
    assert (summary["n_trials"], summary["n_graded"], summary["n_reference"]) == (13, 12, 1)
    assert summary["repeated"] == [] and "aggregate" in summary
    assert [row["status"] for row in summary["trials"]].count("reference") == 1


def test_score_reports_repeated_trials_instead_of_an_aggregate(tmp_path: Path) -> None:
    write_job(tmp_path)
    write_trial(tmp_path, "c", "999-777", 1.0)
    summary = score.summarize(score.load_trials(tmp_path))
    assert summary["repeated"] == ["c 999:777"]
    assert "aggregate" not in summary


def run_score(monkeypatch, capsys, *args: str) -> tuple[int, dict[str, dict], str]:
    monkeypatch.setattr(sys, "argv", ["inferencebench-score", *args])
    with pytest.raises(SystemExit) as exit_info:
        score.main()
    captured = capsys.readouterr()
    decoder, position, summaries = json.JSONDecoder(), 0, {}
    while position < len(captured.out.rstrip()):
        summary, position = decoder.raw_decode(captured.out, position)
        summaries[summary["agent"]] = summary
        position += 1
    return exit_info.value.code, summaries, captured.err


def test_score_keeps_agents_apart_and_fails_on_an_incomplete_run(tmp_path, monkeypatch, capsys) -> None:
    write_job(tmp_path)
    write_job(tmp_path, agent="oracle", skip=("d", "21-1337"))
    trial = write_trial(tmp_path, "d", "21-1337", None, agent="oracle", ungraded=UNGRADED)
    code, summaries, err = run_score(monkeypatch, capsys, str(tmp_path))
    assert code == 1
    assert summaries["claude-code claude-sonnet-4-6"]["aggregate"]["mean"] == pytest.approx(8.08, abs=0.01)
    assert "aggregate" not in summaries["oracle claude-sonnet-4-6"]
    assert "no aggregate, because these cells have no graded trial: d 21:1337" in err
    assert f"ungraded: {trial}: no judge credential" in err


def test_score_pools_a_run_that_was_launched_in_stages(tmp_path, monkeypatch, capsys) -> None:
    stages = {
        "pilot": ("a 21-1337",),
        "scenarios": ("b 21-1337", "c 21-1337", "d 21-1337"),
        "rest": tuple(f"{scenario} {pair}" for scenario in "abcd" for pair in ("248-428", "999-777")),
    }
    for name, cells in stages.items():
        write_job(tmp_path / name, only=cells, agent="oracle")
    jobs = [str(tmp_path / name) for name in stages]
    code, summaries, _ = run_score(monkeypatch, capsys, *jobs)
    assert code == 1 and "aggregate" not in summaries["oracle claude-sonnet-4-6"]
    code, summaries, err = run_score(monkeypatch, capsys, "--pool", *jobs)
    assert (code, err) == (0, "")
    assert summaries["oracle claude-sonnet-4-6"]["n_graded"] == 12
    assert summaries["oracle claude-sonnet-4-6"]["aggregate"]["mean"] == pytest.approx(8.08, abs=0.01)


def test_score_needs_all_of_the_benchmarks_seed_pairs(tmp_path: Path) -> None:
    for scenario, value in PAPER_MEANS.items():
        write_trial(tmp_path, scenario, "21-1337", value)
    summary = score.summarize(score.load_trials(tmp_path))
    assert len(summary["missing"]) == 8
    assert "aggregate" not in summary
    assert list(score.SEED_PAIRS) == InferenceBenchAdapter(tmp_path / "unused").seed_pairs


def test_score_parses_seeds_from_the_end_of_the_task_name() -> None:
    match = score.TASK_RE.search("aisa-group/inferencebench-b-llama-3-1-8b-248-428")
    assert (match["scenario"], match["agent"], match["eval"]) == ("b", "248", "428")
    assert score.sample_sem([1.0]) is None


class TestContinuationLoop:
    """The CLI stand-in runs for a scripted time, or fails after it if the step is negative."""

    @pytest.fixture
    def agent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        pytest.importorskip("harbor")
        from harbor.agents.installed.base import NonZeroAgentExitCodeError

        from inferencebench import agents

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
        agent = agents.ClaudeCodeUntilDeadline(
            logs_dir=tmp_path, model_name="anthropic/claude-sonnet-4-6"
        )
        self.clock = 0.0
        self.budget = "600\n"
        self.steps: list[int] = []
        self.setup_seconds = 0
        self.commands: list[str] = []
        self.runs: list[tuple[bool, int, str]] = []
        monkeypatch.setattr(agents.time, "monotonic", lambda: self.clock)

        async def sleep(seconds: float) -> None:
            self.clock += seconds

        monkeypatch.setattr(agents.asyncio, "sleep", sleep)

        async def _exec(environment, command, user=None, env=None, cwd=None, timeout_sec=None):
            self.commands.append(command)
            if command.startswith("echo $(( $(cat /timer_start)"):
                return types.SimpleNamespace(stdout=self.budget, return_code=0)
            if "claude --verbose" not in command:
                if command.startswith("timeout "):
                    self.clock += self.setup_seconds
                return types.SimpleNamespace(stdout="", return_code=0)
            limit = int(re.match(r"timeout --signal=TERM --kill-after=30s (\d+)s bash -o pipefail -c ", command)[1])
            prompt = next(value for key, value in env.items() if key.startswith("CLAUDE_CODE_INSTRUCTION"))
            self.runs.append(("--continue" in command, limit, prompt))
            step = self.steps.pop(0)
            self.clock += min(abs(step), limit)
            if step < 0 or step >= limit:
                raise NonZeroAgentExitCodeError("the CLI exited with a non-zero status")
            return types.SimpleNamespace(stdout="", return_code=0)

        monkeypatch.setattr(agent, "_exec", _exec)
        monkeypatch.setattr(agent, "_upload_base_settings", AsyncMock())
        return agent

    @pytest.mark.asyncio
    async def test_continues_until_the_deadline_stops_the_cli(self, agent) -> None:
        self.steps = [300, 200, 200]
        await agent.run("the prompt", Mock(), Mock())
        assert [(resumed, limit) for resumed, limit, _ in self.runs] == [(False, 600), (True, 300), (True, 100)]
        assert self.runs[0][2] == "the prompt"
        assert self.runs[1][2] == (
            "Continue where you left off and complete the task. You have approximately 5 minutes "
            "(300 seconds) of wall-clock time remaining. Make sure you utilize this time fully to "
            "achieve the best results you can. Do not ask for user feedback."
        )
        assert self.clock == 600
        assert "claude-code.2.txt" in " ".join(self.commands)

    @pytest.mark.asyncio
    async def test_the_cli_never_starts_after_the_deadline(self, agent) -> None:
        self.steps = [598]
        self.setup_seconds = 1
        await agent.run("the prompt", Mock(), Mock())
        # One second was left for a second run, and its setup used it up.
        assert [(resumed, limit) for resumed, limit, _ in self.runs] == [(False, 599)]
        assert self.steps == []

    @pytest.mark.asyncio
    async def test_a_failed_resume_starts_over_with_the_task_prompt(self, agent) -> None:
        self.steps = [-10, -5, 100, 1000]
        await agent.run("the prompt", Mock(), Mock())
        assert [(resumed, prompt == "the prompt") for resumed, _, prompt in self.runs] == [
            (False, True),
            (True, False),
            (False, True),
            (True, False),
        ]

    @pytest.mark.asyncio
    async def test_gives_up_after_three_failed_runs(self, agent) -> None:
        from harbor.agents.installed.base import NonZeroAgentExitCodeError

        self.steps = [-10] * 5
        with pytest.raises(NonZeroAgentExitCodeError):
            await agent.run("the prompt", Mock(), Mock())
        # Run 1 starts a session; runs 2 and 3 each resume and then start over.
        assert [resumed for resumed, _, _ in self.runs] == [False, True, False, True, False]

    @pytest.mark.asyncio
    async def test_does_not_restart_a_failure_near_the_deadline(self, agent) -> None:
        from harbor.agents.installed.base import NonZeroAgentExitCodeError

        self.steps = [-550]
        with pytest.raises(NonZeroAgentExitCodeError):
            await agent.run("the prompt", Mock(), Mock())
        assert len(self.runs) == 1

    @pytest.mark.parametrize("budget", ["", "-1700000000\n", "0\n"])
    @pytest.mark.asyncio
    async def test_a_missing_timer_is_an_error(self, agent, budget) -> None:
        self.budget = budget
        with pytest.raises(RuntimeError):
            await agent.run("the prompt", Mock(), Mock())
        assert self.runs == []
