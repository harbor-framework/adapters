# ControlArena APPS honest-mode adapter

## Overview

See the [suite coverage](../../docs/control-arena.md) for the other ControlArena settings.

Generate three reviewed Python programming exercises from the APPS setting in ControlArena 20.1.1. The original validated split contains 3,420 main tasks. This adapter covers accordion delimiter parsing (ID 0), maximum digit sum (ID 1), and a stadium wave (ID 17). It measures honest main-task success. [ControlArena APPS](https://control-arena.aisi.org.uk/settings/apps.html)

## What is ControlArena?

ControlArena runs AI control evaluations in Inspect. Its APPS setting asks an agent to submit Python 3.4 code that reads standard input and prints standard output. The original setting also supports experiments with control protocols. [ControlArena introduction](https://control-arena.aisi.org.uk/intro-to-control.html)

## Adapter Features

The generator filters by the three reviewed IDs and reads only the question, eligibility flags, standard inputs, expected outputs, and validated honest solutions. It preserves the native setting description and question, and adds instructions for submitting the native JSON field `code` through Harbor's shell. Data is fetched at generation time from the pinned MIT-labelled ControlArena distribution. Keep generated tasks private to evaluation operators because they contain solutions and hidden tests. [Pinned source and license](https://huggingface.co/datasets/RoganInglis/apps-control-arena/tree/29db28f76042952d56add8671f798280b200744d)

## Generated Task Structure

| Path | Purpose |
| --- | --- |
| `instruction.md`, `task.toml` | Original honest prompt, submission instructions, and Harbor configuration |
| `environment/` | Agent's Python 3.4 image and `submit` command |
| `solution/` | Trusted oracle that submits a validated upstream answer |
| `tests/` | Private cases, native output comparator, and separate verifier |

## Run Evaluation / Harness

From this directory, after generating the tasks, run the Harbor oracle job.

```sh
uv run --locked harbor run -c run_control-arena-apps-honest.yaml
```

Use `harbor run -p datasets/control-arena-apps-honest -a <agent>` to select another Harbor agent. Submit a JSON object containing a string-valued `code` through the `submit` shell command. The verifier records binary `main_task_success` in `reward.json` and the same scalar in `reward.txt`.

## Usage: Create Task Directories

```sh
uv run --locked control-arena-apps-honest --output-dir datasets/control-arena-apps-honest
uv run --locked control-arena-apps-honest --task-ids control-arena/apps-honest-0017 --output-dir datasets/one
```

`--limit N` takes the first N selected IDs in source order. The generator reuses existing directories unless `--overwrite` is supplied.

## Comparison with Original Benchmark (Parity)

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
| --- | --- | --- | ---: | ---: | --- | --- |
| Honest | Pending | Main-task success | 0 live | 3 | Pending | Pending |

Each reference program passed all ten tests in both Harbor Docker and ControlArena's native Inspect Docker scorer. Both harnesses also rejected the same constant wrong program on all three tasks. Harbor recorded three rewards of one and three rewards of zero, with zero exceptions in either job. These are deterministic scorer checks. Live-agent experiment parity is pending. The native replay reads the same private test packet and runs the installed upstream scorer against the original APPS Compose sandbox.

```sh
uv run --locked python tests/native_reference.py datasets/control-arena-apps-honest --log-dir native-logs/oracle
uv run --locked python tests/native_reference.py datasets/control-arena-apps-honest --candidate wrong --log-dir native-logs/wrong
uv run --locked python -m unittest discover -s tests
```

## Notes & Caveats

The verifier runs up to ten paired cases, with ten seconds per case, in the original Python 3.4 userspace. It uses both comparison functions directly from the installed upstream release, including its numeric tolerance, line structure, exit status, and stderr timeout handling. Each submission runs as an unprivileged user inside a separate filesystem root. The trusted controller uses Python 3.13 and limits output files to 10 MiB per stream. The adapter exports the main score only. [Native scorer](https://github.com/UKGovernmentBEIS/control-arena/blob/v20.1.1/control_arena/settings/apps/task/scorers.py)

## Installation / Prerequisites

Install uv, Python 3.13, and Docker with Linux containers. Run `uv sync --locked` in this directory. Generation needs public access to the pinned Hugging Face Parquet source with HTTP byte-range support. Docker must be able to pull `python:3.4` and `python:3.13-slim-bookworm`. Evaluation sandboxes use disabled networking. The oracle and scoring replay require no model credentials.

## Troubleshooting

If generation fails with an HTTP range or Parquet error, check access to the pinned dataset through the proxy, and re-run generation. A verifier infrastructure failure leaves its reward absent. Check `verifier/test-stdout.txt` within the trial, including whether the Linux runtime supports chroot and creating the standard character devices inside the verifier.

## Citation

```bibtex
@article{hendrycks2021apps,
  title = {Measuring Coding Challenge Competence With APPS},
  author = {Hendrycks, Dan and others},
  journal = {NeurIPS Datasets and Benchmarks},
  year = {2021},
  url = {https://arxiv.org/abs/2105.09938}
}
```

Cite the original APPS benchmark and ControlArena when using the tasks. [Hendrycks et al., Measuring Coding Challenge Competence With APPS](https://arxiv.org/abs/2105.09938) · [ControlArena citation](https://github.com/UKGovernmentBEIS/control-arena/tree/v20.1.1#citation)

## Authors & Contributions

Dan Hendrycks and coauthors created APPS. ControlArena contributors prepared and validated the dataset used here. The Harbor adapter was prepared by lijingxian.
