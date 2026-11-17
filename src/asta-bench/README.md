# ASTA Bench → Harbor Adapter

## Overview

[AstaBench](https://github.com/allenai/asta-bench) (Allen Institute for AI) is a suite of scientific-agent benchmarks spanning literature search, scientific QA, data-driven discovery, and code execution. This adapter translates all 11 AstaBench families into Harbor tasks: **2,403 tasks** (1,918 test + 485 validation).

- **Domains**: literature understanding (LitQA2, ArxivDIGESTables, SQA, Paper-Finder), end-to-end discovery (DiscoveryBench, E2E-Bench, E2E-Bench-Hard), code/data-science (DS-1000, SUPER), reproducible science (CORE-Bench-Hard).
- **Language**: English.
- **Splits/sizes**: per-family counts are in the table below and in [`adapter_metadata.json`](./adapter_metadata.json).
- **Provenance**: [AstaBench: Rigorous Benchmarking of AI Agents with a Scientific Research Suite](https://arxiv.org/abs/2510.21652) (Bragg et al., ICLR 2026). Each family keeps its upstream license; several datasets are gated on Hugging Face (`allenai/asta-bench`, `allenai/super`).
- **Upstream harness**: AstaBench is built on [Inspect AI](https://inspect.aisi.org.uk/); each family is an Inspect `Task` with its own scorer. Harbor does not run Inspect tasks, so every family is re-expressed as a Harbor task with a verifier-side scorer.
- **Not shipped** (see Notes & Caveats): one SUPER "Auto" sample (`checkdst`, whose entrypoint cannot run). Upstream evaluates 2,404 samples; the adapter ships 2,403.

| Family | Test | Validation | Scoring |
|---|---:|---:|---|
| `litqa2-fulltext` | 75 | 10 | exact match on the chosen option |
| `litqa2-fulltext-search` | 75 | 10 | recall@30 over gold papers |
| `arxivdigestables-clean` | 100 | 70 | LLM judge (recall of gold table statements) |
| `paper-finder` | 267 | 66 | F1 over gold papers; LLM relevance judge for semantic queries |
| `sqa` | 100 | 100 | LLM judge (rubric, precision, citations) |
| `discoverybench` | 239 | 25 | LLM judge (hypothesis match score) |
| `super-expert` | 45 | 49 | test (Expert): exact match on reported metrics; validation (Auto): the submitted entrypoint command must run cleanly |
| `ds1000` | 900 | 100 | hidden unit tests |
| `core-bench-hard` | 37 | 35 | prediction-interval check on `report.json` |
| `e2e-bench` | 40 | 10 | LLM judge (rubric) |
| `e2e-bench-hard` | 40 | 10 | LLM judge (rubric) |
| **Total** | **1,918** | **485** | |

## What is ASTA Bench?

AstaBench evaluates whether agents can do research-grade scientific work end to end: find relevant papers, answer questions from the literature, build comparison tables, derive hypotheses from data, and reproduce computational results. Each family ships its own scorer; metrics range from exact-match accuracy (LitQA2) to F1 over candidate paper sets (Paper-Finder), LLM-judged rubric scores (SQA, E2E-Bench, ArxivDIGESTables, DiscoveryBench) and prediction-interval checks (CORE-Bench-Hard). It powers the [public leaderboard](https://huggingface.co/spaces/allenai/asta-bench-leaderboard).

## Adapter Features

- **Verifier-side scoring that mirrors upstream.** Each family's `tests/run_scorer.py` is a port of the upstream Inspect scorer: answer parsing, validation rules, metric formulas, judge prompts and judge request parameters are copied from the upstream code (the source file and commit are named in each builder). Judge calls go through `litellm`; the verifier does not depend on Inspect.
- **One verifier contract for all families** (`benchmarks/base.py`): `tests/test.sh` deletes any pre-existing reward before scoring; a missing or invalid answer is a scored 0; a verifier failure (judge/API outage, broken config, or an input on which the upstream scorer raises a sample error) records **no** reward and exits non-zero, so Harbor reports an error instead of a fabricated 0. Transient judge errors (HTTP 5xx including 502, connection errors, timeouts, rate limits) are retried up to 8 times with 2–60 s backoff before that happens.
- **Two packagings of the same tasks.**
  - Default: the **Inspect-AI bridge dataset**. The task image additionally contains the Inspect runtime and the AstaBench fork, plus a `/app/inspect_config.json` naming the upstream task and sample, so the bridge agent can run the upstream solver.
  - `--cli`: the **standard CLI-agent dataset**. No Inspect runtime and no `inspect_config.json`; the agent sees only `instruction.md` and the task files.
- **Custom agent: `InspectSolver`** (`src/asta_bench/inspect_solver/agent.py`, referenced by `import_path: asta_bench.inspect_solver:InspectSolver`; it is not a Harbor-core agent name). It runs the upstream Inspect task inside the task container with `inspect eval --solver astabench/react --no-score`, writes the solver's final completion to `/app/answer.txt`, and, where the upstream scorer reads a sandbox file instead of the completion (CORE-Bench's `report.json`), copies that file out of the Inspect sandbox before it is destroyed. Scoring is then done by the Harbor verifier, exactly as for any other agent. The bridge fails the run (no reward) if the model was offered no tool other than `submit`, or if Inspect reports a sample error.
- **Literature tools for standard agents.** The open-book families (`paper-finder`, `sqa`, `litqa2-fulltext`, `litqa2-fulltext-search`) wire a stdio MCP proxy to the Asta literature tools, authenticated with `ASTA_TOOL_KEY`.
- **Oracle solutions.** Deterministic families (`litqa2-fulltext`, `litqa2-fulltext-search`, `super-expert`, `ds1000`, `core-bench-hard`, and specific/metadata `paper-finder` queries) are solved by writing the gold answer, which then passes through the real scorer; SUPER Auto oracles submit a real reference command that the verifier re-runs. LLM-judged families cannot reach exactly 1.0 through a judge, so their oracle carries a per-task random nonce (`secrets.token_hex`) that exists only in `solution/solve.sh` and `tests/config.json`; the scorer returns 1.0 for that nonce and judges everything else. The nonce check validates the task plumbing, not the judge.
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

All commands run from the repository root. `uv run --project src/asta-bench --with harbor==0.26.0` runs the Harbor CLI inside this adapter's environment so the bridge agent resolves by import path. On Daytona use `--with 'harbor[daytona]==0.26.0'` and add `-e daytona`.

### Running with Datasets Registry

```bash
# Oracle agent
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -d allenai/asta-bench

# Specific agent + model
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -d allenai/asta-bench -a <agent_name> -m "<model_name>"

# Parity subset
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -d allenai/asta-bench@parity -a <agent_name> -m "<model_name>"

# Standard CLI agents use the CLI packaging, published as a separate dataset
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -d allenai/asta-bench-cli -a claude-code -m "<model_name>"
```

### Using Job Configurations

```bash
# Oracle
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -c src/asta-bench/run_asta-bench.yaml

# Inspect-AI bridge agent (the parity path)
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -c src/asta-bench/run_asta-bench_inspect-ai.yaml

# Standard CLI agent (claude-code) on the CLI packaging
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -c src/asta-bench/run_asta-bench_cli.yaml

# Resume a job
uv run --project src/asta-bench --with harbor==0.26.0 harbor jobs resume -p /path/to/jobs/directory
```

### Running Individual Trials

```bash
# Oracle
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -p datasets/asta-bench/asta-bench-inspect-ai/<task_id>

# Standard agent on the CLI packaging
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -p datasets/asta-bench/asta-bench-cli/<task_id> -a <agent> -m "<model>"

# Bridge agent
uv run --project src/asta-bench --with harbor==0.26.0 harbor run -p datasets/asta-bench/asta-bench-inspect-ai/<task_id> \
  --agent-import-path asta_bench.inspect_solver:InspectSolver \
  -m anthropic/claude-haiku-4-5
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
uv run asta-bench --split parity --output-dir ../../datasets/asta-bench/asta-bench-parity
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

**Setup.** Scenario 3 (custom agent): upstream AstaBench has no Harbor-compatible CLI agent, so parity runs the same Inspect solver on both sides: AstaBench's `astabench/react` (Inspect's ReAct agent with each task's tools), with identical tools, prompts, flags and limits.

- **Original side**: the fork [`smiky2011/asta-bench`](https://github.com/smiky2011/asta-bench/tree/claude-haiku-judges) (branch `claude-haiku-judges`; eval code at `04293fb`, the commit installed in the Harbor bridge images, see `ASTABENCH_FORK_COMMIT` in `benchmarks/base.py`), run with `inspect eval` and scored by the fork's own Inspect scorers. The fork's README lists how it differs from upstream.
- **Harbor side**: the `InspectSolver` bridge runs the same Inspect task and solver inside the Harbor task container with `--no-score`; the Harbor verifier scores.
- **Model**: `claude-haiku-4-5` for the solver and every LLM judge, on both sides. Judges use each family's upstream sampling parameters.
- **Subset**: 150 tasks (114 test + 36 validation) across all 11 families, allocated per family in proportion to family size (minimum 5).
- **Metric**: each task's reward is its family's upstream headline metric in [0, 1]; a run's score is the mean reward over the tasks that received a score, in percent.
- **Same limits on both sides**: `--max-tool-output 65536`, and each task's Harbor `[agent] timeout_sec` (15 min for DS-1000 up to 2 h for CORE-Bench, SUPER and E2E-Bench) is applied on the original side as Inspect's `--time-limit`.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| inspect-solver@0.1.0 (`astabench/react`) | claude-haiku-4-5 | Mean reward (%) | 3 | 150 (6.2%) | 23.87 ± 1.69 | 24.66 ± 0.88 |

Per-run scores: original 27.07, 21.32, 23.22; Harbor 23.72, 26.43, 23.84. The run ranges overlap (original 21.32–27.07, Harbor 23.72–26.43).

Per family (mean ± SEM over the 3 runs, %):

| Family | Tasks | Original | Harbor |
|---|---:|---:|---:|
| `arxivdigestables-clean` | 14 | 36.1 ± 1.4 | 33.5 ± 2.3 |
| `core-bench-hard` | 7 | 71.4 ± 8.2 | 57.1 ± 8.2 |
| `discoverybench` | 22 | 20.4 ± 3.9 | 20.0 ± 1.7 |
| `ds1000` | 30 | 24.4 ± 4.8 | 26.7 ± 3.8 |
| `e2e-bench` | 5 | 2.2 ± 2.2 | 0.0 ± 0.0 |
| `e2e-bench-hard` | 5 | 0.0 ± 0.0 | 0.6 ± 0.6 |
| `litqa2-fulltext` | 7 | 0.0 ± 0.0 | 9.5 ± 4.8 |
| `litqa2-fulltext-search` | 7 | 9.5 ± 4.8 | 14.3 ± 0.0 |
| `paper-finder` | 28 | 4.0 ± 0.2 | 4.7 ± 1.6 |
| `sqa` | 17 | 67.7 ± 2.3 | 71.9 ± 1.4 |
| `super-expert` | 8 | 8.3 ± 2.1 | 8.3 ± 5.5 |

**Standard CLI agent.** One Harbor-only run of `claude-code@2.1.325` (model `claude-haiku-4-5`) on the CLI packaging of the parity subset shows that the tasks are usable by a standard agent.

| Agent | Model | Metric | Runs | Dataset Size | Harbor |
|-------|-------|--------|------|--------------|--------|
| claude-code@2.1.325 | claude-haiku-4-5 | Mean reward (%) | 1 | 150 (6.2%) | 42.05 |

All 150 tasks were scored. Per family (%): `arxivdigestables-clean` 29.4, `core-bench-hard` 57.1, `discoverybench` 30.7, `ds1000` 83.3, `e2e-bench` 20.8, `e2e-bench-hard` 31.6, `litqa2-fulltext` 42.9, `litqa2-fulltext-search` 0.0, `paper-finder` 11.5, `sqa` 75.7, `super-expert` 18.8.

**Oracle.** All 2,403 tasks score 1.0 with the oracle agent (Daytona, 2026-11-15). The SUPER Auto verifier changed afterwards (the submitted command now runs unprivileged), so its 49 tasks were run again on 2026-11-17: 49/49 at 1.0. For the LLM-judged families the oracle's nonce checks the execution and verification wiring, not the judge.

**Reproduction.**

```bash
# Harbor side (repository root). Generate the parity subset, then run the bridge agent.
cd src/asta-bench && uv run asta-bench --split parity \
  --output-dir ../../datasets/asta-bench/asta-bench-parity && cd ../..
export ANTHROPIC_API_KEY=... ANTHROPIC_BASE_URL=... HF_TOKEN=... ASTA_TOOL_KEY=...
uv run --project src/asta-bench --with 'harbor[daytona]==0.26.0' harbor run -y \
  -c src/asta-bench/run_asta-bench_inspect-ai.yaml \
  -p datasets/asta-bench/asta-bench-parity \
  -e daytona --override-memory-mb 8192 --override-storage-mb 10240 -n 20

# Original side, in a checkout of the fork (Python 3.11), installed from its lock file.
git clone -b claude-haiku-judges https://github.com/smiky2011/asta-bench && cd asta-bench
uv sync --frozen
uv run --frozen python scripts/harbor_parity_original_side.py \
  --tasks-dir <adapters repo>/datasets/asta-bench/asta-bench-parity \
  --log-dir logs/harbor-parity/run-1 \
  --model anthropic/claude-haiku-4-5 --concurrency 4
```

The script runs one `inspect eval --solver astabench/react` per sample, using the Inspect task, sample id and task arguments from each Harbor task's `environment/workspace/inspect_config.json` (bridge packaging), and the time limit from its `task.toml`. Do not use bare `--solver react`: it resolves to Inspect's built-in agent, which ignores the tools each AstaBench task provides.

Links: [original benchmark](https://github.com/allenai/asta-bench) · [fork used for parity](https://github.com/smiky2011/asta-bench/tree/claude-haiku-judges) · [adapter PR](https://github.com/harbor-framework/adapters/pull/43) (migrated from [harbor#1654](https://github.com/harbor-framework/harbor/pull/1654)) · [dataset PR](https://github.com/harbor-framework/harbor-datasets/pull/230) · [parity and oracle artifacts](https://huggingface.co/datasets/hqefheq/asta-bench-parity/tree/fa4d57630c4db9a01a28392cb020ab3e686cefc7/adapters/asta-bench).

The artifacts are in the adapter author's Hugging Face repository because `harborframework/parity-experiments` is over Hugging Face's file-count limit and rejects new files. The link is pinned to commit `fa4d57630c4db9a01a28392cb020ab3e686cefc7`; `SHA256SUMS.txt` at that commit (SHA-256 `48159af2311a908f3b212e12b4904b8730ae0e8170655b991bc3a16e4994e442`) lists the checksum of every file. It holds every attempt on both sides, including superseded ones, the per-sample scores and the aggregation script (`original_parity/scores/overall.py`).

## Notes & Caveats

**Tasks not shipped**

- **One SUPER "Auto" sample, `checkdst`.** Its entrypoint only aggregates prediction files that no public code can produce (a submodule repository that no longer exists, an unreachable data server), so it cannot run without fabricated inputs. 

**Deviations from upstream and special treatments**

- **SUPER "Auto" (super-expert validation) is scored differently.** Upstream's metric (`evaluate_entrypoints`) looks for a run of the entrypoint lasting at least 10 seconds without a traceback in an execution history that the agent can write (its own answer, or `jupyter_cell_history.json` in its working directory). Here the agent submits the command it ran (`{"command": ..., "cwd": ...}`; the instruction says so, on both parity sides) and the verifier re-runs that command for 15 seconds in the agent's final environment, applying upstream's rule to the real output. The submitted command is untrusted, so it runs as an unprivileged user with `no_new_privs`, the verifier runs from a root-only copy of `/tests`, and every process the command leaves behind is killed before the reward is written; it cannot write the reward or the grader files. The oracle submits a real reference command for each of the 49 samples. The fork applies the same scoring on the original side. The rule itself is upstream's, including how it decides that the command runs the entrypoint (the entrypoint's file name appears in the command), so a command written only to satisfy that check, rather than to run the entrypoint, can still pass, as upstream.
- **Judge model.** Upstream uses a different judge per family (`gpt-4o`, `gemini-3-flash`, `claude-sonnet-4-6`). The fork, and this adapter, use `claude-haiku-4-5` for all of them so that one Anthropic key suffices.
- **Fork changes beyond the judge model.** The fork also (a) adds `astabench/react`, a solver that passes each task's tools to Inspect's ReAct agent; (b) extracts DS-1000 code from `<code>…</code>` before upstream's own post-processing; (c) makes DiscoveryBench's judge-output parsing tolerate list-typed message content; (d) makes `criteria` optional in SQA's judge schema; (e) scores SUPER Auto as above. The Harbor scorers mirror the fork. The fork commits its `uv.lock` (upstream ignores it), and the original side installs with `uv sync --frozen`; an unlocked install resolves `anthropic` 2.x, which breaks `inspect_ai==0.3.203`.
- **Time limits.** Upstream sets no time limit; Harbor stops the agent at each task's `[agent] timeout_sec` and still runs the verifier (no answer scores 0). For parity the same limit is applied on the original side as Inspect's `--time-limit`. One residual difference: when the limit is hit, Inspect still scores the live sandbox, so CORE-Bench could score a `report.json` written before the limit, whereas the Harbor bridge exports `report.json` only when the solver returns.
- **Instruction.** Each `instruction.md` is the upstream `Sample.input` plus a short section saying which file to write the answer to. Benchmark and family names are not mentioned in agent-visible text.
- **Answer location.** Upstream scores the solver's final completion; Harbor scores `/app/answer.txt`. CORE-Bench is scored from `/app/report.json`, as upstream scores `report.json` in its sandbox.
- **CORE-Bench capsules** are downloaded at image build time and stripped exactly as upstream's hard track does (`results/`, `REPRODUCING.md`, `run`, `run.sh`, `environment/` removed), so the agent sees neither the answer files nor the capsule URL. Tarballs are not bundled in the dataset.
- **DS-1000 images keep `matplotlib==3.8.4`** (DS-1000's own pin). Upstream's shared sandbox installs 3.10.0 for an unrelated solver, under which `ds1000-test-520` and `ds1000-test-649` fail even with the reference solution. No Matplotlib problem is in the parity subset.
- **Oracle nonce** for LLM-judged families: see Adapter Features. Upstream has no oracle.
- **Verifier failures are not scores.** Where upstream turns a judge/API failure into a score of 0 (E2E-Bench), the Harbor verifier records no reward instead. Where the upstream scorer raises on an answer (for example an SQA answer whose citation lacks a `title`), upstream leaves the sample unscored and so does the Harbor verifier.
- **Hardening beyond upstream.** DS-1000 executes the submitted snippet inside the test process, so a snippet that exits the process early would count as a pass upstream. The Harbor grader runs the tests in a subprocess with upstream's 180-second timeout and additionally requires a completion marker printed after the tests return.
- **Dataset pin.** All `allenai/asta-bench` files are loaded at revision `a600dc7`. Upstream loads the E2E-Bench files without a revision.
- **Sandbox.** Under the bridge, Inspect runs with `--sandbox local` for the code-execution families: the solver's tools run in the Harbor task container instead of in upstream's nested Docker sandbox. The images mirror upstream's sandbox packages where practical (SUPER uses upstream's base image and requirement files), but CPU, memory and working directory differ.

**Parity execution details**

- **Where it ran.** Harbor side: Harbor 0.26.0 on Daytona, 20 concurrent trials, every sandbox at 8 GB memory and 10 GB storage (Daytona's per-sandbox cap is 8 GB, so `core-bench-hard` ran with 8 GB instead of the 16 GB its `task.toml` requests). Original side: a Windows laptop (Intel i9-13900H, 32 GB RAM) running WSL2 Ubuntu 22.04 with 15.4 GB visible to WSL and Docker Engine 27.1.2, 4 samples at a time.
- **E2E-Bench scores are dominated by answer formatting, on both sides.** Upstream parses the completion with a strict `json.loads`. `astabench/react` returns the model's closing prose followed by the submitted answer, and a long submission comes back wrapped in Inspect's truncation notice, so most completions do not parse and score 0. This is the same solver, flags and parser on both sides, so it does not separate them, but E2E-Bench scores here say little about the agent's research quality.

**Known limitations**

- **Bridge packaging exposes task identity.** `/app/inspect_config.json` names the upstream task and sample, and under `--sandbox local` the solver shares a filesystem with the Inspect harness, its dataset cache and the API keys. The bridge packaging is a parity instrument for running upstream's own solver; use the CLI packaging to evaluate other agents.
- **Open-book and internet.** Every family has `allow_internet = true`: agents need their model API, the literature families need the Asta tools, and SUPER and CORE-Bench tasks install packages and download data. Harbor's Docker environment implements `allow_internet = false` as no network at all, which also cuts off the model API. Several underlying datasets are public, so answer lookup is not prevented by the environment.
- **Asta tool date cutoff.** Upstream restricts the Asta tools to papers inserted before a cutoff date (2025-06-01 for Paper-Finder, 2024-10-17 for the LitQA2 families). The bridge applies it; the MCP proxy used by standard CLI agents does not yet.
- **Paper-Finder verification cost.** Semantic queries are judged with one LLM call per submitted paper (up to 250).
- **`ds1000-test-701` is sensitive to a trailing newline.** Its test template continues on the line where the solution is inserted (`[insert].numpy()`), so an answer that ends with a newline becomes a syntax error and scores 0. This is how DS-1000 and upstream behave for this problem; it is the only one of the 1,000 with such a template. The oracle writes the reference solution byte for byte and passes.
- **Resources.** `core-bench-hard` declares 16 GB memory / 30 GB storage and `e2e-bench*` and `super-expert` 8 GB; hosted sandboxes with lower caps need Harbor's override flags. Some SUPER tasks train models that use more than 8 GB, so on an 8 GB sandbox the training process can be killed for memory.

## Installation / Prerequisites

```bash
cd src/asta-bench
uv sync
```

- Docker installed and running (or a Daytona account; use `harbor[daytona]`).
- Python 3.12+ for the adapter. A checkout of the fork for the original side needs **Python 3.11** and `uv sync --frozen`.
- Run Harbor as `uv run --project src/asta-bench --with harbor==0.26.0 harbor ...` so that `asta_bench.inspect_solver:InspectSolver` is importable. The `oracle` and standard agents need nothing extra.
- Environment variables:
  - `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_BASE_URL`) — solver and judges.
  - `ASTA_TOOL_KEY` — Asta literature tools; required for `paper-finder`, `sqa`, `litqa2-fulltext` and `litqa2-fulltext-search`.
  - `HF_TOKEN` — dataset generation, and bridge runs (Inspect loads the upstream datasets). It needs access to the gated `allenai/asta-bench` and `allenai/super` datasets. It is not forwarded to standard CLI agents.
  - `OPENAI_API_KEY` / `OPENAI_BASE_URL` — only if you use an OpenAI solver model.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'asta_bench'`** — run Harbor with `uv run --project src/asta-bench --with harbor==0.26.0 harbor ...` from the repository root and reference the agent with `--agent-import-path asta_bench.inspect_solver:InspectSolver` (not `-a inspect-solver`).
- **Bridge run exits with "first model call was offered only ['submit']"** — the solver did not receive the task's tools. Use `astabench/react`, not bare `react`.
- **A trial shows a verifier error instead of a reward** — the judge call failed after its retries, or the scorer raised. This is deliberate: an outage is not a score. Re-run the trial.
- **Daytona: the job dies before any trial starts** — install `harbor[daytona]`, not plain `harbor`.
- **Daytona: every trial of one task fails in about 2 seconds with a build error** — a cancelled image build is cached by Daytona; do not interrupt a job while images build. `EnvironmentStartTimeoutError` on a task whose siblings start fine usually means Daytona's build for that image stalled; resume the job later with `harbor jobs resume -f EnvironmentStartTimeoutError`.
- **`TypeError: Cannot instantiate typing.Union`** (original side or bridge) — `anthropic` 2.x is installed; install the fork with `uv sync --frozen`.
- **`TypeError: must be called with a dataclass type or instance` from `datasets`** (original side) — the fork's virtualenv is not Python 3.11.
- **Original side refuses to start because `detailed_reference.json` exists** — Paper-Finder caches its relevance judgements in the fork checkout during a run; move the file away before the next run so runs stay independent.

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

This adapter is developed and maintained by [Quan Shi](mailto:qshi@iskrakow.org) from the harbor team

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository.
- Follow the project's coding style and commit guidelines.

## Acknowledgement

API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
