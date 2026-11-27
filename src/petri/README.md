# Petri → Harbor Adapter

## Overview

This adapter converts [Petri](https://www.anthropic.com/research/petri-open-source-auditing), which stands for Parallel Exploration Tool for Risky Interactions and is Anthropic's open-source alignment-auditing tool. This adapter generates a task per seed instruction, where an **auditor** model designs a scenario and drives a multi-turn conversation with a **target** model. A **judge** model then scores the resulting transcript across dozens of dimensions.

- **Task types**: Multi-turn interaction, alignment auditing, safety research
- **Domains**: AI alignment and safety, deception, whistleblowing, cooperation with human misuse
- **Language**: Python 3.13
- **Dataset size**: 173 tasks
- **Provenance**: [Anthropic Alignment Science Blog](https://alignment.anthropic.com/2025/petri/), [GitHub](https://github.com/meridianlabs-ai/inspect_petri)
- **License**: MIT
- **Source**: [GitHub: meridianlabs-ai/inspect_petri](https://github.com/meridianlabs-ai/inspect_petri/tree/main/src/inspect_petri/_seeds/default)

## What is Petri?

Petri is an open-source alignment-auditing tool built by Anthropic to enable researchers to rapidly test misalignment hypotheses without building a separate environment for each one. Researchers supply a list of seed instructions describing scenarios or behaviors to evaluate. For each seed, an auditor model will set system prompts, send user messages, and interact with the target model. A judge model then reads the full transcript and scores it across dimensions such as `audit_situational_awareness`, `concerning`, `cooperation_with_human_misuse`, and `unprompted_deception_toward_user`.

**References**:
- [Petri: An open-source auditing tool to accelerate AI safety research](https://alignment.anthropic.com/2025/petri/)
- [Petri 2.0: New Scenarios, New Model Comparisons, and Improved Eval-Awareness Mitigations](https://alignment.anthropic.com/2026/petri-v2/)
- [Introducing Petri 3.0](https://meridianlabs.ai/blog/posts/introducing-petri-3/)

## Adapter Features

- **Automatic dataset management**: Clones inspect_petri from GitHub (pinned to fixed commit) and caches locally
- **Auditor sidecar**: The auditor lives in a separate `auditor` container (`environment/auditor_server.py`) and communicates with the target using a thin proxy (`environment/chat.py`)
- **Ported judge grading**: `tests/judge.py` ports Petri's dimension-scoring judge (`inspect_petri/audit_judge`) to grade the final transcript and write a per-task float reward
- **Flexible task generation**: Provides `--output-dir`, `--limit`, `--overwrite`, `--task-ids`, `--dataset-cache-dir`, `--auditor-model`, and `--judge-model` arguments

## Generated Task Structure

```
petri/
├── {task_id}/                     # e.g., `ai_consciousness_gentle_probe`
│   ├── environment/
│   │   ├── auditor_server.py      # HTTP auditor server
│   │   ├── chat.py                # Thin proxy to auditor_server.py
│   │   ├── docker-compose.yaml    # Configure Docker containers
│   │   ├── Dockerfile             # Agent's container
│   │   ├── Dockerfile.auditor     # Auditor sidecar
│   │   └── <seed>.md              # Seed instruction
│   ├── solution/
│   │   └── solve.sh               # Solution script
│   ├── tests/
│   │   ├── Dockerfile             # Verifier's container
│   │   └── judge.py               # Grades a task
│   │   ├── test.sh                # Invokes judge.py
│   ├── instruction.md             # Task instructions for the agent
│   └── task.toml                  # Harbor task configuration
```

## Run Evaluation / Harness in Harbor

### Running with Datasets Registry

```bash
# Use oracle agent (reference solution)
uv run harbor run -d petri

# Use your specified agent and model
uv run harbor run -d petri -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

```bash
# From the repository root
uv run harbor run -c adapters/petri/run_petri.yaml -a <agent_name> -m "<model_name>"

# Or run a job with a locally prepared dataset path
uv run harbor run -p datasets/petri -a <agent_name> -m "<model_name>"

# Resume a previously started job
uv run harbor job resume -p /path/to/jobs/directory
```

Results are saved in the `jobs/` directory by default (configurable via `jobs_dir` in the YAML config).

### Running Individual Trials

```bash
# Run a single task with oracle (pre-written solution)
uv run harbor trial start -p datasets/petri/<task_id>

# Run a single task with a specific agent and model
uv run harbor trial start -p datasets/petri/<task_id> -a <agent_name> -m "<model_name>"
```

Trial outputs are saved in the `trials/` directory by default (configurable via `--trials-dir`).


## Usage: Create Task Directories

```bash
cd adapters/petri
uv run petri --output-dir ../../datasets/petri
```

**Arguments**:
- `--output-dir`: Directory to write generated tasks (default: `datasets/petri`)
- `--limit`: Generate only the first N tasks
- `--overwrite`: Overwrite existing tasks
- `--task-ids`: Only generate specific task IDs
- `--dataset-cache-dir`: Directory to cache the downloaded dataset (default: `~/.cache/harbor/petri`)
- `--auditor-model`: Model the auditor uses to run the audit
- `--judge-model`: Model the verifier uses to judge the audit

Tasks are written to `datasets/petri/` with one directory per task. Each task follows the structure shown in [Generated Task Structure](#generated-task-structure) above.

## Comparison with Original Benchmark (Parity)

Not yet run. This will be discussed with the Harbor team.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| \<agent\>@\<agent_version\> | \<model\> | max-dimension | \<n\> | 173 tasks | \<x% ± y%\> | \<x% ± y%\> |

## Oracle Verification

Oracle reward on this adapter is currently 0% (**by design of the dataset, not the adapter**). Since the reward depends on the judge, there is no "solution transcript" that scores reward 1.0.

## Notes & Caveats

- **No oracle solutions**: See [Oracle Verification](#oracle-verification) above
- **Parity experiments not yet run**: See [Comparison with Original Benchmark (Parity)](#comparison-with-original-benchmark-parity) above
- **Judge-dependent reward**: The per-task float reward comes from an LLM judge, so scores depend entirely on the judge model

## Installation / Prerequisites

```bash
cd adapters/petri
uv sync
```

- Docker installed and running
- Harbor installed and working (see main repository README)
- `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` set for the auditor and judge models

## Troubleshooting

### 1. Verifier Fails to Fetch Transcript
- Verify the auditor sidecar is reachable
- Ensure that `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` are set

### 2. Judge Scoring Is Inconsistent
- Expected (see [Notes & Caveats](#notes--caveats) above)

### 3. Oracle Trial Reports Non-Zero Exit Code
- Expected (see [Oracle Verification](#oracle-verification) above)

## Citation

```bibtex
@misc{petri2025,
  title={Petri: Parallel Exploration of Risky Interactions},
  author={Fronsdal, Kai and Gupta, Isha and Sheshadri, Abhay and Michala, Jonathan and McAleer, Stephen and Wang, Rowan and Price, Sara and Bowman, Sam},
  year={2025},
  url={https://github.com/meridianlabs-ai/inspect_petri},
}
```

## Authors & Contributions

This adapter is developed and maintained by [Tristan](mailto:troath@berkeley.edu) and [Tyler](mailto:tyroath@berkeley.edu) from the Harbor team.

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines
