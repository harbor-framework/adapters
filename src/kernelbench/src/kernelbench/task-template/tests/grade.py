"""Grade /workspace/solution.py against /tests/reference.py on this GPU.

kernelbench           upstream kernelbench.eval.eval_kernel_against_ref: 5 seeded
                      correctness trials (atol=rtol=1e-4), 100 cuda-event timing
                      trials, speedup = PyTorch fp32 eager time / kernel time.
kernelbench-verified  facebookresearch/kernel_bench_verified src.eval: the same plus
                      the 4 hidden input distributions must all pass (atol=rtol=1e-3);
                      speedup is against PyTorch with TF32 enabled on the same
                      inputs and timer; peak memory is recorded.

reward = correct (0/1). fast_1 (correct and speedup > 1) and speedup are reported as
extra metrics; KernelBench's headline fast_p is the mean of fast_1 over tasks.
"""

import json
import os
import sys
from pathlib import Path

import torch

VARIANT = os.environ["KB_VARIANT"]
OUT = Path("/logs/verifier")
SOL = Path("/workspace/solution.py")
REF = Path("/tests/reference.py").read_text()
N_CORRECT, N_PERF = 5, 100
ZERO = {"reward": 0, "correct": 0, "compiled": 0, "fast_1": 0, "speedup": 0}


def write(reward: dict, details: dict):
    (OUT / "reward.json").write_text(json.dumps(reward))
    (OUT / "reward.txt").write_text(str(reward["reward"]))
    (OUT / "details.json").write_text(json.dumps(details, indent=2, default=str))
    print(json.dumps(reward))


if not SOL.exists():
    write(ZERO, {"error": "no /workspace/solution.py"})
    sys.exit(0)
sol = SOL.read_text()
device = torch.device("cuda:0")
details = {"variant": VARIANT, "gpu": torch.cuda.get_device_name(0)}

if VARIANT == "kernelbench":
    from kernelbench.eval import eval_kernel_against_ref

    r = eval_kernel_against_ref(
        REF,
        sol,
        num_correct_trials=N_CORRECT,
        num_perf_trials=N_PERF,
        measure_performance=True,
        timing_method="cuda_event",
        device=device,
        precision=torch.float32,
        backend="cuda",
    )
    ref_ms = r.ref_runtime if r else -1
else:
    sys.path.insert(0, "/opt/kbv")
    from src import eval as kbv

    r = kbv.eval_kernel_against_ref(
        REF,
        sol,
        num_correct_trials=N_CORRECT,
        num_perf_trials=N_PERF,
        measure_performance=True,
        device=device,
        precision=torch.float32,
        hidden_test_path="/tests/hidden.py",
    )
    # TF32 PyTorch baseline on the standard inputs, same timer as the kernel.
    Model, get_init_inputs, get_inputs = kbv.load_original_model_and_inputs(REF, {})

    def to_dev(x):  # cast floats only; int labels/indices keep their dtype
        if not isinstance(x, torch.Tensor):
            return x
        return (x.to(torch.float32) if x.is_floating_point() else x).to(device)

    with torch.no_grad():
        kbv.set_seed(42)
        init = [to_dev(x) for x in get_init_inputs()]
        kbv.set_seed(42)
        model = Model(*init).to(device=device, dtype=torch.float32)
        kbv.set_seed(42)
        inputs = [to_dev(x) for x in get_inputs()]
        prev = torch.get_float32_matmul_precision(), torch.backends.cudnn.allow_tf32
        torch.set_float32_matmul_precision("high")
        torch.backends.cudnn.allow_tf32 = True
        times = kbv.time_execution_with_cuda_event(
            model, *inputs, num_trials=N_PERF, verbose=False, device=device
        )
        base_mem = kbv.get_memory_stats(model, *inputs, device=device)["peak_bytes"]
        torch.set_float32_matmul_precision(prev[0])
        torch.backends.cudnn.allow_tf32 = prev[1]
    ref_ms = kbv.get_timing_stats(times)["mean"]
    details.update(baseline="torch_tf32", baseline_peak_bytes=base_mem)
    if r and r.correctness and getattr(r, "peak_memory", -1) > 0:
        details["mem_eff"] = base_mem / r.peak_memory

if r is None:
    # Upstream returns None when the shared compile lock is contended.
    write(ZERO, {**details, "error": "eval returned None"})
    sys.exit(0)

compiled, correct = bool(r.compiled), bool(r.correctness)
speedup = ref_ms / r.runtime if correct and r.runtime > 0 and ref_ms > 0 else 0.0
details.update(
    compiled=compiled,
    correct=correct,
    runtime_ms=r.runtime,
    ref_runtime_ms=ref_ms,
    speedup=speedup,
    peak_memory=getattr(r, "peak_memory", None),
    metadata=r.metadata,
)
write(
    {
        "reward": int(correct),
        "correct": int(correct),
        "compiled": int(compiled),
        "fast_1": int(correct and speedup > 1.0),
        "speedup": round(speedup, 4),
    },
    details,
)
