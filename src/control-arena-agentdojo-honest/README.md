# ControlArena AgentDojo honest travel

## Overview

See the [suite coverage](../../docs/control-arena.md) for the other ControlArena settings.

This adapter generates four information-retrieval tasks from AgentDojo's simulated travel suite. An agent queries a local directory and writes a text answer. The separate verifier uses the same AgentDojo main-task scoring function that ControlArena calls. Scope is four of the travel suite's 20 user tasks, from the suite version selected by ControlArena 20.1.1. [ControlArena release](https://github.com/UKGovernmentBEIS/control-arena/tree/v20.1.1/control_arena/settings/agentdojo_setting) · [AgentDojo package](https://pypi.org/project/agentdojo/0.1.33/)

## What is AgentDojo?

AgentDojo evaluates agents working with tools in simulated environments. This adapter measures honest user-task utility for two restaurant questions and two car-rental questions. The underlying AgentDojo benchmark version is `v1.2.1`, provided by the pinned `agentdojo==0.1.33` Python package. [Setting catalog](https://control-arena.aisi.org.uk/settings/agentdojo.html)

## Adapter Features

- `travel-user-task-9` and `travel-user-task-10` use read-only restaurant listings, cuisine, hours, prices, ratings/reviews and addresses. `travel-user-task-13` and `travel-user-task-14` use read-only car-company listings, vehicle types, fuel options, ratings/reviews and daily prices.
- `travel-lookup` accepts a named lookup and literal values. The generator copies the reviewed native Python function definitions and projects only the corresponding simulated businesses' public fields into the workspace. Each task exposes only its own domain's lookups.
- The verifier restores the pristine simulated environment, grades the submitted text with the original `_check_task_result` path, and records the binary `main_task_success` verdict. The reference solution is the upstream task's reference output.

## Generated Task Structure

```text
travel-user-task-9/
├── task.toml
├── instruction.md
├── environment/    # lookup CLI, reviewed function definitions, directory data, upstream license
├── solution/       # solve.sh and private reference answer
└── tests/          # separate verifier, locked dependencies, case ID and grade.py
```

## Run Evaluation / Harness

From the adapter directory, generate the tasks and run the included oracle job with Harbor 0.27.0 and a Linux Docker engine.

```bash
harbor run -c run_control-arena-agentdojo-honest.yaml
```

In an agent workspace, `travel-lookup --help` lists the available commands. For example, `travel-lookup get_all_restaurants_in_city Paris` lists the simulated Paris restaurants in a restaurant task. Save the final plain-text answer to `/logs/artifacts/answer.txt`. The verifier publishes `verifier/reward.json` and the same scalar in `verifier/reward.txt`.

## Usage: Create Task Directories

```bash
cd src/control-arena-agentdojo-honest
uv sync --locked
uv run control-arena-agentdojo-honest --output-dir datasets/control-arena-agentdojo-honest
```

Use `--task-ids travel-user-task-9 travel-user-task-10` to select individual rows. Qualified names such as `control-arena/travel-user-task-9` also work. `--limit` caps the selection and `--overwrite` replaces an existing generated task.

## Comparison with Original Benchmark (Parity)

| Agent | Model | Metric | Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
| --- | --- | --- | ---: | ---: | --- | --- |
| Pending live comparison | Pending | Honest main-task utility | 0 | 4 | Pending | Pending |

All four reference submissions received `main_task_success=1` in a Harbor 0.27.0 Docker oracle job with zero trial errors. The three offline regression tests also passed in a freshly installed locked environment.

Run the offline comparison from the package directory. It compares every exposed lookup against its native result, verifies the original prompt on all four rows, and checks native and adapted verdicts on reference, empty and unrelated text.

```bash
uv run python -m unittest discover -s tests -v
```

## Notes & Caveats

The original tool-calling interface becomes a local CLI. Restaurant questions see the simulated Paris restaurant records and rental questions see the Los Angeles rental records. A Harbor shell agent can also read these projected records directly. Read-only operations leave the simulated environment unchanged, and the four reviewed upstream utility methods grade the answer independently of the lookup trace. The Harbor verifier reconstructs the native pre- and post-task state separately from the disposable agent workspace. Reference answers are confined to the private solution directory. Protect generated solutions and evaluation logs when sharing results. [ControlArena data guidance](https://github.com/UKGovernmentBEIS/control-arena/tree/v20.1.1#avoiding-data-contamination)

This slice excludes the remaining travel questions, the other AgentDojo suites, side tasks, injections, and state-changing operations. Its measurement is honest task utility. Monitor behavior, attacks, and protocol safety require different measurements.

## Installation / Prerequisites

The independent uv project uses Python 3.13. Install Harbor 0.27.0 separately for running Docker trials. Package resolution and the first image build require access to public package and image registries. Execution uses local fixture data and the verifier needs no model provider. On Windows, set `$env:PYTHONUTF8 = '1'` before generation and evaluation.

## Troubleshooting

If a lookup name is rejected, use `travel-lookup --help` inside that task's workspace. Pass full business names with spaces as individually quoted arguments. A missing, empty, or invalid UTF-8 submission receives the native utility for an empty answer.

## Citation

```bibtex
@inproceedings{debenedetti2024agentdojo,
  author = {Edoardo Debenedetti and Jie Zhang and Mislav Balunovic and Luca Beurer-Kellner and Marc Fischer and Florian Tramèr},
  title = {AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents},
  booktitle = {NeurIPS},
  year = {2024}
}
```

## Authors & Contributions

AgentDojo was developed by Edoardo Debenedetti and coauthors. ControlArena was developed by the UK AI Security Institute, Redwood Research, and contributors. The Harbor adapter was prepared by lijingxian. [AgentDojo](https://github.com/ethz-spylab/agentdojo) · [ControlArena](https://github.com/UKGovernmentBEIS/control-arena)
