"""CPU tests for transport/retry boundaries; no model or GPU execution."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

RUNTIME = Path(__file__).parents[1] / "src/flashinfer_bench/runtime"
sys.path.insert(0, str(RUNTIME))
import assets
import generate


@pytest.fixture
def driver(tmp_path, monkeypatch):
    import flashinfer_bench

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"target_gpu": "B200", "definition": "test"}))
    output = tmp_path / "solution.json"
    output.write_text("stale")
    monkeypatch.setattr(assets, "check_gpu", lambda target: None)
    monkeypatch.setattr(assets, "prepare", lambda *args: None)
    data = NS(definitions={"test": object()})
    monkeypatch.setattr(
        flashinfer_bench, "TraceSet", NS(from_path=lambda path: data), raising=False
    )
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate.py",
            "--manifest",
            str(manifest),
            "--output",
            str(output),
            "--model",
            "exact-model",
            "--seed",
            "17",
        ],
    )
    calls = []

    def install(outcomes):
        class KernelGenerator:
            def __init__(self, **kwargs):
                assert kwargs["use_ffi"] is False
                assert kwargs["reasoning_effort"] == "high"
                assert kwargs["model_name"] == "exact-model"

            def generate(self, traces, definition, gen_rounds):
                assert traces is data and definition is data.definitions["test"]
                assert gen_rounds == 10
                calls.append(True)
                result = outcomes[len(calls) - 1]
                if isinstance(result, Exception):
                    raise result
                return result

        monkeypatch.setitem(
            sys.modules, "kernel_generator", NS(KernelGenerator=KernelGenerator)
        )

    return output, calls, install


def test_generation_retries_upstream_exceptions_only(driver):
    output, calls, install = driver
    install(
        [
            RuntimeError("first generation failed"),
            NS(model_dump_json=lambda **kw: '{"ok": true}'),
        ]
    )
    generate.main()
    assert len(calls) == 2
    assert json.loads(output.read_text()) == {"ok": True}


def test_saving_failure_never_retries_generation(driver, monkeypatch):
    output, calls, install = driver
    install([NS(model_dump_json=lambda **kw: "{}")])

    def fail_write(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(OSError, match="disk full"):
        generate.main()
    assert len(calls) == 1
    assert not output.exists()


def test_failed_preflight_cannot_leave_stale_submission(driver, monkeypatch):
    output, calls, install = driver
    install([])

    def fail_gpu(target):
        raise RuntimeError("no CUDA")

    monkeypatch.setattr(assets, "check_gpu", fail_gpu)
    with pytest.raises(RuntimeError, match="no CUDA"):
        generate.main()
    assert not output.exists() and not calls
