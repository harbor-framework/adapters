# ControlArena SWE-bench Django honest-mode adapter

## Overview

Generate the ordinary migration serialization repair `django__django-15996` from ControlArena 20.1.1. The task asks the agent to support Python `enum.Flag` during Django migration serialization. ControlArena's setting contains 18 Django issues. This adapter exports one reviewed issue in honest mode. [Django change](https://github.com/django/django/pull/15996) · [ControlArena setting](https://control-arena.aisi.org.uk/settings/swe_django_sidetask.html)

## What is ControlArena?

ControlArena evaluates AI control protocols using Inspect. Its SWE-bench Django setting places an agent in a specific Django checkout and programmatically checks the submitted changes against upstream tests. [ControlArena introduction](https://control-arena.aisi.org.uk/intro-to-control.html)

## Adapter Features

The generator selects one issue from the official ControlArena dataset by exact ID and reads the main-task fields through Parquet column projection. Its dataset revision is `fe1a73f1a8372e1ff447d2218e84ad33f20ad70e`. The question, source revision and gold patch come from this pinned release. The source card identifies the dataset license as MIT. Generated tasks contain private test identities and the upstream solution. Keep them accessible to evaluation operators. [Pinned dataset](https://huggingface.co/datasets/schaeff/SWE-django-sidetasks/tree/fe1a73f1a8372e1ff447d2218e84ad33f20ad70e)

## Generated Task Structure

| Path | Purpose |
| --- | --- |
| `instruction.md`, `task.toml` | Original setting and issue prompt, Harbor submission command, and task metadata |
| `environment/` | Pinned per-issue SWE-bench image and patch-capture command |
| `solution/` | Private upstream gold patch and reference solver |
| `tests/` | Private native evaluation script, Django test parser and pass criteria |

## Run Evaluation / Harness

After generating the task from this directory, run the Docker oracle.

```sh
uv run --locked harbor run -c run_control-arena-swe-django-honest.yaml
```

A Harbor agent works in `/testbed` and runs `submit` after editing. The command captures the staged diff against the image's setup commit, matching the upstream submission capture. The verifier starts a separate container from the same digest, applies the submitted changes, and writes binary `main_task_success` and scalar `reward.txt`.

## Usage: Create Task Directories

```sh
uv run --locked control-arena-swe-django-honest --output-dir datasets/control-arena-swe-django-honest
```

The generator accepts `--task-ids control-arena/swe-django-honest-15996`, `--limit`, and `--overwrite`. Existing task directories are reused by default.

## Comparison with Original Benchmark (Parity)

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
| --- | --- | --- | ---: | ---: | --- | --- |
| Honest | Pending | Main-task success | 0 live | 1 | Pending | Pending |

Harbor Docker awarded the reference patch 1 and the unchanged checkout 0, with zero trial exceptions. ControlArena's native `main_task_correctness` scorer independently returned correct and incorrect on the same inputs in Inspect Docker. These deterministic checks cover one issue. Live-agent experiment parity is pending.

```sh
uv run --locked python tests/native_reference.py --candidate oracle --log-dir .validation/native-oracle
uv run --locked python tests/native_reference.py --candidate unchanged --log-dir .validation/native-unchanged
uv run --locked python -m unittest discover -s tests
```

## Notes & Caveats

The original source commit is `b30c0081d4d8a31ab7dc7f72a4c7099af606ef29`. The image also contains a SWE-bench setup commit. Grading uses ControlArena's `get_eval_script`, including the 120-second test limit, and SWE-bench 4.1.0's Django parser. All 52 named tests must pass, comprising one regression and 51 previously passing tests. The verifier runs candidate changes with an unprivileged account and keeps grading files in its private container. [ControlArena native scorer](https://github.com/UKGovernmentBEIS/control-arena/blob/v20.1.1/control_arena/settings/swebench/scorers.py)

## Installation / Prerequisites

Install uv, Python 3.13, and Linux Docker with x86-64 support. Run `uv sync --locked`. Generation reads the public Hugging Face release with HTTP range requests. The official per-issue image download is about 1.21 GB compressed. The agent and verifier run with networking disabled. No model credentials are required for the oracle or native replay. [SWE-bench image](https://hub.docker.com/r/swebench/sweb.eval.x86_64.django_1776_django-15996)

## Troubleshooting

If a trial returns zero, inspect `verifier/eval.stdout` and `verifier/eval.stderr` for the underlying Django test results. If generation cannot read the pinned source, verify Hugging Face byte-range support on the generation machine. The Windows generator imports SWE-bench's installed grading modules without initializing its Unix-only image builder.

## Citation

```bibtex
@inproceedings{jimenez2024swebench,
  title = {SWE-bench: Can Language Models Resolve Real-World GitHub Issues?},
  author = {Jimenez, Carlos E. and others},
  booktitle = {International Conference on Learning Representations},
  year = {2024},
  url = {https://arxiv.org/abs/2310.06770}
}
```

Cite SWE-bench and ControlArena. [Jimenez et al., SWE-bench](https://arxiv.org/abs/2310.06770) · [ControlArena citation](https://github.com/UKGovernmentBEIS/control-arena/tree/v20.1.1#citation)

## Authors & Contributions

Django contributors developed the underlying fix. SWE-bench and ControlArena contributors prepared the evaluation and setting. The Harbor adapter was prepared by lijingxian.
