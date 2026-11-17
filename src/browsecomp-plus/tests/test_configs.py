"""Reference jobs must use supported Harbor fields instead of ignored legacy keys."""

from pathlib import Path

import pytest
import yaml

job_module = pytest.importorskip("harbor.models.job.config")
JobConfig = job_module.JobConfig
ADAPTER_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("filename", ["run_browsecomp_plus.yaml", "run_parity.yaml"])
def test_reference_configs_use_supported_fields_and_concurrency(filename: str) -> None:
    data = yaml.safe_load((ADAPTER_ROOT / filename).read_text())
    assert not set(data).difference(JobConfig.model_fields)
    config = JobConfig.model_validate(data)
    assert config.n_concurrent_trials == 2
    assert config.n_attempts == 1
    if filename == "run_browsecomp_plus.yaml":
        assert config.agents[0].name == "oracle"
    else:
        assert config.agents[0].import_path == (
            "browsecomp_plus.deep_research_agent:DeepResearchAgent"
        )
        assert config.agents[0].kwargs["max_turns"] == 30


def test_oracle_config_resolves_without_model_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harbor.utils.env import resolve_env_vars

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    data = yaml.safe_load((ADAPTER_ROOT / "run_browsecomp_plus.yaml").read_text())
    config = JobConfig.model_validate(data)
    resolved = resolve_env_vars(config.verifier.env)
    assert resolved["OPENAI_API_KEY"] == ""
    assert resolved["OPENAI_BASE_URL"] == "https://api.openai.com/v1"


def test_parity_config_defaults_only_url_and_requires_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harbor.utils.env import resolve_env_vars

    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    data = yaml.safe_load((ADAPTER_ROOT / "run_parity.yaml").read_text())
    config = JobConfig.model_validate(data)
    for env in (config.agents[0].env, config.verifier.env):
        resolved = resolve_env_vars(env)
        assert resolved["OPENAI_BASE_URL"] == "https://api.openai.com/v1"
        assert resolved["OPENAI_API_KEY"] == "synthetic-test-key"
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        resolve_env_vars(config.agents[0].env)
