# ControlArena vLLM honest metrics maintenance

## Overview

This adapter generates the single validated main task `fix_prefix_cache_metrics_reset` from ControlArena’s vLLM setting. The agent edits the logging module that reports prefix-cache hit rates. A separate verifier computes the Git diff against the pinned baseline and uses ControlArena’s honest PR scorer. [Setting documentation](https://control-arena.aisi.org.uk/settings/vllm.html) · [Suite coverage](../../docs/control-arena.md)

## What is ControlArena vLLM?

ControlArena evaluates code changes to versioned vLLM repositories. The release inventory lists 19,737 main tasks across the full group and 32 main tasks in the validated group. This adapter supports one reviewed maintenance task from that validated group. Its source data identifies the task as requiring no internet during the agent’s work. [Release inventory](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_vllm.md) · [Dataset revision](https://huggingface.co/datasets/RoganInglis/vllm-control-arena/tree/f6ea5be8a1ef134bef49ff415992fb7365d325f3)

## Adapter Features

- The generator verifies the dataset row, its prompt digest, the parent and reference source identities, the changed path and the upstream Apache license. The original user prompt is retained verbatim. The agent receives the baseline version of `vllm/v1/metrics/loggers.py` and its license.
- The verifier compares the submitted module with a private baseline, restores the resulting Git diff under the native `submission_diff` key, and calls `combined_pr_scorer` with honest metadata. This is the scorer result that upstream `vllm_scorer` returns in honest mode. The candidate source is treated as text. [Pinned setting scorer](https://github.com/UKGovernmentBEIS/control-arena/blob/v20.1.1/control_arena/settings/vllm/task/scorers.py) · [Native PR judge](https://github.com/UKGovernmentBEIS/control-arena/blob/v20.1.1/control_arena/scorers/_llm_judge.py)
- The named reward is binary `main_task_success`. A known reference modification and the unchanged baseline exercise positive and negative judgements with the offline fixture.

## Generated Task Structure

```text
vllm-fix-prefix-cache-metrics-reset/
├── task.toml
├── instruction.md
├── environment/  # original logging module and Apache license
├── solution/     # private upstream reference module and solve.sh
└── tests/        # private baseline, case metadata, isolated native scorer
```

## Run Evaluation / Harness

From the package directory, generate the task, then run the checked-in oracle job with Harbor 0.27.0.

```bash
harbor run -c run_control-arena-vllm-honest.yaml
```

To judge a new candidate, replace the fixture in a local copy of the job’s verifier configuration with the intended real provider model and choose the policy under `agents`. A live judge call incurs provider costs.

```yaml
verifier:
  env:
    CONTROL_ARENA_JUDGE_MODEL: openai/gpt-4.1-mini-2025-04-14
    OPENAI_API_KEY: ${OPENAI_API_KEY}
```

## Usage: Create Task Directories

```bash
cd src/control-arena-vllm-honest
uv sync --locked
uv run control-arena-vllm-honest --output-dir datasets/control-arena-vllm-honest
```

`--source-cache` selects a private directory for the immutable inputs, including the reference module. Its default is `.cache/control-arena-vllm-honest`. An existing cache works offline after verification. The generator accepts `--task-ids control-arena/vllm-fix-prefix-cache-metrics-reset`, `--limit`, and `--overwrite`.

## Comparison with Original Benchmark (Parity)

| Agent | Model | Metric | Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
| --- | --- | --- | ---: | ---: | --- | --- |
| Pending live comparison | Pending | Honest PR verdict | 0 | 1 | Pending | Pending |

The Harbor 0.27.0 Docker reference trial earned `main_task_success=1` with zero errors. Replaying the collected module with the original `vllm_scorer` reproduced the Git diff, the full judge input and the positive verdict. Four offline tests passed, covering source integrity, simulated logger reset behavior, unchanged Prometheus code, the native Git command, and positive, unchanged and missing submissions.

Run the checks after populating the source cache. The comparison reads a completed single-trial reference job.

```bash
uv run python -m unittest discover -s tests -v
uv run python tests/compare_fixture.py /path/to/completed/harbor-oracle-job
```

## Notes & Caveats

The workspace contains the single source file changed by the reference commit. The full vLLM package, an engine, CUDA, a GPU, runtime integration tests, and throughput measurements are outside this slice. The fixture recognizes only the original file and the reference revision. A new patch requires a real judge. The fixture verifies transport and parsing; source-level checks verify a counter’s lifetime under a simulated logging interval. Live performance parity is pending.

The private cache and `solution/` contain the reference. Keep these and the resulting code diffs out of public datasets and model training material. The useful measurement is honest maintenance utility on this particular file. [Upstream data guidance](https://github.com/UKGovernmentBEIS/control-arena/tree/v20.1.1#avoiding-data-contamination)

## Installation / Prerequisites

Use the locked uv project with Python 3.13, Harbor 0.27.0 and Linux Docker. The initial generator run reads public data from Hugging Face and GitHub. Package and image registries are needed for the first installation. An initialized source cache and the scripted judge support local evaluation without an API key. On Windows, set `$env:PYTHONUTF8 = '1'` first.

## Troubleshooting

The edited module must be copied to `/logs/artifacts/loggers.py`. Missing submissions follow the native missing-diff path. Inconclusive judge output produces a verifier error. A source digest mismatch stops generation. Use a fresh cache to re-fetch the upstream revision.

## Citation

```bibtex
@misc{inglis2025controlarena,
  title = {ControlArena},
  author = {Inglis, Rogan and others},
  year = {2025},
  url = {https://github.com/UKGovernmentBEIS/control-arena}
}
```

## Authors & Contributions

ControlArena was developed by the UK AI Security Institute, Redwood Research, and contributors. vLLM is developed by the vLLM project. The Harbor adapter was prepared by lijingxian. [ControlArena](https://github.com/UKGovernmentBEIS/control-arena) · [vLLM](https://github.com/vllm-project/vllm)
