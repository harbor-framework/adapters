# ASTA Bench → Harbor Adapter

## Overview

[AstaBench](https://github.com/allenai/asta-bench) (Allen Institute for AI) is a suite of scientific-agent benchmarks spanning literature search, scientific QA, data-driven discovery, and code execution. This adapter translates all 11 AstaBench families into Harbor tasks: **2,354 tasks** (1,918 test + 436 validation).

- **Domains**: literature understanding (LitQA2, ArxivDIGESTables, SQA, Paper-Finder), end-to-end discovery (DiscoveryBench, E2E-Bench, E2E-Bench-Hard), code/data-science (DS-1000, SUPER-Expert), reproducible science (CORE-Bench-Hard).
- **Language**: English.
- **Splits/sizes**: per-family counts are in the table below and in [`adapter_metadata.json`](./adapter_metadata.json).
- **Provenance**: [AstaBench: Rigorous Benchmarking of AI Agents with a Scientific Research Suite](https://arxiv.org/abs/2510.21652) (Bragg et al., ICLR 2026). Each family keeps its upstream license; several datasets are gated on Hugging Face (`allenai/asta-bench`, `allenai/super`).
- **Upstream harness**: AstaBench is built on [Inspect AI](https://inspect.aisi.org.uk/); each family is an Inspect `Task` with its own scorer. Harbor does not run Inspect tasks, so every family is re-expressed as a Harbor task with a verifier-side scorer.
- **What is not shipped** (see Notes & Caveats for the reasons): the SUPER "Auto" split (upstream's `super_validation`, 50 samples), and the 18 CORE-Bench capsules that upstream itself filters out because they need a GPU.

| Family | Test | Validation | Scoring |
|---|---:|---:|---|
| `litqa2-fulltext` | 75 | 10 | exact match on the chosen option |
| `litqa2-fulltext-search` | 75 | 10 | recall@30 over gold papers |
| `arxivdigestables-clean` | 100 | 70 | LLM judge (recall of gold table statements) |
| `paper-finder` | 267 | 66 | F1 over gold papers; LLM relevance judge for semantic queries |
| `sqa` | 100 | 100 | LLM judge (rubric, precision, citations) |
| `discoverybench` | 239 | 25 | LLM judge (hypothesis match score) |
| `super-expert` | 45 | 0 | exact match on reported metrics |
| `ds1000` | 900 | 100 | hidden unit tests |
| `core-bench-hard` | 37 | 35 | prediction-interval check on `report.json` |
| `e2e-bench` | 40 | 10 | LLM judge (rubric) |
| `e2e-bench-hard` | 40 | 10 | LLM judge (rubric) |
| **Total** | **1,918** | **436** | |

## What is ASTA Bench?

AstaBench evaluates whether agents can do research-grade scientific work end to end: find relevant papers, answer questions from the literature, build comparison tables, derive hypotheses from data, and reproduce computational results. Each family ships its own scorer; metrics range from exact-match accuracy (LitQA2) to F1 over candidate paper sets (Paper-Finder), LLM-judged rubric scores (SQA, E2E-Bench, ArxivDIGESTables, DiscoveryBench) and prediction-interval checks (CORE-Bench-Hard). It powers the [public leaderboard](https://huggingface.co/spaces/allenai/asta-bench-leaderboard).

## Adapter Features

- **Verifier-side scoring that mirrors upstream.** Each family's `tests/run_scorer.py` is a port of the upstream Inspect scorer: answer parsing, validation rules, metric formulas, judge prompts and judge request parameters are copied from the upstream code (the source file and commit are named in each builder). Judge calls go through `litellm`; the verifier does not depend on Inspect.
- **One verifier contract for all families** (`benchmarks/base.py`): `tests/test.sh` deletes any pre-existing reward before scoring; a missing or invalid answer is a scored 0; a verifier failure (judge/API outage, broken config, or an input on which the upstream scorer raises a sample error) records **no** reward and exits non-zero, so Harbor reports an error instead of a fabricated 0.
- **Two packagings of the same tasks.**
  - Default: the **Inspect-AI bridge dataset**. The task image additionally contains the Inspect runtime and the AstaBench fork, plus a `/app/inspect_config.json` naming the upstream task and sample, so the bridge agent can run the upstream solver.
  - `--cli`: the **standard CLI-agent dataset**. No Inspect runtime and no `inspect_config.json`; the agent sees only `instruction.md` and the task files.
- **Custom agent: `InspectSolver`** (`src/asta_bench/inspect_solver/agent.py`, referenced by `import_path: asta_bench.inspect_solver:InspectSolver`; it is not a Harbor-core agent name). It runs the upstream Inspect task inside the task container with `inspect eval --solver astabench/react --no-score`, writes the solver's final completion to `/app/answer.txt`, and, where the upstream scorer reads a sandbox file instead of the completion (CORE-Bench's `report.json`), copies that file out of the Inspect sandbox before it is destroyed. Scoring is then done by the Harbor verifier, exactly as for any other agent. The bridge fails the run if the model was offered no tool other than `submit`.
- **Literature tools for standard agents.** The open-book families (`paper-finder`, `sqa`, `litqa2-fulltext`, `litqa2-fulltext-search`) wire a stdio MCP proxy to the Asta literature tools, authenticated with `ASTA_TOOL_KEY`.
- **Oracle solutions.** Deterministic families (`litqa2-fulltext`, `litqa2-fulltext-search`, `super-expert`, `ds1000`, `core-bench-hard`, and specific/metadata `paper-finder` queries) are solved by writing the gold answer, which then passes through the real scorer. LLM-judged families cannot reach exactly 1.0 through a judge, so their oracle carries a per-task random nonce (`secrets.token_hex`) that exists only in `solution/solve.sh` and `tests/config.json`; the scorer returns 1.0 for that nonce and judges everything else. The nonce check validates the task plumbing, not the judge.
- **DS-1000 delegation.** The DS-1000 family reuses the sibling [`src/ds1000`](../ds1000) adapter for dataset loading and the Docker environment, then replaces the instruction, `task.toml` and verifier with AstaBench's versions.
- **Generation is fail-loud.** A family or task that cannot be generated makes the command exit non-zero; nothing is skipped silently.
- **`--split parity`** generates the fixed parity subset listed in [`src/asta_bench/parity_task_ids.txt`](src/asta_bench/parity_task_ids.txt).

## Generated Task Structure

```
asta-bench/
├── {family}-{split}-{sample_id}/
│   ├── task.toml                 # name = "allenai/asta-bench__{family}-{split}-{sample_id}"
│   ├── instruction.md            # upstream task input + where to write the answer
│   ├── environment/
│   │   ├── Dockerfile            # task image; bridge packaging adds the Inspect runtime layer
│   │   └── workspace/            # task files; inspect_config.json (bridge packaging only)
│   ├── solution/
│   │   └── solve.sh              # oracle
│   └── tests/
│       ├── test.sh               # shared verifier contract; writes /logs/verifier/reward.txt
│       ├── run_scorer.py         # port of the upstream scorer (run_test.py for ds1000)
│       └── config.json           # gold data; never in the agent image
```

The adapter is a standalone uv package:

```
src/asta-bench/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_asta-bench.yaml              # oracle
├── run_asta-bench_inspect-ai.yaml   # Inspect-AI bridge agent
├── run_asta-bench_cli.yaml          # standard CLI agent (claude-code)
├── tests/                           # offline verifier controls + scorer equivalence tests
└── src/asta_bench/
    ├── adapter.py
    ├── main.py
    ├── parity_task_ids.txt
    ├── asta_mcp/                    # stdio MCP proxy for the Asta literature tools
    ├── benchmarks/                  # one builder per family + base.py
    ├── inspect_solver/              # InspectSolver bridge agent
    └── task-template/
```

## Run Evaluation / Harness

All commands run from the repository root. `uv run --project src/asta-bench --with harbor==0.25.0` runs the Harbor CLI inside this adapter's environment so the bridge agent resolves by import path.

### Running with Datasets Registry

```bash
# Oracle agent
uv run --project src/asta-bench --with harbor==0.25.0 harbor run -d asta-bench

# Specific agent + model
uv run --project src/asta-bench --with harbor==0.25.0 harbor run -d asta-bench -a <agent_name> -m "<model_name>"

# Parity subset
uv run --project src/asta-bench --with harbor==0.25.0 harbor run -d asta-bench@parity -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

```bash
# Oracle
uv run --project src/asta-bench --with harbor==0.25.0 harbor run -c src/asta-bench/run_asta-bench.yaml

# Inspect-AI bridge agent (the parity path)
uv run --project src/asta-bench --with harbor==0.25.0 harbor run -c src/asta-bench/run_asta-bench_inspect-ai.yaml

# Standard CLI agent (claude-code) on the CLI packaging
uv run --project src/asta-bench --with harbor==0.25.0 harbor run -c src/asta-bench/run_asta-bench_cli.yaml

# Resume a job
uv run --project src/asta-bench --with harbor==0.25.0 harbor job resume -p /path/to/jobs/directory
```

### Running Individual Trials

```bash
# Oracle
uv run --project src/asta-bench --with harbor==0.25.0 harbor run -p datasets/asta-bench/asta-bench-inspect-ai/<task_id>

# Standard agent on the CLI packaging
uv run --project src/asta-bench --with harbor==0.25.0 harbor run -p datasets/asta-bench/asta-bench-cli/<task_id> -a <agent> -m "<model>"

# Bridge agent
uv run --project src/asta-bench --with harbor==0.25.0 harbor run -p datasets/asta-bench/asta-bench-inspect-ai/<task_id> \
  --agent-import-path asta_bench.inspect_solver:InspectSolver \
  -m anthropic/claude-haiku-4-5-20251001
```

## Usage: Create Task Directories

```bash
cd src/asta-bench
uv sync

# Inspect-AI bridge packaging (default output: datasets/asta-bench/asta-bench-inspect-ai)
uv run asta-bench --output-dir ../../datasets/asta-bench/asta-bench-inspect-ai

# Standard CLI-agent packaging
uv run asta-bench --output-dir ../../datasets/asta-bench/asta-bench-cli --cli

# Parity subset only
uv run asta-bench --split parity --output-dir ../../datasets/asta-bench/asta-bench-inspect-ai-parity
```

Flags:
- `--output-dir` — where to write tasks (default `datasets/asta-bench/asta-bench-inspect-ai`).
- `--cli` — generate the standard CLI-agent packaging. If the output directory does not end in `cli`, tasks go to a sibling `<name>-cli`.
- `--split` — `test`, `validation`, `all` (default: both), or `parity`.
- `--families` — subset of families (default: all 11).
- `--limit` — first N tasks per (family, split).
- `--task-ids` — only these task ids.
- `--overwrite` — overwrite existing task directories.

Generation needs `HF_TOKEN` with access to the gated `allenai/asta-bench` and `allenai/super` datasets. Task ids are `<family>-<split>-<sanitized_sample_id>`.

## Comparison with Original Benchmark (Parity)

> **Status: the parity experiment is being re-run.** The numbers previously reported for this adapter (original 24.29 ± 0.85 vs Harbor 22.21 ± 2.10, 3 runs per side on 150 tasks, May 2026) were measured on an earlier revision whose Harbor-side scorers, task set and bridge differed from the current code. They are kept in [`parity_experiment.json`](./parity_experiment.json), labelled as superseded, and must not be read as evidence for this revision. This section describes the protocol; the table will be filled from the new runs.

**Setup.** Scenario 3 (custom agent): upstream AstaBench has no Harbor-compatible CLI agent, so parity uses the same solver on both sides — AstaBench's `react` solver with identical tools, prompts and limits.

- **Original side**: the fork [`smiky2011/asta-bench`](https://github.com/smiky2011/asta-bench/tree/claude-haiku-judges) at commit `027d812` (branch `claude-haiku-judges`; the same commit is installed in the Harbor bridge images, see `ASTABENCH_FORK_COMMIT` in `benchmarks/base.py`), run with `inspect eval` and scored by the fork's own Inspect scorers. The fork's README lists how it differs from upstream.
- **Harbor side**: the `InspectSolver` bridge runs the same Inspect task and solver inside the Harbor task container with `--no-score`; the Harbor verifier scores.
- **Solver model**: `anthropic/claude-haiku-4-5-20251001`. **Judge model**: the same model, with each family's upstream sampling parameters (see Notes & Caveats).
- **Subset**: 146 tasks (114 test + 32 validation) across all 11 families, fixed in [`parity_task_ids.txt`](src/asta_bench/parity_task_ids.txt), which also records how the subset was chosen. Parity runs on a subset because a full run costs roughly 16× more.
- **Metric**: each task's reward is its family's upstream headline metric in [0, 1]. Per-family means and the overall mean are reported per run.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| inspect-solver@0.1.0 (react) | claude-haiku-4-5-20251001 | Mean reward (%) | pending | 146 (6.2%) | pending | pending |

**Standard CLI agent (not a parity row).** Upstream has no terminal-agent path, so a standard-agent run has no original side. One Harbor-only `claude-code` run on the CLI packaging of the parity subset will be reported here to show that the tasks are usable by a standard agent; it is not part of `parity_experiment.json`.

**Oracle.** Oracle results for this revision are pending a full run; they will be reported here with the count of tasks and any failures.

**Reproduction.**

```bash
# Harbor side (repository root). Generate the parity subset, then run the bridge agent.
cd src/asta-bench && uv run asta-bench --split parity \
  --output-dir ../../datasets/asta-bench/asta-bench-inspect-ai-parity && cd ../..
export ANTHROPIC_API_KEY=... HF_TOKEN=... ASTA_TOOL_KEY=...
uv run --project src/asta-bench --with harbor==0.25.0 harbor run \
  -p datasets/asta-bench/asta-bench-inspect-ai-parity \
  --agent-import-path asta_bench.inspect_solver:InspectSolver \
  -m anthropic/claude-haiku-4-5-20251001

# Original side (in a checkout of the fork at the pinned commit; Python 3.11).
# Runs the same samples, read from the generated inspect_config.json files.
uv run python scripts/harbor_parity_original_side.py \
  --tasks-dir <adapters repo>/datasets/asta-bench/asta-bench-inspect-ai-parity \
  --log-dir logs/harbor-parity/run-1
```

The script runs one `inspect eval --solver astabench/react` per sample, using the Inspect task, sample id and task arguments from each Harbor task's `environment/workspace/inspect_config.json` (bridge packaging). Do not use bare `--solver react`: it resolves to Inspect's built-in agent, which ignores the tools each AstaBench task provides.

Links: [original benchmark](https://github.com/allenai/asta-bench) · [fork used for parity](https://github.com/smiky2011/asta-bench/tree/claude-haiku-judges) · [adapter PR](https://github.com/harbor-framework/adapters/pull/43) (migrated from [harbor#1654](https://github.com/harbor-framework/harbor/pull/1654)) · [dataset PR](https://github.com/harbor-framework/harbor-datasets/pull/230) · [parity artifacts](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/251).

## Notes & Caveats

**Tasks not shipped**

- **SUPER "Auto" split (upstream `super_validation`, 50 samples) is excluded.** Its metric, `evaluate_entrypoints`, checks an execution history for a run of the entrypoint lasting at least 10 seconds without a traceback. Upstream accepts that history from the agent's own answer (`parse_super_output`), or from `jupyter_cell_history.json`, which the sandbox's Jupyter server writes in the agent's working directory. Both are agent-writable, so the metric cannot be made forgery-proof while staying faithful. `super-expert` therefore ships the Expert (test) split only.
- **CORE-Bench capsules that need a GPU are excluded, as upstream does.** AstaBench runs CORE-Bench with `filter_out_gpu=True`, dropping capsules whose `REPRODUCING.md` mentions "gpu": 8 of 45 test and 10 of 45 validation capsules. The per-capsule verdicts are pinned in `benchmarks/core_bench_gpu_filter.json`.

**Deviations from upstream and special treatments**

- **Judge model.** Upstream uses a different judge per family (`gpt-4o`, `gemini-3-flash`, `claude-sonnet-4-6`). The fork, and this adapter, use `anthropic/claude-haiku-4-5` for all of them so that one Anthropic key suffices. Scores therefore will not match the public leaderboard. Sampling parameters are upstream's, per family: SQA rubric and citation judges use temperature 0.5 / top_p 0.95 and the precision judge temperature 0.5; ArxivDIGESTables and DiscoveryBench use temperature 0; E2E-Bench and the Paper-Finder relevance judge use the API default.
- **Fork changes beyond the judge model.** The fork also (a) adds `astabench/react`, a solver that passes each task's tools to Inspect's ReAct agent; (b) extracts DS-1000 code from `<code>…</code>` before upstream's own post-processing; (c) makes DiscoveryBench's judge-output parsing tolerate list-typed message content. The Harbor scorers mirror the fork.
- **Instruction.** Each `instruction.md` is the upstream `Sample.input` plus a short section saying which file to write the answer to. Benchmark and family names are not mentioned in agent-visible text.
- **Answer location.** Upstream scores the solver's final completion; Harbor scores `/app/answer.txt`. CORE-Bench is scored from `/app/report.json`, as upstream scores `report.json` in its sandbox.
- **CORE-Bench capsules** are downloaded at image build time and stripped exactly as upstream's hard track does (`results/`, `REPRODUCING.md`, `run`, `run.sh`, `environment/` removed), so the agent sees neither the answer files nor the capsule URL. Tarballs are not bundled in the dataset.
- **Oracle nonce** for LLM-judged families: see Adapter Features. Upstream has no oracle.
- **Verifier failures are not scores.** Where upstream turns a judge/API failure into a score of 0 (E2E-Bench), the Harbor verifier records no reward instead. API errors get a small bounded retry, not upstream's open-ended one.
- **Hardening beyond upstream.** DS-1000 executes the submitted snippet inside the test process, so a snippet that exits the process early would count as a pass upstream. The Harbor grader runs the tests in a subprocess with upstream's 180-second timeout and additionally requires a completion marker printed after the tests return.
- **Dataset pin.** All `allenai/asta-bench` files are loaded at revision `a600dc7`. Upstream loads the E2E-Bench files without a revision.
- **Sandbox.** Under the bridge, Inspect runs with `--sandbox local` for the code-execution families: the solver's tools run in the Harbor task container instead of in upstream's nested Docker sandbox. The images mirror upstream's sandbox packages where practical (SUPER uses upstream's base image and requirement files), but CPU, memory and working directory differ.

**Known limitations**

- **Bridge packaging exposes task identity.** `/app/inspect_config.json` names the upstream task and sample, and under `--sandbox local` the solver shares a filesystem with the Inspect harness, its dataset cache and the API keys. The bridge packaging is a parity instrument for running upstream's own solver; use the CLI packaging to evaluate other agents.
- **Open-book and internet.** Every family has `allow_internet = true`: agents need their model API, the literature families need the Asta tools, and SUPER and CORE-Bench tasks install packages and download data. Harbor's Docker environment implements `allow_internet = false` as no network at all, which also cuts off the model API. Several underlying datasets are public, so answer lookup is not prevented by the environment.
- **Asta tool date cutoff.** Upstream restricts the Asta tools to papers inserted before a cutoff date (2025-06-01 for Paper-Finder, 2024-10-17 for the LitQA2 families). The bridge applies it; the MCP proxy used by standard CLI agents does not yet.
- **Paper-Finder verification cost.** Semantic queries are judged with one LLM call per submitted paper (up to 250).
- **`ds1000-test-701`**: the upstream reference solution is multi-statement while the test harness expects a single expression, so the oracle fails on this task. This is a DS-1000 data issue.
- **Resources.** `core-bench-hard` declares 16 GB memory / 30 GB storage and `e2e-bench*` 8 GB / 20 GB; hosted sandboxes with lower caps need Harbor's override flags.

## Installation / Prerequisites

```bash
cd src/asta-bench
uv sync
```

- Docker installed and running.
- Python 3.12+ for the adapter. An upstream checkout for the original side needs **Python 3.11**.
- Run Harbor as `uv run --project src/asta-bench --with harbor==0.25.0 harbor ...` so that `asta_bench.inspect_solver:InspectSolver` is importable. The `oracle` and standard agents need nothing extra.
- Environment variables:
  - `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_BASE_URL`) — solver and judges.
  - `ASTA_TOOL_KEY` — Asta literature tools; required for `paper-finder`, `sqa`, `litqa2-fulltext` and `litqa2-fulltext-search`.
  - `HF_TOKEN` — dataset generation, and bridge runs (Inspect loads the upstream datasets). It needs access to the gated `allenai/asta-bench` and `allenai/super` datasets. It is not forwarded to standard CLI agents.
  - `OPENAI_API_KEY` / `OPENAI_BASE_URL` — only if you use an OpenAI solver model.
- Tests: `uv run --with pytest --with pydantic==2.13.3 --with tabulate==0.10.0 --with scipy==1.17.1 --with nltk==3.9.4 pytest tests -q`. Set `ASTA_BENCH_TASKS_DIR` to a directory of generated tasks to also run the verifier controls against them.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'asta_bench'`** — run Harbor with `uv run --project src/asta-bench --with harbor==0.25.0 harbor ...` from the repository root and reference the agent with `--agent-import-path asta_bench.inspect_solver:InspectSolver` (not `-a inspect-solver`).
- **Bridge run exits with "first model call was offered only ['submit']"** — the solver did not receive the task's tools. Use `astabench/react`, not bare `react`.
- **A trial shows a verifier error instead of a reward** — the judge call failed or the scorer raised. This is deliberate: an outage is not a score. Re-run the trial.
- **`LocalEntryNotFoundError` / 404 from Hugging Face** — the token lacks access to the gated dataset; request access to `allenai/asta-bench` and `allenai/super`.
- **`TypeError: must be called with a dataclass type or instance` from `datasets`** (original side) — the upstream checkout's virtualenv is not Python 3.11.
- **`ValueError: Feature type 'Json' not found`** (original side) — a newer `datasets` wrote the on-disk cache; delete the processed caches under `~/.cache/huggingface/datasets/` for the affected dataset (not `hub/`).
- **Original side downloads many CORE-Bench capsules** — run `astabench/core_bench` with `-T capsule_ids=[<id>]`, as the bridge does, to restrict it to one capsule.

## Citation

```bibtex
@inproceedings{astabench,
  title     = {Asta{B}ench: Rigorous Benchmarking of {AI} Agents with a Scientific Research Suite},
  author    = {Jonathan Bragg and Mike D'Arcy and Nishant Balepur and Dan Bareket and
               Bhavana Dalvi Mishra and Sergey Feldman and Dany Haddad and Jena D. Hwang and
               Peter Jansen and Varsha Kishore and Bodhisattwa Prasad Majumder and
               Aakanksha Naik and Sigal Rahamimov and Kyle Richardson and Amanpreet Singh and
               Harshit Surana and Aryeh Tiktinsky and Rosni Vasu and Guy Wiener and
               Chloe Anastasiades and Stefanus Candra and Jason Dunkelberger and
               Daniel Emery and Rob Evans and Malachi Hamada and Regan Huff and
               Rodney Kinney and Matt Latzke and Jaron Lochner and Ruben Lozano-Aguilera and
               Ngoc-Uyen Nguyen and Smita Rao and Amber Tanaka and Brooke Vlahos and
               Peter Clark and Doug Downey and Yoav Goldberg and Ashish Sabharwal and
               Daniel S. Weld},
  booktitle = {The Fourteenth International Conference on Learning Representations},
  year      = {2026},
  url       = {https://openreview.net/forum?id=M7TNf5J26u},
}
```

## Authors & Contributions

This adapter is developed and maintained by [Quan Shi](mailto:qshi@iskrakow.org).

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository.
- Follow the project's coding style and commit guidelines.

## Acknowledgement

API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
