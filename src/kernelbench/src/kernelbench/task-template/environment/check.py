"""Local self-check: compile solution.py and compare it to reference.py on the visible inputs."""

from pathlib import Path

import torch
from kernelbench.eval import eval_kernel_against_ref

ref = Path("/workspace/reference.py").read_text()
sol = Path("/workspace/solution.py").read_text()
r = eval_kernel_against_ref(
    ref,
    sol,
    num_correct_trials=2,
    num_perf_trials=20,
    measure_performance=True,
    verbose=False,
    device=torch.device("cuda:0"),
)
print(
    r.model_dump_json(indent=2, exclude={"metadata"})
    if r
    else "eval returned None (retry)"
)
if r and r.metadata:
    for k, v in r.metadata.items():
        print(f"{k}: {str(v)[:2000]}")
