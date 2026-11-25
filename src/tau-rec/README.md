## τ-Rec → Harbor Adapter

## Overview

This adapter brings [τ-Rec](https://github.com/nbharaths/tau-rec) to Harbor. τ-Rec is a verifiable benchmark for agentic conversational recommender systems. In each task an agent talks to a simulated user, uses catalog tools, follows a written policy, and makes a movie recommendation, or abstains if nothing in the catalog fits.

- **Size:** 60 tasks, every task in τ-Rec's `movies-v1` track (the `data` track) at v2.1.0. 55 have at least one valid movie; 5 are `no_valid_recommendation` tasks where the correct move is to abstain. Catalog: 153 movies. Language: English.
- **Not included:** the books track (`books-wikidata-v2`), which is a separate track.
- **Provenance:** [github.com/nbharaths/tau-rec](https://github.com/nbharaths/tau-rec), tag `v2.1.0` (commit `8b4c3e6823add74f6c209fff864e2eae6849880c`). MIT license.
- **Main change for Harbor:** τ-Rec's own orchestrator, tools, user simulator and scorer run unchanged in a sidecar container (`movie-runtime`), which exposes the conversation and catalog tools to the agent over MCP. The agent's container holds no τ-Rec code or data.

## What is τ-Rec?

Most conversational recommender benchmarks use an LLM as the judge, which can be biased and inconsistent. τ-Rec checks success programmatically instead. Each task states the user's constraints as structured predicates over the catalog (`runtime <= 120`, `genres contains Comedy`, ...). The simulated user reveals them at a controlled rate: some up front, some only when asked, and some never, so the agent has to infer them from rejections. A trial's reward is `constraint × policy`: 1 only if the final recommendation satisfies every constraint (or, on `no_valid_recommendation` tasks, the agent correctly abstains) and the agent broke no policy rule. τ-Rec reports `pass^k` over repeated trials to reward consistency. Paper: *τ-Rec: A Verifiable Benchmark for Agentic Recommender Systems*, RecSys 2026 ([doi:10.1145/3773078.3831847](https://doi.org/10.1145/3773078.3831847)).

## Adapter Features

- **Native runtime in a sidecar.** The `movie-runtime` sidecar runs τ-Rec's own `Orchestrator`, `ToolKit`, user simulator and policy. The agent reaches it only through MCP tools (start the conversation, message the user, search and inspect the catalog, recommend). Nothing is re-implemented, so the conversation and scoring are τ-Rec's.
- **Tamper-resistant grading.** The authoritative conversation trace is written to a sidecar-only path (`/var/lib/tau-rec/trace.json`) and collected by Harbor as an artifact after the agent stops. Grading runs in a separate verifier environment (`environment_mode = "separate"`) built from a pinned τ-Rec clone, using τ-Rec's `CombinedEvaluator`. A forged trace written from the agent's container does not change the reward (tested).
- **No answers in reach.** The agent's image is Python plus `mcp` only, and the tools it sees are named neutrally. The gold answers live only in the sidecar and verifier images.
- **Pinned builds.** Every image clones τ-Rec at `v2.1.0` and checks the commit, uses `uv sync --frozen`, a digest-pinned Python base image, a pinned `uv`, and a constraints file for the MCP packages.
- **Oracle.** `solution/` holds a scripted oracle that plays a correct conversation for each task. It scores 60/60.
- **Parity agent.** `tau_rec_parity_agent.py` wraps τ-Rec's own `LiteLLMAgent`, so Harbor-side parity runs send the same model requests as the original harness.
- **Checkout check.** The adapter verifies that `--tau-rec-root` is at the pinned commit, and clones the pinned tag into `src/tau-rec/.cache/tau-rec` if no checkout is given.

## Generated Task Structure

```
datasets/tau-rec/
├── task_001/ … task_060/
│   ├── task.toml                     # task config: MCP server, artifacts, separate verifier
│   ├── instruction.md                # what the agent is told
│   ├── environment/
│   │   ├── Dockerfile                # main (agent) image: python + mcp only
│   │   ├── constraints.txt           # pinned MCP sub-dependencies
│   │   ├── docker-compose.yaml       # main + movie-runtime sidecar
│   │   └── runtime-server/           # sidecar: τ-Rec runtime behind MCP
│   │       ├── Dockerfile
│   │       ├── server.py
│   │       └── bridge.py
│   ├── solution/                     # oracle
│   │   ├── solve.sh
│   │   ├── oracle.py
│   │   └── oracle_plan.json
│   └── tests/                        # separate verifier
│       ├── Dockerfile
│       ├── test.sh
│       ├── evaluate.py
│       └── config.json
```

Adapter code:
```
src/tau-rec/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_tau-rec.yaml
├── tau_rec_parity_agent.py          # parity agent (Harbor side)
├── run_tau_rec_parity_agent.py      # its in-container runner
├── src/tau_rec_adapter/
│   ├── adapter.py                   # TauRecAdapter(...).run()
│   ├── main.py                      # CLI
│   └── task-template/
└── tests/                           # adapter unit tests
```

The package is named `tau_rec_adapter` rather than `tau_rec` because `tau_rec` is the upstream benchmark's own package, which the adapter imports; the same name would shadow it.

## Run Evaluation / Harness
Harbor Registry & Datasets makes running adapter evaluation easy and flexible.

### Running with Datasets Registry

 Simply run

```bash
# Use oracle agent (reference solution)
harbor run -d tau-rec

# Use your specified agent and model
harbor run -d tau-rec -a <agent_name> -m "<model_name>"
```
from the repository root to evaluate on the entire dataset.


However, if you choose to prepare the task directories locally and/or with custom versions/subsets for evaluation, you may either use `harbor run` or `harbor trial`. Instructions for using the adapter code to prepare task directories are provided in the [Usage](#usage-create-task-directories) session.

### Using Job Configurations
The example configuration file(s) for the adapter is provided under `src/tau-rec`. You may either use `-c path/to/configuration.yaml` or `-p path/to/dataset` to run evaluation on the entire benchmark after preparing the task directories locally.


```bash
# From the repository root
# Run a job with the default adapter configuration
harbor run -c src/tau-rec/run_tau-rec.yaml -a <agent_name> -m "<model_name>"

# Or run a job without configuration yaml but instead with locally prepared dataset path
harbor run -p datasets/tau-rec -a <agent_name> -m "<model_name>"

# Resume a previously started job
harbor job resume -p /path/to/jobs/directory
```

Results are saved in the `jobs/` directory by default (configurable via `jobs_dir` in the YAML config).

#### Running the oracle locally

Every trial, oracle included, needs `OPENAI_API_KEY`: the `movie-runtime` sidecar's user simulator (`gpt-5-mini` by default, `TAU_REC_USER_MODEL` to change it) calls OpenAI. `OPENAI_BASE_URL` is optional.

```bash
export OPENAI_API_KEY=...   # required; the sidecar refuses to start without it
harbor run -y -c src/tau-rec/run_tau-rec.yaml
```

- `harbor run` asks for confirmation before passing host env vars (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `TAU_REC_USER_MODEL`) into the tasks; `-y` answers yes, which non-interactive runs (CI, scripts, no TTY) need or the run aborts.
- Logs: the authoritative trace stays in the sidecar at `/var/lib/tau-rec/trace.json`; Harbor collects it into the trial's `artifacts/` dir after the agent stops, and the separate verifier grades that copy.
- Docker needs the Compose v2 plugin (`docker compose`). Containers on Compose networks must resolve `api.openai.com`; a sidecar that cannot reach OpenAI keeps retrying the user turn rather than failing fast.

### Running Individual Trial

For quick testing or debugging a single task:

```bash
# Run a single task with oracle (pre-written solution)
harbor trial start -p datasets/tau-rec/<task_id>

# Run a single task with a specific agent and model
harbor trial start -p datasets/tau-rec/<task_id> -a <agent_name> -m "<model_name>"
```

Trial outputs are saved in the `trials/` directory by default (configurable via `--trials-dir`).


## Usage: Create Task Directories

```bash
cd src/tau-rec
uv run tau-rec                          # writes ../../datasets/tau-rec; clones τ-Rec v2.1.0 if needed
uv run tau-rec --tau-rec-root /path/to/tau-rec-v2.1.0 --overwrite
```

Available flags:
- `--output-dir` — Directory to write generated tasks (default: the repo-root `datasets/tau-rec`)
- `--limit` — Generate only the first N tasks
- `--overwrite` — Overwrite existing tasks
- `--task-ids` — Only generate these task IDs, space-separated (e.g. `--task-ids task_001 task_002`)
- `--tau-rec-root` — A τ-Rec checkout at the pinned v2.1.0 commit (default: `$TAU_REC_ROOT`, else a clone of the pinned tag in `src/tau-rec/.cache/tau-rec`). Any other commit is rejected.

Tasks are written to `datasets/tau-rec/` with one directory per task. Each task follows the structure shown in ["Generated Task Structure"](#generated-task-structure) above.

## Comparison with Original Benchmark (Parity)

Parity compares tau-Rec's own harness (`tau-rec run`) with the Harbor adapter on all 60 movies-v1 tasks, 3 runs per side and 1 trial per task per run. Both sides use the same agent: `tau-rec-parity-agent` runs tau-Rec's native `LiteLLMAgent` against the `movie-runtime` MCP sidecar, which hosts tau-Rec's own orchestrator, tools and scorer. Scores are **mean ± sample SEM** over runs. See `parity_experiment.json` for the raw per-run scores.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| tau-rec-parity-agent@1.0 | gpt-5-mini-2025-08-07 | Average Reward (= pass^1) | 3 | 60 (100%) | 38.33% ± 0.96% | 43.89% ± 2.42% |
| claude-code@2.1.329 | claude-haiku-5-5 | Average Reward | 1 | 60 (100%) | – | 50.00% |

- Per-run scores: original 36.67%, 38.33%, 40.00%; Harbor 43.33%, 48.33%, 40.00%. The run-score ranges overlap, at 40.00%.
- Pooled over the 3 runs: pass^1/2/3 is 0.383/0.283/0.233 on the original and 0.439/0.333/0.283 on Harbor. The paired per-task Δ pass^1 (Harbor − original) is +0.056, with a task-bootstrap 95% interval of [−0.006, +0.122]. pass^4 is not reported because each side has 3 runs; pass^1/2/3 are given.
- A fidelity diagnostic found no structural difference between the two sides. The system prompt, tool definitions and greeting, and the user-simulator request, were compared in-process for all 60 tasks; first-request token counts were also compared across all 360 trials. Tool results, error text and the abstain path were checked in stubbed-model equivalence tests (3 extra scripted scenarios covering 7 behaviours, all identical, beyond the adapter's own parity-agent tests) and against counts from the real runs (tool-error results 1/3656 original vs 0/3720 Harbor; the same two recommend argument forms on abstain). Harbor scored at or above the original in every round, recommended (rather than abstained) more often (on 21 of the 30 tasks where the recommend count differs; sign test p=0.043, paired permutation p=0.067), and had fewer multi-turn conversations (13% vs 23% of trials with two or more agent turns). These p-values are uncorrected across the several metrics examined. The pattern is consistent with sampling variance, but a systematic difference is not ruled out. These 3+3 runs predate the adapter's later integrity changes (separate verifier, sidecar-only trace, benchmark data removed from the agent container) and were not repeated in full; after those changes the oracle scored 60/60, and an 8-task parity sanity check scored 5/8 on Harbor and 4/8 on the original (paired delta +0.125, task-bootstrap 95% interval 0 to +0.375 over 8 tasks; the earlier sanity run on the same 8 tasks scored 3/8 on both sides). The parity agent's model requests were not changed by those edits: its tau-Rec Python environment, installed afresh after the change, has a package list (uv pip freeze) identical to the previous environment's, and the in-process request-comparison and stubbed-model equivalence tests still pass.
- The claude-code row is a single standard-agent run with no original-benchmark equivalent. It shows that a Harbor CLI agent can drive the tasks through the MCP tools. This run was made after the adapter's integrity changes (separate verifier, sidecar-only trace, benchmark data removed from the agent container); an earlier run before those changes scored 51.67%. One trial (`task_025`) hit a claude-code installer TLS error during agent setup, before any model call, and Harbor's configured infrastructure retry re-ran it automatically; all 60 tasks are scored (30/60 correct). Codex could not be run on the OpenAI account used here (OpenAI rejected the requests with `codex_byok_restricted_by_api_credit_promo`: the organization is enrolled in the monthly API Credits benefit with ChatGPT subscriptions, which blocks bring-your-own-key Codex usage), so claude-code was used instead.

Reproduction:
- **Original side:** run [tau-Rec](https://github.com/nbharaths/tau-rec) at tag `v2.1.0` (commit `8b4c3e6823add74f6c209fff864e2eae6849880c`), after `uv sync --frozen`, with `OPENAI_API_KEY` set:
  ```bash
  uv run --frozen tau-rec run --track data --trials 1 --model gpt-5-mini-2025-08-07 --output <dir>
  ```
  The defaults are tools mode, keyword retrieval (bm25-v1), `--max-turns 20`, no trial timeout, and the `gpt-5-mini` simulator at temperature 1.0. Run it 3 times.
- **Harbor side:** from the repository root, with `OPENAI_API_KEY` set, run 3 times:
  ```bash
  PYTHONPATH="$PWD/src/tau-rec" harbor run -y -c src/tau-rec/run_tau-rec.yaml \
    -a tau_rec_parity_agent:TauRecParityAgent -m gpt-5-mini-2025-08-07
  ```
  `PYTHONPATH="$PWD/src/tau-rec"` is required. The parity agent is imported from `src/tau-rec/` (import path `tau_rec_parity_agent:TauRecParityAgent`), and `harbor` does not put `src/tau-rec/` on `sys.path`. Without it, the run fails with `No module named 'tau_rec_parity_agent'`.
- **Standard agent:** set `ANTHROPIC_API_KEY` for the agent and `OPENAI_API_KEY` for the simulator, then run:
  ```bash
  harbor run -y -c src/tau-rec/run_tau-rec.yaml -a claude-code -m anthropic/claude-haiku-5-5 --ak version=2.1.329
  ```
- **Scoring:** a trial's reward is tau-Rec's primary reward (0 or 1). A run's score is the mean reward over the 60 tasks.

## Notes & Caveats

- **Launching the parity agent:** run `harbor run` from the repository root with `PYTHONPATH="$PWD/src/tau-rec"`. The agent is imported as `tau_rec_parity_agent:TauRecParityAgent`, and without that path the import fails with `No module named 'tau_rec_parity_agent'`.
- **Every trial calls OpenAI:** the `movie-runtime` sidecar's user simulator (`gpt-5-mini`) needs `OPENAI_API_KEY` for every trial, oracle included.
- **Re-runs after host sleep:** the first attempt at round 1 stalled while the host was repeatedly asleep and was stopped by the operator. Its partial outputs were discarded on both sides, and round 1 was relaunched. The host slept again during the relaunched round 1. The trials in flight during that sleep were `task_001`–`task_008` on Harbor and `task_001`–`task_010` on the original side; `task_001`–`task_010` were re-run once on **both** sides, and those re-runs replace the originals in round 1. No other trials were replaced.
- **Standard-agent retry:** in the claude-code run, one trial (`task_025`) hit a claude-code installer TLS error during agent setup, before any model call. Harbor's configured infrastructure-only retry (`max_retries: 2`, for `NetworkConnectionError` and `AgentSetupTimeoutError`) re-ran it automatically, and the retried trial is the one scored, so all 60 tasks are scored. This was an infrastructure failure, not an agent outcome.
- **DNS on colima:** on the colima Docker VM used here, the VM resolver timed out on IPv6 (AAAA) lookups. That breaks CLI agents (codex, claude-code) inside `main`, while A-record lookups, the sidecar and the parity agent were unaffected. The standard-agent runs used a run-level compose overlay that sets `dns: [8.8.8.8, 1.1.1.1]` on `main` (passed with `--extra-docker-compose`); it is not part of the adapter. Codex and claude-code also install node and their CLI in every trial, so a longer agent-setup timeout (`--agent-setup-timeout-multiplier`) helps on slow hosts.
- **Codex not run:** Harbor's `codex` agent could not be run on the OpenAI account used here. OpenAI rejected its requests with `codex_byok_restricted_by_api_credit_promo`: the organization is enrolled in the monthly API Credits benefit with ChatGPT subscriptions, which blocks bring-your-own-key Codex usage. The standard-agent run used `claude-code` instead.
- **Residual difference:** see the parity section. Harbor scored at or above the original in every round, recommended more often, and had fewer multi-turn conversations. This is consistent with sampling variance, but a systematic difference is not ruled out.

## Installation / Prerequisites

- Docker with the Compose v2 plugin (`docker compose`), running.
- Harbor installed (see the main repository README).
- Adapter environment:
  ```bash
  cd src/tau-rec
  uv sync
  ```
- `OPENAI_API_KEY` for every trial (the sidecar's user simulator), plus the key for whichever agent model you run (e.g. `ANTHROPIC_API_KEY` for claude-code).
- Network access during image builds and trials: the sidecar and verifier images clone τ-Rec from GitHub, and the parity agent installs τ-Rec in the agent container at setup.

## Troubleshooting

- **`No module named 'tau_rec_parity_agent'`** when running the parity agent: run from the repository root with `PYTHONPATH="$PWD/src/tau-rec"`.
- **Sidecar exits at start:** `OPENAI_API_KEY` is not set, or `-y` was not passed in a non-interactive run, so Harbor did not forward host env vars.
- **Trials hang on the user's turn:** the sidecar cannot reach `api.openai.com`; it retries instead of failing. Check DNS and network from Compose containers.
- **CLI agents fail to install (DNS errors, `EAI_AGAIN`, TLS errors):** on colima the VM resolver can time out on IPv6 lookups. A compose overlay that sets `dns: [8.8.8.8, 1.1.1.1]` on `main` (`--extra-docker-compose`), a larger `--agent-setup-timeout-multiplier`, and infra-only retries (`NetworkConnectionError`, `AgentSetupTimeoutError`) fixed it here.
- **Build timeouts on a cold cache:** `build_timeout_sec` is 600. The first build clones τ-Rec and installs its locked environment, which can take longer on a slow network; re-run once the cache is warm, or raise the timeout locally.
- **`verify_checkout` errors about a missing `data/tasks` or a non-git directory:** a clone into `src/tau-rec/.cache/tau-rec` was interrupted. Delete `src/tau-rec/.cache/tau-rec` and re-run.

## Citation

```bibtex
@inproceedings{narasimhan2026taurec,
  title     = {$\tau$-Rec: A Verifiable Benchmark for Agentic Recommender Systems},
  author    = {Narasimhan, Bharath Sivaram and Narasimhan, Karthik R},
  booktitle = {Proceedings of the 20th ACM Conference on Recommender Systems},
  pages     = {915--919},
  year      = {2026},
  publisher = {Association for Computing Machinery},
  doi       = {10.1145/3773078.3831847},
  url       = {https://github.com/nbharaths/tau-rec}
}
```

## Authors & Contributions

This adapter is developed and maintained by Bharath Sivaram Narasimhan, one of τ-Rec's authors.

**Issues and Contributions:**
- Adapter issues and pull requests: this repository.
- Benchmark issues (tasks, catalog, scoring): [nbharaths/tau-rec](https://github.com/nbharaths/tau-rec).

**Agent use:** Claude Code wrote the adapter code and tests and ran the experiments. I set the design and the parity plan, approved all spend, and reviewed the results.

## Acknowledgement

Parity experiments were self-funded; no Harbor-provided API keys were used.
