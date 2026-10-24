# AgentPersonaBench → Harbor Adapter

## Overview

This adapter converts the survey, chat, web, and os-app surfaces of [AgentPersonaBench](https://github.com/MatrAIx-ai/AgentPersonaBench) into Harbor tasks. The upstream benchmark has 2,460 tasks. This adapter emits 2,301. The other 159 are listed in `EXCLUSIONS.md` and `EXCLUSIONS-<surface>.md` when the dataset is generated. A task is emitted only when its own verifier can score an oracle artifact as fully held. Most chat oracles restate the verifier's HELD clauses as `user_turns.json`. Sixty chat oracles instead use calibrated concrete turns because a rubric restatement was insufficient or unstable. The judge prompt is unchanged.

- **Source**: https://github.com/MatrAIx-ai/AgentPersonaBench (code Apache-2.0, tasks CC-BY-4.0)
- **Paper**: https://arxiv.org/abs/2610.04379
- **What changed**: per-task Dockerfile. Survey and chat images contain that task's `input/` (`bot.md` and `context.md` for chat). Web images start from the upstream Playwright base and add the task site. Os-app images inline the upstream Linux desktop base, then the task's own app install. `solution/solve.sh` is a deterministic oracle. For chat it writes `user_turns.json`. Most tasks restate each verifier HELD clause in the user's voice. The 60 slugs in `chat_oracle_calibrated.txt` use concrete choices and commitments because the restatement did not score stably. Those 60 turns are hand-written and were checked against a judge. `[verifier.env]` passes `ANTHROPIC_API_KEY` through and sets `ADHERENCE_JUDGE_MODEL` to `claude-opus-4-8`. `tests/test.sh` points that verifier at `/logs/verifier/reward.txt`. Web, os-app, and chat reconstruct the task tree the verifier reads, and chat adds `tests/llm_client.py` so the original `from llm_client import chat` still resolves. Task text, `instruction.md`, and verifier pass/fail rules are copied unchanged. Harbor `task.toml` stays the harness config. Where a verifier used to load `[[checks]]` from the benchmark `task.toml`, those tables are written to `tests/checks.toml` and the copied verifier reads that file.
- **Persona**: `persona.yaml` stays in the host task directory. It is not copied into the image. Survey composition is `persona-openhands-sdk`. Chat is `persona-chat`. Web is `persona-web`. Os-app is `persona-computer-1`.

## What is AgentPersonaBench?

AgentPersonaBench checks whether a frozen persona changes what an agent does, not how it describes itself. Survey tasks ask the agent to answer a questionnaire, write a short reply, or submit a small code file. Chat tasks are a 12-turn conversation: the persona is the user, and the task's `bot.md` is the other side. Web tasks ask the agent to use a local page. Os-app tasks ask the agent to use a Linux desktop application. The verifier scores the resulting artifact. A single-attribute task is held or violated. A multi-attribute task awards one point per held check. The task text does not name the trait under test.

## Adapter Features

- Reads a local AgentPersonaBench checkout (`--source` or `$APB_SOURCE`)
- `--surface survey`, `--surface chat`, `--surface web`, or `--surface app`
- Oracle `solve.sh` writes the artifact the upstream verifier treats as fully held
- Upstream `verifier.py` and its answer key are copied unchanged, aside from the `checks.toml` path above
- Survey agent `persona-openhands-sdk` (`agentpersonabench.agents.persona_openhands_sdk:PersonaOpenHandsSdk`): host-side persona prompt, `reasoning_effort=medium`, non-model HTTP blocked
- Chat agent `persona-chat` (`agentpersonabench.agents.persona_chat:PersonaChat` 1.0.0): 12-turn user simulator at temperature 0.7 against `bot.md` at temperature 0.6
- Web agent `persona-web` (`agentpersonabench.agents.persona_web:PersonaWeb` 1.0.0)
- Os-app agent `persona-computer-1` (`agentpersonabench.agents.persona_computer_1:PersonaComputer1`)

## Generated Task Structure

```
agentpersonabench/
├── {task_id}/
│   ├── task.toml                 # Task configuration
│   ├── instruction.md            # Task instructions for the agent
│   ├── persona.yaml              # Host-side persona. Not copied into the image.
│   ├── environment/
│   │   └── Dockerfile
│   ├── solution/
│   │   └── solve.sh              # Oracle
│   └── tests/
│       ├── test.sh
│       ├── verifier.py
│       └── checks.toml           # Present when the verifier reads [[checks]]
```

```
src/agentpersonabench/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
└── src/agentpersonabench/
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

`adapter.py` defines `AgentPersonaBenchAdapter` with a `run()` method. `main.py` constructs it and calls `run()` through the standard CLI flags.

## Run Evaluation / Harness

Harbor Registry & Datasets makes running adapter evaluation easy and flexible.

### Running with Datasets Registry

The dataset is not registered yet. Until the `harbor-datasets` PR is merged, run against a local directory.

```bash
# Oracle check on one generated task
uv run harbor run -p datasets/agentpersonabench/<task_id> -a oracle

# Survey parity agent
PYTHONPATH=src/agentpersonabench/src harbor run -p datasets/agentpersonabench/<survey-task-id> \
  -a agentpersonabench.agents.persona_openhands_sdk:PersonaOpenHandsSdk \
  -m "<provider/model>" --ak reasoning_effort=medium
```

### Using Job Configurations

`run_agentpersonabench.yaml` runs the oracle agent. `run_agentpersonabench_parity.yaml` runs the recorded two-task web parity arm against a directory generated with `--surface web --split parity`. Chat and os-app use different agents, so their reproduction commands remain separate below.

```bash
# From the repository root
harbor run -c src/agentpersonabench/run_agentpersonabench.yaml

# Chat
PYTHONPATH=src/agentpersonabench/src harbor run \
  -a agentpersonabench.agents.persona_chat:PersonaChat \
  -m "dashscope/deepseek-v4.1-flash" -e docker \
  -p datasets/agentpersonabench/<chat-task-id>

# Web
PYTHONPATH=src/agentpersonabench/src harbor run \
  -a agentpersonabench.agents.persona_web:PersonaWeb \
  -m "qwen3.8-flash" -e docker \
  -p datasets/agentpersonabench/<web-task-id>

# Os-app
PYTHONPATH=src/agentpersonabench/src harbor run \
  -a agentpersonabench.agents.persona_computer_1:PersonaComputer1 \
  -m "qwen3.8-flash" -e docker \
  -p datasets/agentpersonabench/<app-task-id>
```

Results are saved in the `jobs/` directory by default.

### Running Individual Trial

```bash
uv run harbor trial start -p datasets/agentpersonabench/<task_id>

PYTHONPATH=src/agentpersonabench/src harbor trial start -p datasets/agentpersonabench/<task_id> \
  -a agentpersonabench.agents.persona_openhands_sdk:PersonaOpenHandsSdk \
  -m "<provider/model>" --ak reasoning_effort=medium
```

## Usage: Create Task Directories

```bash
cd src/agentpersonabench
uv run agentpersonabench --source /path/to/AgentPersonaBench --surface survey --overwrite \
  --output-dir ../../datasets/agentpersonabench
uv run agentpersonabench --source /path/to/AgentPersonaBench --surface chat --overwrite \
  --output-dir ../../datasets/agentpersonabench
uv run agentpersonabench --source /path/to/AgentPersonaBench --surface web --overwrite \
  --output-dir ../../datasets/agentpersonabench
uv run agentpersonabench --source /path/to/AgentPersonaBench --surface app --overwrite \
  --output-dir ../../datasets/agentpersonabench
```

Available flags:

- `--output-dir` — Directory to write generated tasks (defaults to `datasets/agentpersonabench` at the repo root)
- `--limit` — Generate only the first N tasks
- `--overwrite` — Overwrite existing tasks
- `--task-ids` — Only generate specific task IDs
- `--source` — AgentPersonaBench checkout (or set `$APB_SOURCE`)
- `--surface` — `survey` (default), `chat`, `web`, or `app`
- `--split` — `all` or `parity`. The recorded parity subset contains two web, one app, and two chat tasks; it contains no survey task

Generated counts from the current checkout: survey 502 of 502, chat 562 of 565, web 644 of 707, os-app 593 of 686.

## Comparison with Original Benchmark (Parity)

The comparison below is a sampled subset, not a full-benchmark parity. Scores are mean ± sample standard error of the mean. For a single run, sample SEM is undefined, so that row is the one observed reward. Web and os-app used `qwen3.8-flash`, temperature 0, three runs each. Chat used `dashscope/deepseek-v4.1-flash` for the persona and the bot, one run each, scored by the same `glm-4.7` judge with thinking disabled. The benchmark's own judge remains `claude-opus-4-8`. That key currently returns HTTP 401, so these chat scores are not Claude scores.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| persona-web@1.0.0 | qwen3.8-flash | reward | 3 | 1 (vaccines-opposed-web) | 1.000 ± 0.000 | 1.000 ± 0.000 |
| persona-web@1.0.0 | qwen3.8-flash | points (max 3) | 3 | 1 (wellness-web) | 2.333 ± 0.667 | 2.667 ± 0.333 |
| persona-computer-1@1.0.0 | qwen3.8-flash | reward | 3 | 1 (no-budget-apps-app) | 0.333 ± 0.333 | 0.000 ± 0.000 |
| persona-chat@1.0.0 | dashscope/deepseek-v4.1-flash | reward | 1 | 1 (vaccines-opposed-chat) | 1.000 (n=1) | 1.000 (n=1) |
| persona-chat@1.0.0 | dashscope/deepseek-v4.1-flash | points (max 3) | 1 | 1 (wellness-chat) | 3.000 (n=1) | 3.000 (n=1) |

Raw runs: vaccines-opposed-web APB (1, 1, 1), Harbor (1, 1, 1). wellness-web APB (1, 3, 3), Harbor (3, 2, 3). no-budget-apps-app APB (0, 0, 1), Harbor (0, 0, 0). Chat rewards are the single GLM verdict on each side.

Reproduction:

```bash
# Harbor web. Source DashScope credentials first.
PYTHONPATH=src/agentpersonabench/src harbor run -y \
  -a agentpersonabench.agents.persona_web:PersonaWeb \
  -m qwen3.8-flash -e docker \
  -p datasets/agentpersonabench/vaccines-opposed-web -n 3

# Harbor os-app. The recorded runs set temperature 0. Without this variable
# persona-computer-1 uses 0.7.
ADHERENCE_TEMPERATURE=0 PYTHONPATH=src/agentpersonabench/src harbor run -y \
  -a agentpersonabench.agents.persona_computer_1:PersonaComputer1 \
  -m qwen3.8-flash -e docker \
  -p datasets/agentpersonabench/no-budget-apps-app -n 3

# Harbor chat. Judge override used for the recorded scores:
# ADHERENCE_JUDGE_MODEL=glm-4.7 plus ZAI_API_KEY and ZAI_API_BASE.
PYTHONPATH=src/agentpersonabench/src harbor run -y \
  -a agentpersonabench.agents.persona_chat:PersonaChat \
  -m dashscope/deepseek-v4.1-flash -e docker \
  -p datasets/agentpersonabench/vaccines-opposed-chat -n 1

# APB, from an AgentPersonaBench checkout, same model ids.
# Web and os-app: python evaluation/run_task.py <task-path> --model <qwen-arm>
# Chat: LLM_PROVIDER=dashscope LLM_MODEL=deepseek-v4.1-flash
#   python -c "from chat_harness import run_chat_adherence; run_chat_adherence(...)"
```

Multi-attribute reward is an integer point count, matching the upstream verifier, not a 0/1 fraction. Details are in `parity_experiment.json`.

## Notes & Caveats

Emitted tasks keep upstream `instruction.md`, `persona.yaml`, `input/`, and `verifier.py` bytes. The verifier change is the `[[checks]]` path, from the benchmark `task.toml` to `tests/checks.toml`. Persona rendering reads that file, so a tested value such as `None` or `Unknown` stays in the prompt. `persona.yaml` is not copied into the image at build time. Survey does not upload it. Web and chat copy it from `tests/` only after the agent has finished. `persona-computer-1` uploads it to `/app/input/persona.yaml` when the agent starts, matching APB's mixin.

`tests/test.sh` deletes `/logs/verifier/reward.txt` before the verifier runs. The verifier then rebuilds `/input` and `/environment` from the pristine copies under `tests/`, which Harbor uploads only at grade time.

Excluded tasks, 159 of 2,460: survey 0, chat 3, web 63, os-app 93. The current oracle synthesizer has not produced and verified a full-score artifact for the excluded web and os-app tasks; this does not claim that no such artifact can exist. Three chat tasks (`debugger-first-chat`, `instrumentation-first-chat`, `risk-seeking-chat`) raise `OracleError` because the verifier has no HELD clause. Twelve chat verifiers are rule-based. Sixty chat oracles use hand-written calibrated turns (`chat_oracle_calibrated.txt`) because a rubric restatement was insufficient or unstable. The other chat oracles restate the verifier's own HELD sentences; that shows the judge accepts the restatement. `reviewstyle-web` uses the same calibrated review text as `reviewstyle-chat` and a real Playwright trace.

Web pages keep ground truth in `data-*` attributes and HTML comments inside the agent-visible image, as upstream does. `persona-web` does not read those attributes. A shell-capable agent can. Os-app catalogs under `/opt/task-environment/` are in the same position.

The Harbor oracle's latest trial is fully held on all 2,301 emitted tasks, with 0 exceptions. Rewards stay the verifier's point counts, so the mean of the raw rewards is 1.586, not a pass rate. LLM-judge trials in that run used `dashscope/deepseek-v4.1-flash` with thinking disabled, passed through `--verifier-env`. The 60 calibrated turns and the three chat exclusions were gated with `glm-4.7`, thinking disabled. Generated `task.toml` still pins `claude-opus-4-8`. That pin was not used for this oracle, because `ANTHROPIC_API_KEY` returns HTTP 401. The first pass scored 13 tasks short. Their oracle text, or a missing `tests/questionnaire.yaml`, was fixed, and the rerun scored those 13 fully held. Upstream commit `db1b8b493009811314421e7a1775c947762dc3b7`. Harbor 0.18.0.

`persona-computer-1` is Harbor's computer-1 with the persona prompt spliced in. It is not APB's vendored computer-1. On `no-budget-apps-app` the run ranges overlap, and the means differ by 0.333, equal to the APB sample SEM. The pair is unmatched because the agents are not the same program. The recorded os-app runs set `ADHERENCE_TEMPERATURE=0`. The agent uses 0.7 when that variable is unset.

APB's vaccines chat transcript ends with an `[Ended: satisfied — ...]` turn. Harbor's last turn is a normal goodbye. Both scored HELD under `glm-4.7` on the one recorded run. For DeepSeek, the Harbor chat bot uses a completion budget of 8192 because a 1024 budget returns empty `content` after `reasoning_content`. APB's bot budget stays 1024.

The generated dataset lives in `datasets/agentpersonabench`, which is gitignored. The adapter PR contains the adapter. Publishing the tasks is a separate PR to `harbor-datasets`.

## Installation / Prerequisites

```bash
cd src/agentpersonabench
uv sync
```

- Docker installed and running
- Harbor installed (`uv tool install harbor`)
- An AgentPersonaBench checkout for `--source`
- API keys for the agent and, for chat grading, `ANTHROPIC_API_KEY`. `glm-4.7` grading needs `ZAI_API_KEY` and `ZAI_API_BASE`. DashScope models need `DASHSCOPE_API_KEY`.

## Troubleshooting

- Chat reward 0 with `judge HTTP 401` means the Anthropic key was rejected. The verdict is not a content score. `ADHERENCE_JUDGE_MODEL` in the generated `task.toml` is still `claude-opus-4-8`.
- A GLM judge that returns empty text spent the token budget on reasoning. `tests/llm_client.py` disables thinking for model ids that contain `glm`.
- `run_agentpersonabench_parity.yaml` is the recorded web parity agent. Generate `datasets/agentpersonabench-parity-web` with `--surface web --split parity` before using it. Chat and os-app stay on their own commands above.

## Citation

```bibtex
@article{agentpersonabench2026,
  title={AgentPersonaBench: Benchmarking Persona-Driven User Simulation},
  author={Huang, Jintao and others},
  year={2026},
  url={https://arxiv.org/abs/2610.04379}
}
```

## Authors & Contributions

This adapter is developed by Jaden Hou (36116720+JianhengHou@users.noreply.github.com). Benchmark authors are listed in the upstream `CITATION.cff` and copied into each generated `task.toml`.

**Issues and Contributions:**

- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines

## Acknowledgement

API inference for the sampled parity runs used credentials already present in the local environment. No 2077AI parity-key grant was used.
