{prompt}

---

## How this task is run

- Write your final answer to `/workspace/solution.py`: one self-contained Python module that defines `class ModelNew(nn.Module)` with the same constructor and `forward` signature as `Model`. Inline CUDA via `torch.utils.cpp_extension.load_inline` is the expected approach.
- The reference architecture is at `/workspace/reference.py`. You have one NVIDIA H100 (sm_90), CUDA 12.8, PyTorch 2.9, and a shell; you may compile, test, and profile as much as you like within the time limit.
{check_note}
- Precision: fp32 inputs and outputs.{verified_note}
- Do not edit `reference.py`; the grader uses its own copy.
