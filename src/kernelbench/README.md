## KernelBench → Harbor Adapter

## Overview

This adapter turns the 250 problems of [KernelBench](https://github.com/ScalingIntelligence/KernelBench) (levels 1-3) into Harbor tasks. Each task gives the agent a PyTorch reference architecture (`Model`) and asks for a faster drop-in replacement (`ModelNew`) built on custom CUDA kernels. The answer is compiled and graded on a GPU.

The adapter produces two datasets from the same problems. They differ only in how a solution is graded, and both reuse the upstream grading code unchanged:

| Dataset | Tasks | Grader | Correctness | Speed baseline |
|---|---|---|---|---|
| `kernelbench` | 249 | [ScalingIntelligence/KernelBench](https://github.com/ScalingIntelligence/KernelBench) `kernelbench.eval` @ `423217d` | 5 seeded random inputs, atol = rtol = 1e-4 | PyTorch fp32 eager |
| `kernelbench-verified` | 246 | [facebookresearch/kernel_bench_verified](https://github.com/facebookresearch/kernel_bench_verified) `src.eval` @ `3fdf6fe` | the above, plus 4 hidden input distributions (×1, ×3, ×0.01, ×−1), atol = rtol = 1e-3 | PyTorch with TF32 enabled |

Tasks are excluded as follows. Both datasets drop L2-66: it applies training-mode dropout, so even the PyTorch reference fails its own correctness check. `kernelbench-verified` also drops L2-23, L2-80 and L2-83, which KernelBench-Verified removes from its leaderboard because their output is constant zero. That gives 250 − 1 = 249 tasks for `kernelbench` and 250 − 4 = 246 for `kernelbench-verified`.

The upstream harnesses are one-shot: they send the prompt to an LLM and grade its single reply. The adapter changes this in one way. It keeps each benchmark's prompt verbatim and appends a short section addressed to an agent: where to write the answer, a local `check.py` for testing, and the hardware available. The agent may then compile, test and profile freely within the time limit.

## What is KernelBench?

KernelBench ([Ouyang et al., 2025](https://arxiv.org/abs/2502.10517)) measures whether language models can write GPU kernels that are both correct and faster than PyTorch. It contains 250 problems at three levels: single operators (L1), fused operator sequences (L2), and full architectures (L3). The headline metric is **fast_p**: the fraction of problems where the generated kernel is correct and more than `p`× faster than the PyTorch reference. `fast_1` is the usual summary.

[KernelBench-Verified](https://github.com/facebookresearch/kernel_bench_verified) (Zhang et al., 2026) re-grades the same problems more strictly, so that numerical shortcuts and input-specific hacks no longer pass:

- **Hidden inputs:** correctness must also hold on hidden inputs of different magnitudes and signs.
- **Stronger baseline:** speed is compared against PyTorch with TF32 Tensor Cores enabled, removing the "free" speedup from simply switching fp32 matmuls to TF32.
- **Withheld inputs:** for four problems that were known to be reward-hacked, the prompt hides the input definitions.

## Adapter Features

- **Pinned upstream sources.** The adapter checks out both upstream repos at fixed commits into `~/.cache/harbor-kernelbench`; change the location with `--source-dir`. Prompts are produced by each benchmark's own prompt builder, called unmodified: the one-shot CUDA template in KernelBench's `prompts.toml`, and KernelBench-Verified's `prompt_generate_custom_cuda_from_prompt_template` together with its `strip_test_config` for the four input-blind problems.
- **Upstream graders, unmodified.** `tests/grade.py` calls the upstream `eval_kernel_against_ref` with that benchmark's own settings: 5 correctness trials, 100 CUDA-event timing trials, fp32. For KernelBench-Verified it also passes the problem's hidden-test file. The TF32 baseline is timed in the same process, with the same timer and the same inputs.
- **Separate verifier container.** `verifier.environment_mode = "separate"`, so grading runs in a fresh container built from the task image. The agent cannot have altered the eval code, the reference, or the GPU state. Only `/workspace/solution.py` is carried over, as an artifact.
- **Hidden tests stay hidden.** KernelBench-Verified's hidden inputs are written to `tests/hidden.py` and are not part of the agent image.
- **One GPU per trial.** `environment/docker-compose.yaml` reserves one NVIDIA GPU per trial, because timing is only meaningful if the kernel has the card to itself.
- **Rewards** (`/logs/verifier/reward.json`):
  - `reward` = `correct` (0/1), so the oracle scores 1.0.
  - `fast_1` = correct and speedup > 1; its mean over tasks is KernelBench's fast_1.
  - `compiled` (0/1).
  - `speedup` = baseline time / kernel time, or 0 if the solution is incorrect.
  - Full details, including timings, peak memory and compile/runtime errors, go to `/logs/verifier/details.json`.
- **Oracle.** The PyTorch reference itself, renamed `ModelNew`. It shows that the image builds, the reference runs, and the grader accepts a correct answer.

## Generated Task Structure

```
datasets/kernelbench/                          # or datasets/kernelbench-verified/
├── kernelbench-l1-019-relu/
│   ├── task.toml                              # name = "kernelbench/kernelbench-l1-019-relu"
│   ├── instruction.md                         # upstream prompt + agent addendum
│   ├── environment/
│   │   ├── Dockerfile                         # pytorch 2.9.1 / CUDA 12.8 + pinned upstream graders
│   │   ├── docker-compose.yaml                # 1 x NVIDIA GPU reservation
│   │   ├── reference.py                       # visible reference (input-stripped for blind tasks)
│   │   └── check.py                           # local self-check (absent for blind tasks)
│   ├── solution/
│   │   ├── solve.sh                           # oracle: reference renamed ModelNew
│   │   └── reference.py
│   └── tests/
│       ├── test.sh
│       ├── grade.py                           # calls the upstream grader
│       ├── reference.py                       # grader's copy of the reference
│       └── hidden.py                          # kernelbench-verified only: hidden inputs
```

Adapter code:

```
src/kernelbench/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_kernelbench.yaml
├── run_kernelbench-verified.yaml
└── src/kernelbench/
    ├── __init__.py
    ├── adapter.py
    ├── main.py
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/{Dockerfile, docker-compose.yaml, check.py}
        ├── solution/solve.sh
        └── tests/{test.sh, grade.py}
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the datasets are published:

```bash
# Oracle (reference solution)
harbor run -d kernelbench/kernelbench
harbor run -d kernelbench/kernelbench-verified

# An agent and model
harbor run -d kernelbench/kernelbench-verified -a codex -m "openai/<model>" -n 8
```

Every trial needs one NVIDIA GPU, so set `-n` to at most the number of GPUs on the host.

### Using Job Configurations

```bash
# From the repository root, after generating the datasets (see Usage)
harbor run -c src/kernelbench/run_kernelbench.yaml
harbor run -c src/kernelbench/run_kernelbench-verified.yaml

# Or point at a locally generated dataset
harbor run -p datasets/kernelbench-verified -a <agent> -m "<model>"
```

### Running Individual Trial

```bash
harbor trial start -p datasets/kernelbench/kernelbench-l1-019-relu
harbor trial start -p datasets/kernelbench/kernelbench-l1-019-relu -a <agent> -m "<model>"
```

## Usage: Create Task Directories

```bash
cd src/kernelbench
uv sync
uv run kernelbench --variant kernelbench          --output-dir ../../datasets/kernelbench
uv run kernelbench --variant kernelbench-verified --output-dir ../../datasets/kernelbench-verified
```

Flags:
- `--output-dir`: where to write tasks (default: `datasets/<variant>` at the repo root)
- `--limit`: generate only the first N tasks
- `--overwrite`: regenerate tasks that already exist
- `--task-ids`: only these tasks, e.g. `kernelbench-l1-019 kernelbench-verified-l3-035`
- `--variant`: `kernelbench` (default) or `kernelbench-verified`
- `--levels`: subset of `1 2 3`
- `--source-dir`: where the pinned upstream repos are checked out

Generation needs `git` and network access to GitHub. It does not need a GPU or torch.

## Comparison with Original Benchmark (Parity)

Parity has not been run yet; the plan (agent, model, number of runs, subset) is being agreed with the Harbor team. The upstream harness is one-shot LLM generation with no agent loop, so the original side will be a fork of each upstream repo that runs the same agent CLI under the same instruction, image, GPU and timeout (Scenario 2 in the adapter guide). The proposed parity metrics are the per-task binary rates `correct` and `fast_1`. Mean speedup is not proposed: it is heavy-tailed (a single task can reach several hundred ×) and too noisy to use for a range-overlap test.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| TBD | TBD | correct | TBD | TBD | TBD | TBD |

Reproduction (Harbor side):

```bash
harbor run -c src/kernelbench/run_kernelbench-verified.yaml -a <agent> -m "<model>"
```

## Notes & Caveats

- **Upstream bug, patched in the image.** In both repos, `_process_input_tensor` casts every input tensor to the eval precision. This turns int64 class labels into floats, so problems with integer inputs (e.g. L1-95 CrossEntropyLoss) fail even for the reference. The Dockerfile patches the line so that only floating-point tensors are cast, and the TF32 baseline in `grade.py` casts the same way. Without the patch, the oracle cannot reach 100%. The KernelBench bug is reported as [ScalingIntelligence/KernelBench#151](https://github.com/ScalingIntelligence/KernelBench/issues/151), with open fixes in #152 and #185. KernelBench-Verified carries the same code (`src/eval.py`).
- **Excluded tasks.** L2-66 is excluded from both datasets (training-mode dropout, unscoreable). L2-23/80/83 are excluded from `kernelbench-verified` only, following its leaderboard. `kernelbench` keeps them for fidelity to the original, but they are degenerate: the output is constant zero, so returning zeros is "correct" and arbitrarily fast. L2-80 has been seen at more than 500× speedup.
- **Prompt addendum.** Both upstream prompts are kept verbatim. The appended agent section (output path, `check.py`, hardware, and for KernelBench-Verified a note that grading uses hidden inputs and a TF32 baseline) is a prompt modification and will be applied identically on the original side for parity.
- **Agent environment.** Agents get network access, one GPU, 16 CPUs, 256 GB RAM, and a 60-minute limit (90 minutes for L3). L1-45 materializes a 16 GB input, so lower memory limits kill the reference.
- **Timing noise.** Speedups come from 100 CUDA-event trials on a dedicated GPU. Across two full oracle runs on H100, the oracle's speedup (ideally 1.0) had a median of 1.00 and a 5th percentile of 0.98. On `kernelbench-verified`, the oracle (fp32 PyTorch) is slower than the TF32 baseline on matmul- and conv-heavy problems; that is expected and does not affect its `reward` (= correct).
- **Model refusals.** Claude Code with Claude Opus 5.5 / Sonnet 5.5 refused about a third of the tasks under the provider's usage-policy classifier (`AgentSafetyRefusalError`), including plain matmul problems. This is a property of the model, not of the tasks; it should be considered when choosing a parity model.
- **Hardware.** Tasks declare `gpu_types = ["H100"]` and the instruction mentions sm_90. Kernels are compiled for whatever GPU is present, but timings and speedups are only comparable on the same GPU model.

## Installation / Prerequisites

- Docker with the NVIDIA Container Toolkit and at least one NVIDIA GPU (H100 for comparable numbers)
- Harbor CLI (`uv tool install harbor`)
- `git` and network access for task generation and image builds (pip, GitHub)
- The first image build pulls `pytorch/pytorch:2.9.1-cuda12.8-cudnn9-devel` (about 10 GB). All tasks share every layer except the final `COPY`.

```bash
cd src/kernelbench
uv sync
```

## Troubleshooting

- **`could not select device driver "nvidia"`:** the NVIDIA Container Toolkit is missing, or Docker is not configured to use it.
- **Verifier killed with no reward:** the container hit its memory limit. Keep `memory_mb = 262144` (L1-45 needs a 16 GB input).
- **`eval returned None`:** the upstream grader could not take its compile lock. Re-run the trial.
- **Trials waiting on GPUs:** each trial reserves one GPU. Lower `n_concurrent_trials` to the number of GPUs.

## Citation

```bibtex
@misc{ouyang2025kernelbenchllmswriteefficient,
      title={KernelBench: Can LLMs Write Efficient GPU Kernels?},
      author={Anne Ouyang and Simon Guo and Simran Arora and Alex L. Zhang and William Hu and Christopher Ré and Azalia Mirhoseini},
      year={2025},
      eprint={2502.10517},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/2502.10517},
}

@article{zhang2026kernelbenchverified,
  title={KernelBench-Verified: Do LLM-Generated Kernels Actually Beat PyTorch?},
  author={Zhang, Yunxiang and Yu, Ping and Wang, Jianyu and Fan, Max (Xiangjun) and Reed, Julian and Mirhoseini, Azalia and Su, Will},
  journal={arXiv preprint},
  year={2026}
}
```

## Authors & Contributions

This adapter is developed and maintained by [haoqingwang](mailto:1506751656@qq.com). It builds on the earlier KernelBench adapter work by Simon Guo in [harbor-framework/harbor#999](https://github.com/harbor-framework/harbor/pull/999).

**Issues and Contributions:**
- Submit Issues and Pull Requests to [harbor-framework/adapters](https://github.com/harbor-framework/adapters)
