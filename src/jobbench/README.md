# JobBench → Harbor Adapter

> **Status: work in progress.** Task generation is complete. Oracle deliverables and parity experiments are not done yet, and the sections that depend on them are marked as pending.

## Overview

[JobBench](https://job-bench.github.io/) evaluates agentic CLI tools on the tedious, multi-source work that professionals most want to hand off: reconciling contradictory data, cross-referencing records, tracing citations, and producing a finished deliverable such as a workbook, memo or report.

- **Size:** 128 tasks across 35 white-collar occupations, in two splits: `main` (65 tasks, the leaderboard split) and `easy` (63 simplified tasks).
- **This adapter:** generates all 128 tasks. Nothing is excluded. Task IDs are `<split>--<occupation>--task<N>`, for example `main--lawyers--task1`.
- **Sources:** tasks come from the Hugging Face dataset [`JobBench/job-bench`](https://huggingface.co/datasets/JobBench/job-bench) (MIT), pinned to revision `d43a66575635da0d3f6cb9a20976dc1a60f3ffc9`. The instruction text, Docker images and judge come from [`Job-Bench/job-bench-eval`](https://github.com/Job-Bench/job-bench-eval) (Apache-2.0), pinned to commit `660b33a86ed032559df0b2fdc1ad38cf7ceb83f3`.
- **Grading:** an LLM judge scores the agent's deliverables against a weighted rubric. There are no unit tests and no reference solutions upstream.
- **Modifications:** none to the prompt, environment or judge. The only additions are `solution/solve.sh` (upstream has no oracle), a comment in `tests/test.sh`, and the paper's author list in `task.toml`.
- **Task count:** the paper reports 130 tasks. The pinned dataset revision contains 128 (65 main, 63 easy), and all 128 are adapted.

## What is JobBench?

JobBench asks what workers actually want automated, not only what can be automated. Its tasks are drawn from Workbank, a survey of worker preferences across 35 occupations. Each task gives the agent a working folder with a `TASK_INSTRUCTIONS.txt` and reference files (spreadsheets, PDFs, databases, documents), and asks for final deliverables in an output folder. Some tasks need live web search.

After the agent finishes, an LLM judge checks the deliverables against the task's `RUBRICS.json`. A rubric block earns its full weight only if all of its criteria pass, otherwise it earns zero. The task score is `round(earned weight / total weight, 4)`, and the benchmark score is the mean of the task scores. The upstream default judge is xAI `grok-4.3`.

Links: [paper](https://arxiv.org/abs/2605.26329), [website and leaderboard](https://job-bench.github.io/), [evaluation code](https://github.com/Job-Bench/job-bench-eval), [dataset](https://huggingface.co/datasets/JobBench/job-bench).

## Adapter Features

- **Pinned sources.** The dataset is downloaded from Hugging Face at a fixed revision. Only `task_folder/` and `RUBRICS.json` are fetched for each task; the upstream task card is never given to the agent.
- **Unmodified upstream harness.** The instruction text, the agent image, the verifier image and the rubric judge are copied from the upstream evaluation repository without changes. JobBench ships its own Harbor converter, and for all 128 tasks the files this adapter shares with that converter's output are byte-identical, except for an added comment in `tests/test.sh` and the `authors` field in `task.toml`, which lists the paper's authors.
- **Separate verifier image.** Tasks use `environment_mode = "separate"`, so the judge runs in its own container and the judge API key is never visible to the agent. The agent's `/workspace/output` is passed to the verifier as an artifact.
- **Same reward as upstream.** The verifier writes the weighted rubric score (0 to 1) to `/logs/verifier/reward.json`. If the output folder is empty the reward is 0 and the judge is not called. If the judge itself fails, no reward is written, so an infrastructure error is not scored as a zero.
- **Configurable judge.** `JUDGE_MODEL`, `JUDGE_API_BASE` and `JUDGE_API_KEY` are read from the host environment and default to xAI `grok-4.3`.
- **Split selection.** `--split main|easy|all` selects which tasks to generate.
- **Rubric validation at generation time.** A task with a malformed rubric fails generation instead of failing later in the verifier.

## Generated Task Structure

```
jobbench/
└── <split>--<occupation>--task<N>/
    ├── task.toml                 # Task configuration (timeouts, resources, judge env)
    ├── instruction.md            # Upstream agent instruction, unchanged
    ├── environment/
    │   ├── Dockerfile            # Upstream agent image
    │   ├── requirements.txt
    │   └── task_folder/          # Task inputs, including TASK_INSTRUCTIONS.txt
    ├── solution/
    │   ├── solve.sh              # Copies deliverables/ to /workspace/output
    │   └── deliverables/         # Reference deliverable (only when one exists)
    └── tests/
        ├── test.sh               # Runs verify.py
        ├── verify.py             # Upstream verifier entry point
        ├── judge.py              # Upstream rubric judge
        ├── jobbench_eval/        # Upstream judge library
        ├── Dockerfile            # Upstream verifier image
        ├── calc-runtime/
        ├── requirements.txt
        └── RUBRICS.json          # This task's weighted rubric
```

The adapter is a standalone `uv` package under `src/jobbench/`, with the code in `src/jobbench/src/jobbench/` and the task template in `src/jobbench/src/jobbench/task-template/`.

## Run Evaluation / Harness

Run these commands from the root of the adapters repository, with the Harbor CLI installed. Every run that scores an agent needs a judge key:

```bash
export JUDGE_API_KEY="your_xai_key"
# Optional overrides (defaults shown)
export JUDGE_MODEL="grok-4.3"
export JUDGE_API_BASE="https://api.x.ai/v1"
```

### Running with Datasets Registry

Once the dataset is published:

```bash
# Oracle agent (reference deliverables)
harbor run -d jobbench/jobbench

# A specific agent and model
harbor run -d jobbench/jobbench -a <agent_name> -m "<model_name>"
```

The dataset is not registered yet. Until the `harbor-datasets` PR is merged, use the local methods below.

### Using Job Configurations

```bash
# Run the reference configuration on the locally generated dataset
harbor run -c src/jobbench/run_jobbench.yaml -a <agent_name> -m "<model_name>"

# Or point directly at the generated tasks
harbor run -p datasets/jobbench -a <agent_name> -m "<model_name>"

# Resume a previously started job
harbor job resume -p /path/to/jobs/directory
```

Results are saved in `jobs/` by default.

### Running Individual Trial

```bash
# Oracle on one task
harbor trial start -p datasets/jobbench/<task_id>

# A specific agent and model on one task
harbor trial start -p datasets/jobbench/<task_id> -a <agent_name> -m "<model_name>"
```

Trial outputs are saved in `trials/` by default.

## Usage: Create Task Directories

```bash
cd src/jobbench
uv run jobbench --output-dir ../../datasets/jobbench
```

Available flags:

- `--output-dir`: directory to write generated tasks (defaults to `datasets/jobbench` at the repository root)
- `--limit`: generate only the first N tasks
- `--overwrite`: replace task directories that already exist
- `--task-ids`: generate only these task IDs, for example `main--lawyers--task1`
- `--split`: `main` (65 tasks), `easy` (63 tasks) or `all` (default)
- `--revision`: Hugging Face dataset revision (defaults to the pinned commit)
- `--source-dir`: use a local copy of the dataset instead of downloading

The first run downloads about 620 MB from Hugging Face. The generated dataset is about 290 MB.

## Comparison with Original Benchmark (Parity)

Parity experiments have not been run yet. This table will be filled in from `parity_experiment.json` once they are complete.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| TBD | TBD | Mean weighted rubric score | TBD | TBD | TBD | TBD |

Reproduction steps, to be confirmed against the final parity setup.

Original benchmark (repository `Job-Bench/job-bench-eval` at commit `660b33a86ed032559df0b2fdc1ad38cf7ceb83f3`):

```bash
git clone https://github.com/Job-Bench/job-bench-eval.git
cd job-bench-eval
git checkout 660b33a86ed032559df0b2fdc1ad38cf7ceb83f3
./setup.sh

# Generate deliverables with the chosen agent, then judge them
BENCHMARK_MODELS="<model>" ./eval/run_benchmark_claude_code_cli.sh
JUDGE_API_KEY="your_xai_key" uv run ./eval/run_judge.sh
```

Harbor adapter:

```bash
cd src/jobbench && uv run jobbench --split main --output-dir ../../datasets/jobbench && cd ../..
export JUDGE_API_KEY="your_xai_key"
harbor run -p datasets/jobbench -a <agent_name> -m "<model_name>"
```

Scores on both sides are the mean of the per-task weighted rubric scores, as described in [What is JobBench?](#what-is-jobbench). Both sides must use the same judge model.

## Notes & Caveats

- **No upstream oracle.** JobBench ships rubrics, not reference solutions. `solution/solve.sh` submits a reference deliverable when one exists for the task and exits non-zero otherwise, so that a missing oracle is never mistaken for an empty answer. No reference deliverables are included yet, so the oracle agent currently fails on every task. The plan is to build them from the strongest agent outputs and confirm they score the same under the original judge and under Harbor.
- **LLM judge.** Scores depend on the judge model and are not fully deterministic. Use the same judge on both sides of any comparison. A full judging pass over all tasks costs roughly $20 with the default judge, per the upstream documentation.
- **Rubrics are public.** Every task's `RUBRICS.json` is published in the public Hugging Face dataset, and tasks run with internet access, so an agent could in principle look up the rubric it will be graded on. The original benchmark has the same exposure. The rubric is never placed in the agent's container.
- **Network access.** Tasks run with public network access, as upstream, because some require online research. Results can vary with what the agent's search tools return.
- **Timeouts.** The agent timeout is 7200 seconds and the verifier timeout is 3600 seconds, matching the upstream Harbor converter. The upstream Claude Code and Codex CLI runners default to 3600 seconds per task (`TIMEOUT_PER_TASK`), so that value has to be raised to 7200 on the original side for a like-for-like comparison.
- **Environment difference on the original side.** The upstream CLI runners run the agent on the host machine, while Harbor runs it in the upstream Docker image. This is a known difference between the two sides that parity will need to account for.
- **Task schema.** Tasks use `schema_version = "1.4"` and write `reward.json`, matching the upstream converter.
- **Verified so far.** Harbor 0.22.0 loads all 128 task configurations. One task has been run end to end in Docker: both images build and the verifier returns a valid reward. That run had an empty output, so the LLM judge has not graded a real deliverable through this adapter yet.

## Installation / Prerequisites

- Docker installed and running. The agent image is large (LibreOffice, Tesseract, GDAL and other document tooling). Both images built with 8 GB of memory assigned to Docker; larger tasks may need more.
- The Harbor CLI installed and working.
- `uv`, to run the adapter:
  ```bash
  cd src/jobbench
  uv sync
  ```
- A judge API key in `JUDGE_API_KEY` (xAI by default), plus the API key for whichever agent you run.
- About 1 GB of free disk space for the dataset download and the generated tasks, in addition to the Docker images.

## Troubleshooting

- **The oracle fails with "No reference deliverable is available for this JobBench task."** This is expected until reference deliverables are added. See Notes & Caveats.
- **A trial finishes with no reward.** The judge failed (missing or invalid `JUDGE_API_KEY`, wrong `JUDGE_API_BASE`, or a model the endpoint does not serve). The verifier deliberately writes no reward in this case. Fix the judge settings and rerun.
- **Reward is 0 and the judge was not called.** The agent wrote nothing to `/workspace/output`.
- **The image build is slow or times out.** The first build installs a large toolchain. The build timeout is 1800 seconds; later builds reuse the Docker cache.
- **Generation says tasks were skipped.** The task directories already exist. Pass `--overwrite` to replace them.

## Citation

```bibtex
@article{li2026jobbench,
  title={JobBench: Aligning Agent Work With Human Will},
  author={Li, Yuetai and Feng, Yichen and Xu, Zhangchen and Ma, Zixian and Zheng, Kaiyuan and Jiang, Fengqing and Sun, Xinghua and Shao, Rulin and Chen, Zichen and Huang, Yue and Han, Xinyang and Lee, Brian and Xu, Kayla and Zeng, Shenglai and Hua, Hang and Zhang, Xiangliang and Alomair, Basel and Krishna, Ranjay and Zettlemoyer, Luke and Koh, Pang Wei and Ramasubramanian, Bhaskar and Niu, Luyao and Yue, Xiang and Poovendran, Radha},
  journal={arXiv preprint arXiv:2605.26329},
  year={2026},
  url={https://arxiv.org/abs/2605.26329}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Yogya Mehrotra](mailto:ymehrotra@ucsd.edu).

**Issues and Contributions:**
- Submit Issues and Pull Requests to the [adapters repository](https://github.com/harbor-framework/adapters)
- Follow the project's coding style and commit guidelines
