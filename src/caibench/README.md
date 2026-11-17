# CAIBench → Harbor Adapter

## Overview

This adapter converts [CAIBench](https://aliasrobotics.github.io/cai/cai_benchmark/), Alias Robotics' benchmark for cybersecurity AI agents, into Harbor task format. Of CAIBench's 5 categories, this adapter covers the 2 that are public: **Security Knowledge Benchmarks** (CyberMetric, SecEval, CTI-Bench) and **Privacy Benchmarks** (CyberPII-Bench). The other 3 categories (Jeopardy CTFs, Attack-Defense CTFs, Cyber Ranges) are gated behind a CAI PRO subscription and are out of scope (see [Notes & Caveats](#notes--caveats) below).

- **Task types**: Multiple-choice/short-answer security knowledge questions and PII anonymization
- **Domains**: Cybersecurity knowledge, MITRE ATT&CK, CWE/CVSS vulnerability scoring, PII redaction
- **Language**: Python 3.12
- **Dataset size**: 16,820 tasks (see [Task Breakdown](#task-breakdown) below)
- **Provenance**: [CAI docs](https://aliasrobotics.github.io/cai/) (see [Citation](#citation) below)
- **License**: MIT
- **Source**: [aliasrobotics/cai](https://github.com/aliasrobotics/cai), [cybermetric/CyberMetric](https://github.com/cybermetric/CyberMetric), [XuanwuAI/SecEval](https://github.com/XuanwuAI/SecEval), [maveryn/cti-bench](https://github.com/maveryn/cti-bench)

## Task Breakdown

| Sub-Benchmark | Tasks | Task ID prefix |
|---------------|-------|----------------|
| CyberMetric | 10,000 | `cybermetric__` |
| SecEval | 2,182 | `seceval__` |
| CTI-Bench MCQ | 2,500 | `cti_bench_mcq__` |
| CTI-Bench ATE | 60 | `cti_bench_ate__` |
| CTI-Bench RCM | 1,000 | `cti_bench_rcm__` |
| CTI-Bench VSP | 1,000 | `cti_bench_vsp__` |
| CyberPII-Bench | 78 | `cyberpii_bench__` |

## What is CAIBench?

CAIBench is Alias Robotics' benchmark for evaluating agent capabilities in offensive, defensive, and analytical cybersecurity. The benchmark spans 5 categories: Jeopardy CTFs, Attack-Defense CTFs, Cyber Ranges, Security Knowledge Benchmarks, and Privacy Benchmarks. Scoring in the original benchmark consists of accuracy, F1 score, and mean absolute deviation (MAD). This adapter uses the same metrics, but edited so it writes a per-task float reward instead of a dataset-wide aggregate.

**References**:
- Paper: [Cybersecurity AI Benchmark (CAIBench): A Meta-Benchmark for Evaluating Cybersecurity AI Agents](https://arxiv.org/abs/2510.24317)
- Framework: [aliasrobotics/cai](https://github.com/aliasrobotics/cai), [CAI docs](https://aliasrobotics.github.io/cai/)

## Adapter Features

- **Automatic dataset management**: Clones CyberMetric/SecEval/CTI-Bench from GitHub (pinned to fixed commits), downloads CyberPII-Bench's CSV, and caches locally
- **Ported grading**: `tests/grade.py` ports code from CAI's `eval.py` and `annotation_metrics.py`
- **Multiple sub-benchmarks**: Fills out `task-template` with benchmark-specific prompts, solutions, and grading
- **Flexible task generation**: Provides `--limit`, `--overwrite`, `--task-ids`, `--sub-benchmarks`, `--dataset-cache-dir`, and `--cybermetric-size` arguments

## Generated Task Structure

```
caibench/
├── {task_id}/               # e.g. "cti_bench_vsp__00412
│   ├── task.toml            # Harbor task configuration
│   ├── instruction.md       # Task instructions for the agent
│   ├── environment/
│   │   └── Dockerfile       # Agent's container
│   ├── solution/
│   │   └── solve.sh         # Echoes correct answer
│   └── tests/
│       ├── test.sh          # Invokes grade.py
│       ├── grade.py         # Grades a task
│       └── expected.json    # Expected solution
```

## Run Evaluation / Harness in Harbor

### Running with Datasets Registry

```bash
# Use oracle agent (reference solution)
uv run harbor run -d caibench

# Use your specified agent and model
uv run harbor run -d caibench -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

```bash
# From the repository root
uv run harbor run -c adapters/caibench/run_caibench.yaml -a <agent_name> -m "<model_name>"

# Or run a job with a locally prepared dataset path
uv run harbor run -p datasets/caibench -a <agent_name> -m "<model_name>"

# Resume a previously started job
uv run harbor job resume -p /path/to/jobs/directory
```

Results are saved in the `jobs/` directory by default (configurable via `jobs_dir` in the YAML config).

### Running Individual Trials

```bash
# Run a single task with oracle (pre-written solution)
uv run harbor trial start -p datasets/caibench/<task_id>

# Run a single task with a specific agent and model
uv run harbor trial start -p datasets/caibench/<task_id> -a <agent_name> -m "<model_name>"
```

Trial outputs are saved in the `trials/` directory by default (configurable via `--trials-dir`).

## Usage: Create Task Directories

```bash
cd adapters/caibench
uv run caibench --output-dir ../../datasets/caibench
```

**Arguments**:
- `--output-dir`: Directory to write generated tasks (default: `datasets/caibench`)
- `--limit`: Generate only the first N tasks (counted across all selected sub-benchmarks)
- `--overwrite`: Overwrite existing tasks
- `--task-ids`: Only generate specific task IDs
- `--sub-benchmarks`: Which sub-benchmarks to generate (`cybermetric`, `seceval`, `cti_bench_mcq`, `cti_bench_ate`, `cti_bench_rcm`, `cti_bench_vsp`, `cyberpii_bench`; default: all)
- `--dataset-cache-dir`: Directory to cache the cloned/downloaded datasets (default: `~/.cache/harbor/caibench`)
- `--cybermetric-size`: Which `CyberMetric-{size}-v1.json` variant to use (`80`, `500`, `2000`, `10000`; default: `10000`)

Tasks are written to `datasets/caibench/` with one directory per task. Each task follows the structure shown in [Generated Task Structure](#generated-task-structure) above.

## Comparison with Original Benchmark (Parity)

Not yet run. This will be discussed with the Harbor team.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| \<agent\>@\<agent_version\> | \<model\> | accuracy / F1 / MAD | \<n\> | 16,820 tasks | \<x% ± y%\> | \<x% ± y%\> |

## Oracle Verification

Currently, this adapter has been run with the oracle agent at 500 tasks (reward 1.0). It will be run with all 16,820 tasks soon.

## Notes & Caveats

- **Full oracle verification not yet run**: See [Oracle Verification](#oracle-verification) above
- **Parity experiments not yet run**: See [Comparison with Original Benchmark (Parity)](#comparison-with-original-benchmark-parity) above
- **Jeopardy CTFs, Attack-Defense CTFs, and Cyber Ranges excluded**: These challenges are gated behind a `CAIBENCH_IMG_REGISTRY_TOKEN` that is granted only upon request to CAI PRO subscribers (not able to be adapted without access)
- **CyberMetric default size (10000)**: CyberMetric ships 4 different versions consisting of 80, 500, 2000, and 10000 questions (this adapter uses the 10000-question variant by default, which can be overwritten with `--cybermetric-size`)

## Installation / Prerequisites

```bash
cd adapters/caibench
uv sync
```

- Docker installed and running
- Harbor installed and working (see main repository README)
- `git` and network access to GitHub

## Troubleshooting

### 1. CyberMetric/SecEval/CTI-Bench `git clone` Fails
- The repos are cloned over `https://github.com/...`
- Check network access rather than credentials

### 2. CTI-Bench VSP Tasks Fail
- Verify the `cvss` Python package installed cleanly in `environment/Dockerfile` (`pip install cvss==3.4`)
- Confirm the agent's answer is a well-formed CVSS 3.1 vector string
- Malformed vector strings result in reward 0.0 instead of erroring

### 3. CyberPII-Bench Tasks Fail
- Check whether the agent outputted any extra text around the anonymized content

## Citation

CAIBench:
```bibtex
@misc{sanzgómez2025cybersecurityaibenchmarkcaibench,
  title={Cybersecurity AI Benchmark (CAIBench): A Meta-Benchmark for Evaluating Cybersecurity AI Agents},
  author={María Sanz-Gómez and Víctor Mayoral-Vilches and Francesco Balassone and Luis Javier Navarrete-Lozano and Cristóbal R. J. Veas Chavez and Maite del Mundo de Torres},
  year={2025},
  eprint={2510.24317},
  archivePrefix={arXiv},
  primaryClass={cs.CR},
  url={https://arxiv.org/abs/2510.24317},
}
```

CyberMetric:
```bibtex
@INPROCEEDINGS{10679494,
  author={Tihanyi, Norbert and Ferrag, Mohamed Amine and Jain, Ridhi and Bisztray, Tamas and Debbah, Merouane},
  booktitle={2024 IEEE International Conference on Cyber Security and Resilience (CSR)},
  title={CyberMetric: A Benchmark Dataset based on Retrieval-Augmented Generation for Evaluating LLMs in Cybersecurity Knowledge},
  year={2024},
  volume={},
  number={},
  pages={296-302},
  keywords={Accuracy;Reverse engineering;Benchmark testing;NIST Standards;Risk management;Problem-solving;Computer security},
  doi={10.1109/CSR61664.2024.10679494}}
```

SecEval:
```bibtex
@misc{li2023seceval,
  title={SecEval: A Comprehensive Benchmark for Evaluating Cybersecurity Knowledge of Foundation Models},
  author={Li, Guancheng and Li, Yifeng and Wang Guannan and Yang, Haoyu and Yu, Yang},
  publisher = {GitHub},
  howpublished= "https://github.com/XuanwuAI/SecEval",
  year={2023}
}
```

CTI-Bench:
```bibtex
@article{alam2024ctibench,
  title={Ctibench: A benchmark for evaluating llms in cyber threat intelligence},
  author={Alam, Md Tanvirul and Bhusal, Dipkamal and Nguyen, Le and Rastogi, Nidhi},
  journal={Advances in Neural Information Processing Systems},
  volume={37},
  pages={50805--50825},
  year={2024}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Tristan](mailto:troath@berkeley.edu) and [Tyler](mailto:tyroath@berkeley.edu) from the Harbor team.

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines
