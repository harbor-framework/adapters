import json
import tomllib
from pathlib import Path

import pytest

from agentclinic import prompts
from agentclinic.adapter import AgentClinicAdapter
from agentclinic.cases import load_cases

FIXTURE = Path(__file__).parent / "fixtures" / "medqa_ext_sample.jsonl"
REQUIRED = [
    "task.toml",
    "instruction.md",
    "environment/Dockerfile",
    "environment/docker-compose.yaml",
    "environment/runtime/Dockerfile",
    "environment/runtime/requirements.txt",
    "environment/runtime/server.py",
    "environment/runtime/seal.py",
    "environment/runtime/prompts.py",
    "environment/runtime/clinic.py",
    "environment/runtime/llm.py",
    "environment/runtime/case.json",
    "solution/solve.sh",
    "tests/Dockerfile",
    "tests/test.sh",
    "tests/judge.py",
    "tests/prompts.py",
    "tests/llm.py",
    "tests/case.json",
]


@pytest.fixture
def generated(tmp_path):
    paths = AgentClinicAdapter(tmp_path / "out", source=FIXTURE).run()
    return tmp_path / "out", paths


def test_generate_three(generated):
    out, paths = generated
    assert [p.name for p in paths] == ["medqa-ext-000", "medqa-ext-001", "medqa-ext-002"]
    for task in paths:
        for rel in REQUIRED:
            assert (task / rel).is_file(), rel
        for path in task.rglob("*"):
            if path.is_file() and path.suffix in {".toml", ".md", ".sh", ".yaml"}:
                text = path.read_text()
                for token in ("{task_id}", "{objective}", "{diagnosis_json}"):
                    assert token not in text, (path, token)


def test_task_toml(generated):
    _, paths = generated
    config = tomllib.loads((paths[1] / "task.toml").read_text())
    assert config["version"] == "1.0"
    assert config["task"]["name"] == "agentclinic/agentclinic__medqa-ext-001"
    assert config["task"]["authors"][0] == {"name": "Samuel Schmidgall"}
    assert len(config["task"]["authors"]) == 6
    assert config["verifier"]["environment_mode"] == "separate"
    assert config["verifier"]["env"]["AGENTCLINIC_MODERATOR_MODEL"] == "gpt-4o-mini"
    assert config["artifacts"] == [{"source": "/root/logs", "service": "clinic"}]
    assert config["verifier"]["collect"] == [{"service": "clinic", "command": "python3 /app/seal.py"}]
    assert config["environment"]["mcp_servers"] == [
        {"name": "clinic", "transport": "streamable-http", "url": "http://clinic:8000/mcp"}
    ]


def test_task_toml_loads_in_harbor(generated):
    config_module = pytest.importorskip("harbor.models.task.config")
    _, paths = generated
    config = config_module.TaskConfig.model_validate_toml((paths[0] / "task.toml").read_text())
    assert config.verifier.environment_mode.value == "separate"
    assert config.environment.mcp_servers[0].url == "http://clinic:8000/mcp"


def test_instruction_starts_with_upstream_doctor_prompt_and_hides_benchmark(generated):
    _, paths = generated
    case = load_cases(FIXTURE)[0]
    text = (paths[0] / "instruction.md").read_text()
    assert text.startswith(prompts.doctor_system_prompt(prompts.MAX_INFERENCES, 0, case.examiner_information()))
    for word in ("agentclinic", "medqa", "osce", "benchmark"):
        assert word not in text.lower()
    for tool in ("ask_patient", "request_test", "submit_diagnosis", "get_status"):
        assert tool in text


def test_diagnosis_only_in_solution_and_tests(generated):
    _, paths = generated
    task = paths[0]
    diagnosis = load_cases(FIXTURE)[0].correct_diagnosis
    assert diagnosis in (task / "solution/solve.sh").read_text()
    assert json.loads((task / "tests/case.json").read_text())["correct_diagnosis"] == diagnosis
    for path in [task / "instruction.md", *(task / "environment").rglob("*")]:
        if path.is_file():
            assert diagnosis.lower() not in path.read_text().lower(), path


def test_runtime_case_matches_runtime_view(generated):
    _, paths = generated
    case = load_cases(FIXTURE)[2]
    assert json.loads((paths[2] / "environment/runtime/case.json").read_text()) == case.runtime_view()


def test_overwrite_guard(tmp_path):
    out = tmp_path / "out"
    AgentClinicAdapter(out, source=FIXTURE, limit=1).run()
    sentinel = out / "medqa-ext-000" / "sentinel"
    sentinel.write_text("keep")
    AgentClinicAdapter(out, source=FIXTURE, limit=1).run()
    assert sentinel.exists()
    AgentClinicAdapter(out, source=FIXTURE, limit=1, overwrite=True).run()
    assert not sentinel.exists()


def test_split_and_ids_are_passed_through(tmp_path):
    paths = AgentClinicAdapter(tmp_path / "out", source=FIXTURE, task_ids=["medqa-ext-002"]).run()
    assert [p.name for p in paths] == ["medqa-ext-002"]


def test_solve_script_is_valid_bash_and_python(generated):
    import subprocess

    _, paths = generated
    script = paths[0] / "solution/solve.sh"
    assert subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode == 0
    body = script.read_text().split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    compile(body, "solve.py", "exec")


def test_compose_restarts_the_clinic_on_failure(generated):
    _, paths = generated
    compose = (paths[0] / "environment/docker-compose.yaml").read_text()
    assert "restart: on-failure" in compose


def test_simulator_retry_settings_reach_the_sidecar(generated):
    _, paths = generated
    config = tomllib.loads((paths[0] / "task.toml").read_text())
    compose = (paths[0] / "environment/docker-compose.yaml").read_text()
    for name in ("AGENTCLINIC_LLM_TRIES", "AGENTCLINIC_LLM_RETRY_SLEEP", "AGENTCLINIC_LLM_DEADLINE"):
        assert name in config["environment"]["env"]
        assert f"{name}=${{{name}" in compose


def test_parity_split_has_its_own_default_directory():
    from agentclinic.main import default_output_dir

    assert default_output_dir("full").name == "agentclinic"
    assert default_output_dir("parity").name == "agentclinic-parity"


def test_parity_split_refuses_a_directory_with_other_tasks(tmp_path):
    out = tmp_path / "out"
    AgentClinicAdapter(out, source=FIXTURE, limit=1).run()
    with pytest.raises(ValueError, match="medqa-ext-000"):
        AgentClinicAdapter(out, split="parity", source=FIXTURE).run()


def test_base_images_are_pinned_by_digest():
    template = Path(__file__).resolve().parents[1] / "src/agentclinic/task-template"
    pinned = "FROM python:3.12.16-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"
    for rel in ("environment/Dockerfile", "environment/runtime/Dockerfile", "tests/Dockerfile"):
        assert (template / rel).read_text().splitlines()[0] == pinned, rel


@pytest.mark.parametrize(
    "name, dataset, agent",
    [
        ("run_agentclinic.yaml", "datasets/agentclinic", "oracle"),
        ("agentclinic-parity.yaml", "datasets/agentclinic-parity", "agentclinic-doctor"),
    ],
)
def test_job_configs_load_in_harbor(name, dataset, agent):
    import yaml

    job_config = pytest.importorskip("harbor.models.job.config")
    raw = yaml.safe_load((Path(__file__).resolve().parents[1] / name).read_text())
    config = job_config.JobConfig.model_validate(raw)
    assert [str(d.path) for d in config.datasets] == [dataset]
    assert config.agents[0].name == agent


def test_run_config_lists_commented_alternatives():
    text = (Path(__file__).resolve().parents[1] / "run_agentclinic.yaml").read_text()
    assert "#   import_path: agentclinic.agents.doctor:AgentClinicDoctorAgent" in text
    assert "# - name: codex" in text
