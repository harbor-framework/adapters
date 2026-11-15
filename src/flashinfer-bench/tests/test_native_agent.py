import asyncio
import shlex
from types import SimpleNamespace as NS

import pytest

pytest.importorskip("harbor")
from flashinfer_bench.native_agent import FlashInferNativeAgent


def test_native_transport_preserves_settings_and_uses_env_for_key(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("BASE_URL", "https://example.invalid/v1")
    calls = []

    class Environment:
        async def exec(self, command, **kwargs):
            calls.append((command, kwargs))
            return NS(return_code=0)

    agent = FlashInferNativeAgent(
        logs_dir=tmp_path, model_name="exact-model-id", seed=17
    )
    context = NS()
    asyncio.run(agent.setup(Environment()))
    asyncio.run(
        agent.run("This must not become a model prompt", Environment(), context)
    )
    assert len(calls) == 1
    command, kwargs = calls[0]
    argv = shlex.split(command)
    assert argv[argv.index("--model") + 1] == "exact-model-id"
    assert argv[argv.index("--rounds") + 1] == "10"
    assert argv[argv.index("--attempts") + 1] == "2"
    assert argv[argv.index("--seed") + 1] == "17"
    assert "test-key" not in command and "model prompt" not in command
    assert kwargs["env"]["LLM_API_KEY"] == "test-key"
    assert kwargs["env"]["BASE_URL"] == "https://example.invalid/v1"


def test_failed_native_process_is_not_success(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    class Environment:
        async def exec(self, *args, **kwargs):
            return NS(return_code=1)

    agent = FlashInferNativeAgent(logs_dir=tmp_path, model_name="exact-model-id")
    with pytest.raises(RuntimeError, match=r"Native generator failed \(exit 1\)"):
        asyncio.run(agent.run("", Environment(), NS()))
