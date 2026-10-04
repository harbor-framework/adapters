## JAXBench → Harbor Adapter

**Notice:**
1. This is the template file for harbor adapter README. Please follow this structure and fill the contents and/or replace parts if necessary. If a prior version of the adapter code and README exists (i.e., under the `terminal-bench` repo), you could reuse some sections, but make sure they align with the new requirements and commands.
2. Make sure your default task preparation dir is `datasets/jaxbench` instead of other default paths like `tasks/jaxbench`. If the prior version is using a different path, please update it accordingly.
3. Read and understand our tutorial before you go — [agent version](https://www.harborframework.com/docs/datasets/adapters) or [human version](https://www.harborframework.com/docs/datasets/adapters-human).

## Overview

Describe at a high level what JAXBench evaluates. Include:
- Task types, domains, languages, dataset size/splits
- Provenance (paper/repo), licensing notes, known constraints
- Any differences from similarly named benchmarks
- Explicitly state how many tasks are in this adapter and how that number is derived from the source benchmark
- Briefly mention the main modifications for adaptation (e.g., prompt changes for agents vs. LLMs, excluded tasks and reasons)

## What is JAXBench?

Write a short paragraph explaining the original benchmark, goals, and audience. Link to the paper and/or site. Clarify scoring/metrics used in the original.

## Adapter Features

Bullet the notable features your adapter implements. Examples to tailor/remove:
- Automatic repo/data management (clone, cache, cleanup)
- Comprehensive task generation (schema extraction, solution validation, id mapping)
- Dockerized environments; language/toolchain support
- Evaluation specifics (pytest, judge, diff checks, speedups, resource limits)
- Prompt adaptations vs. the original harness (if any)

## Generated Task Structure

Show the on-disk layout produced by this adapter. Replace or extend as needed:
```
jaxbench/
├── {task_id}/
│   ├── task.toml                 # Task configuration
│   ├── instruction.md            # Task instructions for the agent
│   ├── environment/              # Container definition
│   │   └── Dockerfile
│   ├── solution/                 # Oracle/golden solution (optional if original benchmark doesn't have one)
│   │   └── solve.sh
│   └── tests/                    # Test assets and scripts
│       └── test.sh               # Test execution script
```

And make sure your adapter code has a task-template directory that includes these files, even if they are empty or dummy. The adapter reads from the `task-template/` directory to replace/add contents and generate task directories correspondingly.

The adapter is scaffolded as a Python package via `uv init --package`. A typical adapter code directory looks as follows:
```
adapters/jaxbench/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
└── src/jaxbench/
    ├── __init__.py
    ├── adapter.py
    ├── main.py
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/
        │   └── Dockerfile
        ├── solution/
        │   └── solve.sh
        └── tests/
            └── test.sh
```

> **Note:** `adapter.py` should define a `<Benchmark>Adapter` class with a `run()` method if possible; `main.py` constructs the adapter and calls `run()` through the standard CLI flags.


## Run Evaluation / Harness
Harbor Registry & Datasets makes running adapter evaluation easy and flexible.

### Running with Datasets Registry

 Simply run

```bash
# Use oracle agent (reference solution)
uv run harbor run -d jaxbench

# Use your specified agent and model
uv run harbor run -d jaxbench -a <agent_name> -m "<model_name>"
```
from the harbor root to evaluate on the entire dataset.

> [For adapter creators]: You will need to (1) upload the prepared task directories to https://github.com/laude-institute/harbor-datasets (2) Add your dataset entries to [registry.json](../../../registry.json) following a similar format as others. Only after all the PRs are merged, can you run the above scripts (otherwise the datasets are not yet registered). At development time, use the scripts below to run experiments.

However, if you choose to prepare the task directories locally and/or with custom versions/subsets for evaluation, you may either use `harbor run` or `harbor trial`. Instructions for using the adapter code to prepare task directories are provided in the [Usage](#usage-create-task-directories) session.

### Using Job Configurations
The example configuration file(s) for the adapter is provided under `harbor/adapters/jaxbench`. You may either use `-c path/to/configuration.yaml` or `-p path/to/dataset` to run evaluation on the entire benchmark after preparing the task directories locally.

> [For adapter creators]: Please specify the file(s), e.g., `run_jaxbench.yaml`, `run_jaxbench-python.yaml` for subsets/versions. Examples of config yaml can be seen from [harbor/examples/configs](../../../examples/configs/).

```bash
# From the repository root
# Run a job with the default adapter configuration
uv run harbor run -c adapters/jaxbench/run_jaxbench.yaml -a <agent_name> -m "<model_name>"

# Or run a job without configuration yaml but instead with locally prepared dataset path
uv run harbor run -p datasets/jaxbench -a <agent_name> -m "<model_name>"

# Resume a previously started job
uv run harbor job resume -p /path/to/jobs/directory
```

Results are saved in the `jobs/` directory by default (configurable via `jobs_dir` in the YAML config).

### Running Individual Trial

For quick testing or debugging a single task:

```bash
# Run a single task with oracle (pre-written solution)
uv run harbor trial start -p datasets/jaxbench/<task_id>

# Run a single task with a specific agent and model
uv run harbor trial start -p datasets/jaxbench/<task_id> -a <agent_name> -m "<model_name>"
```

Trial outputs are saved in the `trials/` directory by default (configurable via `--trials-dir`).


## Usage: Create Task Directories

```bash
cd adapters/jaxbench
uv run jaxbench --output-dir ../../datasets/jaxbench
```

Available flags:
- `--output-dir` — Directory to write generated tasks (defaults to `datasets/jaxbench` at the repo root)
- `--limit` — Generate only the first N tasks
- `--overwrite` — Overwrite existing tasks
- `--task-ids` — Only generate specific task IDs

Tasks are written to `datasets/jaxbench/` with one directory per task. Each task follows the structure shown in ["Generated Task Structure"](#generated-task-structure) above.

## Comparison with Original Benchmark (Parity)

Summarize how you validated fidelity to the original benchmark. Include a small table of headline metrics and a pointer to `parity_experiment.json`. Report each score as **mean ± sample SEM**.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| \<agent\>@\<agent_version\> | \<model\> | \<metric\> | \<n\> | \<size\> | \<x% ± y%\> | \<x% ± y%\> |

If there's a prior version parity experiment done in `terminal-bench`:
- If your parity for Harbor is a direct comparison to the original benchmark (which we recommend if claude-4.5-haiku is easily supported), then you may only include these scores and do not need to include the `terminal-bench` parity.
- However, if you are comparing to `terminal-bench` adapters, then please include both parity scores to show that "original <--> terminal bench adapter" and then "terminal bench adapter <--> harbor adapter".

Reproduction requirements and steps (mandatory):
- Which repo/fork and commit to use for the original benchmark; which scripts/commands to run; any env variables needed
- Which commands to run in Harbor to reproduce adapter-side results:
  ```bash
  uv run harbor run -c adapters/jaxbench/run_jaxbench.yaml -a <agent> -m "<model>"
  ```
- How to interpret the results/scores; if metrics are non-trivial, briefly explain their computation

## Notes & Caveats

**Task count: 49 of 50.** The adapter converts JAXBench level1 at upstream commit
[`7afeb78`](https://github.com/AI-Hypercomputer/accelerator-agents/tree/7afeb78188383e857f8fe12d98d308eb1fd30435/JAXBench)
(50 workloads) and excludes one:

| Excluded workload | Reason |
|-------------------|--------|
| `11p_Megablox_GMM` | Upstream `baseline.py` cannot be compiled by the upstream harness: `workload()` receives `max_expert_size` as a positional argument, which `jax.jit` traces, but uses it as a static array shape (`baseline.py:42`). `python -m JAXBench evaluate` therefore errors while running the baseline, before any candidate kernel is graded, so no agent can solve this task. |

The exclusion list lives in `EXCLUDED_WORKLOADS` in `src/jaxbench/adapter.py`.

**Oracle solutions.** For tasks where upstream ships a hand-written Pallas kernel (`optimized.py`), the
oracle is that kernel. For four tasks, the upstream Pallas kernel fails the upstream harness at the pinned
commit, so the oracle falls back to the baseline itself (expected speedup ≈1.0×), the same as the 42 tasks
without a Pallas kernel. These tasks remain valid for agents: the baseline compiles and grades correctly.

| Workload | Upstream `optimized.py` failure |
|----------|---------------------------------|
| `1p_Flash_Attention` | Output differs from baseline (max diff 0.0625 > 1e-2 tolerance) |
| `2p_GQA_Attention` | Output differs from baseline (max diff 0.0625 > 1e-2 tolerance) |
| `6p_Paged_Attention` | `workload()` takes 5 arguments but `create_inputs()` returns 6 |
| `7p_Ragged_Paged_Attention` | Scoped VMEM OOM at compile time on TPU v6e (34.39 MiB > 32 MiB limit) |

The fallback list lives in `BROKEN_PALLAS_ORACLES` in `src/jaxbench/adapter.py`; each task records its
oracle source in `task.toml` (`[metadata] jaxbench_oracle = "pallas" | "baseline"`). The Pallas kernels are
still copied into `tests/` because the upstream harness benchmarks `optimized.py` (when present) for its
`speedup_vs_pallas` report; that step does not affect correctness or the reward.

**Oracle verification.** The oracle is judged on correctness (`correct = 1` on every task), not on the
reward being exactly 1.0: speedup is a device-timing ratio, so a baseline oracle scores ≈1.0× with small
noise (e.g. 1.01×), and a Pallas oracle scores its real speedup over XLA. The same convention is used by the
`algotune` adapter, which also uses the baseline as its oracle. Two oracle configs are provided:

| Config | Dataset | Oracle | Tasks |
|--------|---------|--------|-------|
| `run_jaxbench_gke_tpu_v6e_xla_oracle.yaml` | `datasets/jaxbench-xla-oracle` (`--oracle baseline`) | XLA baseline for every task | 49 |
| `run_jaxbench_gke_tpu_v6e_pallas_oracle.yaml` | `datasets/jaxbench` (default) | Upstream Pallas kernel | 3 (`3p`, `4p`, `8p`) |

`run_jaxbench_gke_tpu_v6e.yaml` is the reference config for the full adapted dataset (`datasets/jaxbench`).

**Hardware.** Every task requires one TPU v6e chip (`[environment.tpu] type = "v6e"`, `topology = "1x1"`),
which Harbor provides only through the GKE environment. See `run_jaxbench_gke_tpu_v6e.yaml`.

## Installation / Prerequisites

Adapters are managed as standalone uv Python packages. You can add or remove dependencies using `uv add` / `uv remove` from the adapter directory:

```bash
cd adapters/jaxbench
uv add datasets  # add a dependency
uv remove datasets  # remove a dependency
```

List environment setup specific to this adapter (edit as needed):
- Docker installed and running
- Harbor installed and working (see main repository README)
- Python environment with dependencies:
  ```bash
  cd adapters/jaxbench
  uv sync
  ```
- Dataset-specific steps (e.g., creds, downloads):
  - API keys for agents/models (export as environment variables)
  - Large docker images, toolchains, or dataset downloads
  - Any benchmark-specific dependencies

## Troubleshooting

List frequent issues and fixes (docker cleanup, timeouts, flaky tests, etc.).

## Citation

Provide BibTeX or links to cite the original benchmark (and this adapter if desired):
```bibtex
@article{<key>,
  title={<benchmark_name>: <paper title>},
  author={<authors>},
  year={<year>},
  url={<paper_or_repo_url>}
}
```

## Authors & Contributions
This adapter is developed and maintained by [<your_name>](mailto:<your_email>) from the Harbor team.

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines

## Acknowledgement

If you used API keys provided via [adapters/parity_api_instructions.md](../parity_api_instructions.md) for running parity experiments, please include the following acknowledgement:

> API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).