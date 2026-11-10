## AgentDojo → Harbor Adapter

## Overview

This adapter converts [AgentDojo](https://github.com/ethz-spylab/agentdojo) into Harbor tasks. AgentDojo evaluates tool-using LLM agents on realistic tasks while third-party data returned by the tools (emails, files, web pages, messages) contains prompt injections.

- **Task type**: tool use through function calls, with and without prompt injection attacks
- **Suites**: `workspace`, `travel`, `banking`, `slack`
- **Benchmark version**: v1.2.2 (upstream's default), from `agentdojo==0.1.35`
- **Adapter size**: 1,046 tasks
  - `user` split: 97 user tasks without injections (workspace 40, travel 20, banking 16, slack 21)
  - `attack` split: 949 (user task, injection task) pairs under the attack (560 + 140 + 144 + 105)
- **Scoring**: deterministic upstream checks, no LLM judge and no API key needed to score
- **Original repo**: <https://github.com/ethz-spylab/agentdojo>
- **License**: MIT

## What is AgentDojo?

AgentDojo ([paper](https://arxiv.org/abs/2406.13352), NeurIPS 2024 Datasets and Benchmarks) is a dynamic environment for prompt injection attacks and defenses. Each suite has a stateful environment (an inbox, calendar and cloud drive; flights, hotels and restaurants; a bank account; a Slack workspace and the web), a set of tools, **user tasks** that the agent should complete, and **injection tasks** that an attacker wants the agent to carry out instead. An attack places text in the environment's injection vectors, which the agent only sees through tool outputs while working on a user task.

Upstream reports three numbers per model:

- **Utility**: share of user tasks completed without any attack.
- **Utility under attack**: share of (user task, injection task) pairs where the user task is still completed.
- **Targeted attack success rate (ASR)**: share of pairs where the injection task succeeded (upstream's `security` value; lower is better).

All checks are deterministic Python functions over the agent's final answer, the environment before and after the run, and the sequence of tool calls. The paper's main attack is `important_instructions`. Results are listed on the [AgentDojo results page](https://agentdojo.spylab.ai/results/).

## Adapter Features

- Generates all 97 user tasks and all 949 attacked pairs of v1.2.2 from the pinned `agentdojo==0.1.35` package; `--split`, `--suites` and `--task-ids` select subsets.
- **MCP runtime sidecar** (`agentdojo-runtime`): each task runs upstream agentdojo in a sidecar container that builds the task's environment (with the attack's injections for the `attack` split) and serves the suite's tools over MCP with upstream's names, descriptions and JSON schemas. Tool calls go through upstream's `FunctionsRuntime`, and the agent sees upstream's YAML-formatted results, or upstream's error message when a call fails.
- **Isolated state**: the environment never leaves the sidecar. The agent can change it only through tool calls, and the main container holds no task data.
- **Final answer channel**: the agent calls `submit_answer` with its final response to the user, which stands in for upstream's last assistant message.
- **Verifier**: asks the sidecar to score the episode with upstream's checks (`TaskSuite._check_task_result`) on the in-memory environment, then writes `reward.json`:
  - `reward`, `utility`: 1 if the user task succeeded
  - `security` (`attack` split only): 1 if the injection task succeeded, as in upstream (lower is better)
- **Oracle**: replays the user task's upstream ground-truth tool calls through MCP, then submits its ground-truth output. It never follows the injection.
- **`metric.py`**: computes upstream's utility, utility under attack and targeted ASR per suite from Harbor job directories, as mean +/- sample SEM across runs.

## Generated Task Structure

```
datasets/agentdojo/
├── workspace-user_task_0/                      # user split
├── workspace-user_task_0-injection_task_0/     # attack split
│   ├── task.toml                               # metadata and the agentdojo MCP server
│   ├── instruction.md                          # system message, tool note, user request
│   ├── environment/
│   │   ├── Dockerfile                          # main (agent) container
│   │   ├── docker-compose.yaml                 # adds the agentdojo-runtime sidecar
│   │   └── runtime-server/
│   │       ├── Dockerfile
│   │       ├── requirements.txt                # pinned agentdojo + fastmcp
│   │       ├── server.py                       # MCP tools and scoring
│   │       └── task_config.json                # suite, task ids, injections
│   ├── solution/
│   │   ├── solve.sh
│   │   ├── oracle.py
│   │   └── oracle.json                         # ground-truth calls and output
│   └── tests/
│       ├── test.sh
│       ├── evaluate.py
│       └── config.json
└── ...
```

Adapter code layout:

```
src/agentdojo/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_agentdojo.yaml
├── metric.py
└── src/agentdojo_adapter/
    ├── __init__.py
    ├── adapter.py
    ├── main.py
    └── task-template/
```

## Run Evaluation / Harness

Tasks need an agent that supports MCP servers (for example `claude-code` or `codex`): the suite tools are only available through the `agentdojo` MCP server. No judge or API key is needed for scoring.

### Running with Datasets Registry

Simply run:

```bash
# Oracle agent (reference solution)
uvx --from harbor==0.25.0 harbor run -d ethz-spylab/agentdojo

# Use your specified agent and model
uvx --from harbor==0.25.0 harbor run -d ethz-spylab/agentdojo -a <agent_name> -m "<model_name>"
```

from the adapters repository root to evaluate on the entire dataset.

However, if you choose to prepare the task directories locally and/or with custom versions/subsets for evaluation, you may either use `harbor run` or `harbor trial`. Instructions for using the adapter code to prepare task directories are provided in the [Usage](#usage-create-task-directories) section.

### Using Job Configurations

The example configuration file for the adapter is provided at `src/agentdojo/run_agentdojo.yaml`.

```bash
# From the repository root
# Run a job with the default adapter configuration
uvx --from harbor==0.25.0 harbor run -c src/agentdojo/run_agentdojo.yaml -a <agent_name> -m "<model_name>"

# Or run a job without configuration yaml but instead with locally prepared dataset path
uvx --from harbor==0.25.0 harbor run -p datasets/agentdojo -a <agent_name> -m "<model_name>"

# Resume a previously started job
uvx --from harbor==0.25.0 harbor job resume -p /path/to/jobs/directory

# Upstream metrics (utility, utility under attack, targeted ASR) per suite
python src/agentdojo/metric.py jobs/<job-dir>
```

Results are saved in the `jobs/` directory by default (configurable via `jobs_dir` in the YAML config). Harbor's own job summary averages each reward key over all trials, so `security` is diluted when a job mixes the two splits; use `metric.py`, or run the splits as separate jobs.

### Running Individual Trial

For quick testing or debugging a single task:

```bash
# Run a single task with oracle
uvx --from harbor==0.25.0 harbor trial start -p datasets/agentdojo/workspace-user_task_0-injection_task_0

# Run a single task with a specific agent and model
uvx --from harbor==0.25.0 harbor trial start -p datasets/agentdojo/workspace-user_task_0 -a <agent_name> -m "<model_name>"
```

Trial outputs are saved in the `trials/` directory by default (configurable via `--trials-dir`).

## Usage: Create Task Directories

```bash
cd src/agentdojo
uv sync
uv run agentdojo --output-dir ../../datasets/agentdojo
```

Available flags:
- `--output-dir`: directory to write generated tasks to (defaults to `datasets/agentdojo` at the repo root)
- `--limit`: generate only the first N tasks (upstream suite order, then task number)
- `--overwrite`: overwrite existing tasks
- `--task-ids`: only generate these tasks, by directory name (e.g. `workspace-user_task_0`, `workspace-user_task_0-injection_task_1`)
- `--split`: `user`, `attack` or `all` (default)
- `--suites`: only these suites
- `--benchmark-version`: AgentDojo benchmark version (default `v1.2.2`)
- `--attack`: registered AgentDojo attack for the `attack` split (default `important_instructions_no_model_name`; see Notes & Caveats)
- `--attack-target-model`: model id whose name attacks such as `important_instructions` address (default `gpt-4o-2024-05-13`, upstream's default model)

Tasks are written to `datasets/agentdojo/` with one directory per task. Each task follows the structure shown in ["Generated Task Structure"](#generated-task-structure) above.

## Comparison with Original Benchmark (Parity)

Parity has not been run yet. The plan (agents, models, attack, number of runs) will be agreed with the Harbor team before any runs.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| TBD | TBD | Utility | TBD | 97 tasks (100% of user split) | TBD | TBD |
| TBD | TBD | Utility under attack | TBD | 949 tasks (100% of attack split) | TBD | TBD |
| TBD | TBD | Targeted ASR | TBD | 949 tasks (100% of attack split) | TBD | TBD |

Planned reproduction:

- **Original side**: upstream's runner with the same model and attack, for example:
  ```bash
  python -m agentdojo.scripts.benchmark --benchmark-version v1.2.2 \
    --model <model> --attack important_instructions_no_model_name
  ```
  Upstream runs models through its own tool-calling pipeline rather than a Harbor agent, so a matching agent for the Harbor side (or upstream support for a Harbor agent) is part of the parity plan.
- **Harbor side**:
  ```bash
  uvx --from harbor==0.25.0 harbor run -c src/agentdojo/run_agentdojo.yaml -a <agent> -m "<model>"
  python src/agentdojo/metric.py jobs/<job-dir>
  ```

## Notes & Caveats

- **Oracle**: all 1,046 tasks reach reward 1.0 with `security` 0 (see the PR for the run). Before writing the adapter, the same ground-truth replay was simulated in process with upstream's checks: 97/97 user tasks and 949/949 pairs succeed, no pair triggers its injection task, and no ground-truth call errors.
- **Instruction**: upstream sends its default system message as the system prompt and the task prompt as the user message. Harbor agents receive one instruction, so `instruction.md` contains the system message verbatim, one added paragraph that names the MCP server and `submit_answer`, and the task prompt verbatim.
- **Final answer**: upstream scores the text of the agent's last message. Here the agent submits it with `submit_answer`; if it never does, the answer is empty, so checks that read the answer fail while checks on the environment and tool calls still apply. The last submission counts. The function stack trace passed to the checks contains every suite tool call (including failed ones), not `submit_answer`.
- **Default attack**: the paper's `important_instructions` attack addresses the victim model by name (e.g. "GPT-4"), which is not known when tasks are generated. The default is upstream's `important_instructions_no_model_name` variant, which says "the AI language model" instead. Pass `--attack important_instructions --attack-target-model <model id>` to bake in a model's name, or any other registered attack. Denial-of-service attacks are scored differently upstream and are rejected.
- **Injection tasks run as user tasks**: with an attack, upstream also runs each injection task on its own and reports how many the model solves, as a capability sanity check. These 35 runs are not generated; upstream's ground truth for workspace injection tasks 10 to 13 is empty, so they would have no oracle.
- **Upstream `TaskSuite.check()`**: in `agentdojo==0.1.35` it reports every user task as "not injectable" because it only reads tool outputs stored as strings, while the package now stores content blocks. The adapter does not rely on it; the in-process simulation above checks ground truth, and `BaseAttack.get_injection_candidates` (which upstream's attacks use) finds injection vectors for every user task.
- **Tool schemas**: identical to upstream's function-calling schemas, except that FastMCP inlines `$ref` definitions; this affects `share_file` (workspace), whose `permission` enum is the same.
- **Step limit**: upstream's tool loop stops after 15 model turns. Harbor agents use their own limits; the agent timeout is 900 s.
- **Scoring closes the task**: the verifier's request to the sidecar's `/evaluate` endpoint first rejects all further tool calls, so the agent cannot use it to probe its score and keep going.
- **Reward on the attack split**: `reward` equals `utility`, as upstream's primary number; `security` is reported next to it and is lower-is-better. Harbor's summary averages `security` over all trials of a job, so use `metric.py` for a mixed job.
- **Benchmark version**: tasks follow v1.2.2, which includes upstream's fixes to workspace user task 16, workspace injection tasks 11 and 12, and banking user task 6.

## Installation / Prerequisites

Adapters are managed as standalone uv Python packages. You can add or remove dependencies using `uv add` / `uv remove` from the adapter directory:

```bash
cd src/agentdojo
uv add <package>     # add a dependency
uv remove <package>  # remove a dependency
```

- Docker installed and running (each task starts the main container and the `agentdojo-runtime` sidecar)
- Harbor (commands above use `uvx --from harbor==0.25.0`)
- Python 3.12+ with `uv` for task generation:
  ```bash
  cd src/agentdojo
  uv sync
  ```
- API keys: only what your agent needs; scoring calls no model

## Troubleshooting

- **Agent has no AgentDojo tools**: the agent must support MCP servers; the tools are served by `agentdojo-runtime` at `http://agentdojo-runtime:8000/mcp`.
- **Verifier exit code 1, no reward**: the verifier could not reach the sidecar, or the sidecar serves a different task than the verifier expects. Check the verifier stdout and the sidecar logs.
- **Slow first build**: the sidecar installs about 115 pinned packages once; later tasks reuse the cached layers.

## Citation

```bibtex
@inproceedings{debenedetti2024agentdojo,
  title={AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for {LLM} Agents},
  author={Edoardo Debenedetti and Jie Zhang and Mislav Balunovic and Luca Beurer-Kellner and Marc Fischer and Florian Tram{\`e}r},
  booktitle={The Thirty-eight Conference on Neural Information Processing Systems Datasets and Benchmarks Track},
  year={2024},
  url={https://openreview.net/forum?id=m1YYAQjO3w}
}
```

## Authors & Contributions
This adapter is developed and maintained by [Jianing Yin](mailto:jianingyin@alumni.upenn.edu).

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines
