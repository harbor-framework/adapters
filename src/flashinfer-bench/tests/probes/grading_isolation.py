"""Characterize the pinned runner's trust violation, without CUDA or model calls.

This is a regression probe, not a replacement runner or a sandbox. CPU tensors
exercise the actual PythonBuilder and DefaultEvaluator. CUDA synchronization is
disabled; a fixed timing sentinel makes timer replacement observable without
claiming any GPU measurement. All candidate imports occur in subprocesses, so
the probe does not poison pytest's interpreter.
"""

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

PIN = "15618a67e8d7b7f49ca61b5ba3b9f26a876d0bee"
TIMING_SENTINEL_MS = 123.0
FORGED_LATENCY_MS = 0.001


def load_upstream(root):
    for suffix in (
        "",
        ".bench",
        ".bench.runner",
        ".bench.evaluators",
        ".compile",
        ".compile.builders",
    ):
        name = "flashinfer_bench" + suffix
        package = types.ModuleType(name)
        package.__path__ = [str(root.joinpath(*name.split(".")))]
        sys.modules[name] = package
    data = importlib.import_module("flashinfer_bench.data")
    runnable = importlib.import_module("flashinfer_bench.compile.runnable")
    sys.modules["flashinfer_bench.compile"].Runnable = runnable.Runnable
    # No build_baseline call: use the pinned reference directly on CPU.
    sys.modules["flashinfer_bench.compile"].BuilderRegistry = None
    timing = types.ModuleType("flashinfer_bench.bench.timing")
    timing.time_runnable = lambda *args: TIMING_SENTINEL_MS
    sys.modules[timing.__name__] = timing
    return data


def fixture(root, definition_path):
    import torch

    data = load_upstream(root)
    checker = importlib.import_module("flashinfer_bench.bench.evaluators.default")
    config = importlib.import_module("flashinfer_bench.bench.config")
    raw_definition = definition_path.read_bytes()
    if hashlib.sha256(raw_definition).hexdigest() != (
        "15a53ef0b38deae0b5909b45b3e158479d5fd62ec785708dc6acf3ad9d1b5843"
    ):
        raise ValueError("Expected the unchanged pinned rmsnorm_h128 definition")
    definition = data.Definition.model_validate_json(raw_definition)
    if definition.name != "rmsnorm_h128":
        raise ValueError("This probe is deliberately restricted to rmsnorm_h128")
    torch.cuda.synchronize = lambda device=None: None
    inputs = [
        torch.ones((1, 128), dtype=torch.bfloat16),
        torch.ones(128, dtype=torch.bfloat16),
    ]
    reference_scope = {}
    # Execute only the mathematical reference from the SHA-256 checked fixture.
    exec(definition.reference, reference_scope)  # noqa: S102
    reference = reference_scope["run"](*inputs)
    kwargs = {
        "definition": definition,
        "inputs": [inputs],
        "ref_outputs": [[reference]],
        "cfg": config.ResolvedEvalConfig(),
        "log_path": None,
        "device": "cpu",
    }
    return torch, data, checker, kwargs


def child(root, definition_path, mode):
    torch, data, checker, kwargs = fixture(root, definition_path)
    definition = kwargs["definition"]
    # All controls use the same real pinned reference or the same wrong tensor.
    wrong = (
        "import torch\ndef run(hidden_states, weight):\n"
        "    return torch.zeros_like(hidden_states)\n"
    )
    checker_tamper = (
        "import importlib\n"
        "judge = importlib.import_module('flashinfer_bench.bench.evaluators.default')\n"
        "judge.compute_error_stats = lambda *args: (0., 0., False, 1.)\n"
    )
    timer_tamper = (
        "import importlib\n"
        "judge = importlib.import_module('flashinfer_bench.bench.evaluators.default')\n"
        f"judge.time_runnable = lambda *args: {FORGED_LATENCY_MS}\n"
    )
    source = {
        "correct": definition.reference,
        "wrong": wrong,
        "checker_tamper": checker_tamper + wrong,
        "timer_tamper": timer_tamper + definition.reference,
    }[mode]
    solution = data.Solution(
        name=mode,
        definition=definition.name,
        author="isolation-probe",
        spec=data.BuildSpec(
            language="python",
            target_hardware=["B200"],
            entry_point="main.py::run",
            destination_passing_style=False,
        ),
        sources=[data.SourceFile(path="main.py", content=source)],
    )
    builder = importlib.import_module(
        "flashinfer_bench.compile.builders.python_builder"
    ).PythonBuilder()
    with tempfile.TemporaryDirectory(prefix="fib-isolation-probe-") as cache:
        os.environ["FIB_CACHE_PATH"] = cache
        candidate = builder.build(definition, solution)
        try:
            evaluation = checker.DefaultEvaluator.evaluate(
                **kwargs,
                sol_runnable=candidate,
                ref_mean_latency_ms=TIMING_SENTINEL_MS,
            )
            output = candidate(*kwargs["inputs"][0])
            return {
                "status": evaluation.status.value,
                "latency_ms": (
                    evaluation.performance.latency_ms
                    if evaluation.performance
                    else None
                ),
                "output": output.to(dtype=torch.float32).tolist(),
            }
        finally:
            candidate.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--definition", type=Path, required=True)
    parser.add_argument(
        "--child", choices=("correct", "wrong", "checker_tamper", "timer_tamper")
    )
    args = parser.parse_args()
    revision = subprocess.check_output(
        ["git", "-C", str(args.upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != PIN or subprocess.check_output(
        ["git", "-C", str(args.upstream), "diff", "HEAD", "--", "flashinfer_bench"]
    ):
        raise ValueError("The probe requires an unchanged pinned upstream checkout")
    if args.child:
        print(json.dumps(child(args.upstream, args.definition, args.child)))
        return

    cases = {}
    for mode in ("correct", "wrong", "checker_tamper", "timer_tamper"):
        run = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--upstream",
                str(args.upstream.resolve()),
                "--definition",
                str(args.definition.resolve()),
                "--child",
                mode,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        cases[mode] = json.loads(run.stdout)

    # A trusted process can recheck data without importing the submitted module.
    # This demonstrates only checker separation, not OS isolation or trusted timing.
    torch, _, checker, kwargs = fixture(args.upstream, args.definition)
    output = torch.tensor(cases["checker_tamper"]["output"], dtype=torch.bfloat16)
    replay = types.SimpleNamespace(
        metadata=types.SimpleNamespace(destination_passing_style=False)
    )

    class Replay:
        metadata = replay.metadata

        def __call__(self, *inputs):
            return output

    _, checked = checker.DefaultEvaluator.check_correctness(
        **kwargs, sol_runnable=Replay()
    )
    for result in cases.values():
        del result["output"]
    print(
        json.dumps(
            {
                "upstream_revision": PIN,
                "definition": "rmsnorm_h128",
                "device": "cpu",
                "gpu_timing_exercised": False,
                "timing_sentinel_ms": TIMING_SENTINEL_MS,
                "cases": cases,
                "separate_checker_status": checked.status.value
                if checked
                else "PASSED",
                "production_isolation_fixed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
