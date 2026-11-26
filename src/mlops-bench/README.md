# MLOps-Bench — Harbor Adapter

## Overview

MLOps-Bench evaluates coding agents on production ML-engineering changes across the
MLOps lifecycle. Each task asks the agent to complete a CI-facing stage gate (data
pipeline validation, feature parity, training gate, serving gate, monitoring gate,
release/governance gate, or end-to-end release flow) in a small Python workspace, and
scores the result with executable behavioral tests.

- **Size:** 212 tasks, all of the released benchmark (no exclusions). They come from 31
  public ML repositories × 7 lifecycle stages (a few repositories are missing a stage
  upstream).
- **Language / tooling:** Python, standard library only; pytest for scoring. CPU-only,
  no network needed by the tasks themselves.
- **Scoring:** 1,492 behavioral tests: 636 fail-to-pass (F2P) tests for the new
  behavior and 856 pass-to-pass (P2P) tests for behavior that must keep working.
- **Provenance:** [oracle-samples/mlops-bench](https://github.com/oracle-samples/mlops-bench)
  at commit `8f48b685df0491af048bde4b56c7917d0e42d336`, Apache-2.0; paper
  [arXiv:2610.23506](https://arxiv.org/abs/2610.23506) (EMNLP 2026 Findings).
- **Main adaptation:** upstream ships no runner or prompt template. The adapter renders
  each task's `problem.json` specification into `instruction.md`; the original side of
  the parity experiment is a runner in a fork of the benchmark that sends the same
  prompt (see [Parity](#comparison-with-original-benchmark-parity)).

## What is MLOps-Bench?

MLOps-Bench ([Tran et al., 2026](https://arxiv.org/abs/2610.23506)) asks whether AI
agents can make reliable, repository-compatible MLOps changes rather than only write ML
code. Every task combines a natural-language specification, an editable starting
workspace (`repo/`), a plausible but incomplete baseline (`buggy/`), an oracle
implementation (`oracle/`), and F2P/P2P behavioral tests. The paper reports two
metrics: **task completion rate** (all scoring tests pass) and **test pass rate**
(fraction of individual scoring tests passed). Upstream evaluation gives the agent only
the task specification and `repo/`, then scores the edited workspace with
`tests/test_f2p.py` and `tests/test_p2p.py`.

## Adapter Features

- **Pinned, reproducible source:** clones `oracle-samples/mlops-bench` at a pinned
  commit (or uses a local clone via `--source-dir`) and records the commit in each
  `task.toml`.
- **Stable task names:** `oracle-samples/mlops-bench__<slug>`, where the slug is the
  upstream `instance_id` lowercased with non-alphanumerics replaced by hyphens, e.g.
  `MLO-25_GREAT_EXPECTATIONS__GREAT_EXPECTATIONS-04_MODEL_SERVING` →
  `mlo-25-great-expectations-great-expectations-04-model-serving`.
- **Instruction rendering:** `instruction.md` renders the `problem` block of
  `problem.json` (title, context, objective, requirements, success criteria, technical
  constraints, public API contract, data context, system context and constraints,
  evaluation criteria) without rewording, plus one line giving the workspace location.
  The `metadata` block is omitted.
- **Evaluation isolation, per the upstream README:** only `repo/` goes into the agent
  image. `oracle/`, `buggy/`, `expected_changes.patch`, `metadata.json` (which lists
  hidden-test names) and the F2P/P2P tests are never visible to the agent.
- **Pinned environment:**
  - base image `python:3.11.18-slim-trixie` pinned by digest (`sha256:07d48240…`);
  - `git=1:2.47.3-0+deb13u1`;
  - pytest 8.3.5 and all its dependencies (iniconfig 2.0.0, packaging 24.2, pluggy 1.5.0)
    pinned and hash-locked in `requirements.txt`, installed with `--require-hashes --no-deps`;
  - apt configured with `APT::Install-Recommends "false"`, so CLI agents' own setup
    installs stay small (Claude Code's `curl nodejs npm procps`: 352 MB instead of 1.02 GB).

  `/workspace` is a git repo with the starting workspace committed, so agents can diff
  their changes.
- **Oracle:** `solve.sh` applies the upstream `expected_changes.patch` to `/workspace`.
- **Separate verifier:** `[verifier] environment_mode = "separate"` with its own image,
  `tests/Dockerfile`: the same pinned base image and hash-locked pytest, with
  `test.sh`, `test_f2p.py` and `test_p2p.py` baked in. After the agent phase only
  `/workspace` is collected as an artifact and restored into the verifier container, so
  changes outside `/workspace` (installed packages, reward files, shell state) cannot
  affect scoring. pytest runs with `python -I` and gets
  `/workspace` on its import path only through `-o pythonpath`, with conftest
  discovery confined to `/tests`. Planting `pytest.py`, `sitecustomize.py` or
  `conftest.py` in the workspace therefore cannot fake a pass. This was tested
  with an adversarial solution, which scored 0.
- **Verifier output:** runs the F2P and P2P suites with pytest/JUnit and writes
  `reward.json` and `reward.txt`:
  - `reward`: 1.0 iff every scoring test passes (task completion), else 0.0
  - `test_pass_rate`: passed tests / published test count (`f2p_test_count + p2p_test_count`)
  - `f2p_passed`, `p2p_passed`: per-suite passed counts

  Denominators use the published per-task counts, so import or collection errors count
  as failed tests rather than shrinking the denominator.
- **Standard agents:** no custom agent is needed; tasks run with any Harbor CLI agent.
  Parity uses Harbor's built-in `claude-code` agent, and the parity fork launches Claude
  Code the same way (see [Parity](#comparison-with-original-benchmark-parity)).
- **Filters and splits:** `--task-ids` (upstream id, slug, or full task name), `--stage`,
  `--limit`, and `--split parity` for the 49-task parity subset.

## Generated Task Structure

```
datasets/mlops-bench/
├── mlo-25-great-expectations-great-expectations-04-model-serving/
│   ├── task.toml                  # name, authors, stage/repo metadata, F2P/P2P counts
│   ├── instruction.md             # rendered problem.json specification
│   ├── environment/
│   │   ├── Dockerfile             # agent image: digest-pinned python:3.11 + git; copies repo/
│   │   ├── requirements.txt       # hash-locked pytest + deps
│   │   └── repo/                  # upstream starting workspace (mlops_bench_contracts/)
│   ├── solution/
│   │   ├── solve.sh               # applies expected_changes.patch
│   │   └── expected_changes.patch # upstream oracle patch
│   └── tests/
│       ├── Dockerfile             # separate verifier image (same pins; bakes in /tests)
│       ├── requirements.txt       # same hash-locked pytest + deps
│       ├── test.sh                # runs F2P + P2P, writes reward.json / reward.txt
│       ├── test_f2p.py            # upstream fail-to-pass tests
│       └── test_p2p.py            # upstream pass-to-pass tests
└── ...
```

Adapter code layout:

```
src/mlops-bench/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_mlops-bench.yaml           # oracle (default) and other agents, full dataset
├── run_mlops-bench_parity.yaml    # parity config: claude-code@2.1.326 on the parity subset
└── src/mlops_bench/
    ├── __init__.py
    ├── adapter.py                 # discovery, instruction rendering, parity subset, task generation
    ├── main.py                    # CLI entry point
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/
        │   ├── Dockerfile
        │   └── requirements.txt
        ├── solution/solve.sh
        └── tests/
            ├── Dockerfile
            └── test.sh
```

## Run Evaluation / Harness

### Running with the Datasets Registry

After the dataset is published:

```bash
# Oracle (reference solution)
harbor run -d oracle-samples/mlops-bench

# A specific agent and model
harbor run -d oracle-samples/mlops-bench -a <agent_name> -m "<model_name>"

# The parity subset, once published under the `parity` tag
harbor run -d oracle-samples/mlops-bench@parity -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

From the adapters repository root, after generating tasks locally (see
[Usage](#usage-create-task-directories)):

```bash
# Oracle verification (default agent in the config)
harbor run -c src/mlops-bench/run_mlops-bench.yaml

# Another agent/model
harbor run -c src/mlops-bench/run_mlops-bench.yaml -a <agent_name> -m "<model_name>"

# Or point directly at the generated dataset
harbor run -p datasets/mlops-bench -a <agent_name> -m "<model_name>"

# Parity configuration (claude-code@2.1.326 + claude-haiku-4-5 on the parity subset)
harbor run -c src/mlops-bench/run_mlops-bench_parity.yaml --job-name mlops-parity-run1
```

Results are saved under `jobs/` (set by `jobs_dir` in the YAML).

### Running Individual Trials

```bash
harbor trial start -p datasets/mlops-bench/<task_id> -a oracle
harbor trial start -p datasets/mlops-bench/<task_id> -a <agent_name> -m "<model_name>"
```

## Usage: Create Task Directories

```bash
cd src/mlops-bench
uv sync
uv run mlops-bench --output-dir ../../datasets/mlops-bench                    # all 212 tasks
uv run mlops-bench --split parity --output-dir ../../datasets/mlops-bench-parity  # 49-task parity subset
```

Flags:

- `--output-dir`: where to write tasks (default: `datasets/mlops-bench` at the repo root)
- `--limit N`: generate only the first N tasks (sorted by upstream path)
- `--overwrite`: replace existing task directories
- `--task-ids ID [ID ...]`: only these tasks (upstream `MLO-...` ids, generated slugs, or full task names)
- `--stage STAGE [STAGE ...]`: only these stages (e.g. `MODEL_SERVING DATA_PIPELINE`)
- `--split {full,parity}`: `full` (default) or the 49-task parity subset
- `--source-dir PATH`: use a local clone of `oracle-samples/mlops-bench` instead of cloning
- `--source-ref REF`: upstream ref to clone (default: the pinned commit)

## Comparison with Original Benchmark (Parity)

**Status: parity runs are pending the Harbor team's agreement on the plan below.** The
harness on both sides is built and smoke-tested.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| claude-code@2.1.326 | claude-haiku-4-5 | task completion rate | 3 (planned) | 49 (23.1%, planned) | pending | pending |

**Original side (Scenario 2).** MLOps-Bench has no runner or agent integration, so the
original side is a runner in a fork of the benchmark,
[`pixel3user/mlops-bench@harbor-parity`](https://github.com/pixel3user/mlops-bench/tree/harbor-parity)
(`harbor_parity/`; everything else is upstream at `8f48b68`, unchanged). It follows the
upstream README's evaluation protocol: copy `repo/` as the agent's workspace, prompt the
agent with the task specification, then score with
`PYTHONPATH=<workspace> python3 -m pytest -q tests/test_f2p.py tests/test_p2p.py`.
Held identical to the Harbor side:

- **Agent:** Claude Code 2.1.326, installed with the commands Harbor's `claude-code` agent
  runs, and launched with Harbor's command, flags and environment variables
  (`--output-format=stream-json --permission-mode=bypassPermissions --print`, prompt on
  stdin, Harbor's `set -o pipefail` prefix and config-directory setup).
- **Model and endpoint:** `claude-haiku-4-5` through the same Anthropic-compatible
  endpoint (`ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY`).
- **Prompt:** byte-identical to Harbor's `instruction.md` for all 212 tasks
  (`harbor_parity/check_prompts.py`).
- **Environment:** the adapter's digest-pinned image contents (git, hash-locked pytest,
  apt without recommends), `/workspace` committed as a git baseline, root user, 1 CPU,
  2048 MB, 1800 s agent timeout.
- **Metrics, per run:** task completion rate (share of tasks whose published F2P and P2P
  tests all pass) and test pass rate (passed scoring tests over published scoring
  tests, pooled across the run's tasks, as upstream defines "test pass"), counting
  each `test_*` function as upstream specifies.
- **Scoring invocation:** the original side runs upstream's plain command
  (`PYTHONPATH=<workspace> python3 -m pytest`); Harbor's verifier runs the same test
  files with the same counting, hardened against workspace tampering (`python -I`,
  `-o pythonpath`, conftest discovery limited to `/tests`). The two agree unless an
  agent tampers with grading.

**Planned subset.** The parity subset is 49 tasks: 7 per MLOps stage, drawn with
`random.Random(42)` from each stage's instance ids (25 of the 31 repositories appear).
The 212 tasks are 7 stage templates instantiated for 31 repositories, so every stage
template is covered; the full set would cost about $510 (3 runs per side at about $0.40
per Claude Code episode, measured) against about $120 for the subset.

**Smoke test (1 task, each side, 2026-11-26):** on
`MLO-01_GOOGLECLOUDPLATFORM__MLOPS_WITH_VERTEX_AI-01_DATA_PIPELINE`, both sides reported
identical Claude Code settings at start-up (model, `/workspace`, permission mode,
version, API-key source, the same 26 tools) and both scored reward 1.0 (7/7 tests;
original 25 turns, Harbor 37 turns).

Reproduction (both sides):

```bash
# Original side (parity fork)
git clone -b harbor-parity https://github.com/pixel3user/mlops-bench.git && cd mlops-bench
docker build -f harbor_parity/Dockerfile --target score -t mlops-bench-parity-score harbor_parity
docker build -f harbor_parity/Dockerfile --target agent --build-arg CLAUDE_CODE_VERSION=2.1.326 \
    -t mlops-bench-parity-agent:2.1.326 harbor_parity
export ANTHROPIC_API_KEY=... ANTHROPIC_BASE_URL=...
python3 harbor_parity/run_parity.py --run-name run1 --model claude-haiku-4-5 \
    --agent-image mlops-bench-parity-agent:2.1.326 \
    --task-ids-file harbor_parity/parity_subset.txt --n-concurrent 4

# Harbor side (adapters repo root)
cd src/mlops-bench && uv run mlops-bench --split parity --output-dir ../../datasets/mlops-bench-parity && cd ../..
export ANTHROPIC_API_KEY=... ANTHROPIC_BASE_URL=...
harbor run -c src/mlops-bench/run_mlops-bench_parity.yaml --job-name mlops-parity-run1
```

Oracle verification is reported under Notes & Caveats.

Links: [paper](https://arxiv.org/abs/2610.23506) · [original benchmark](https://github.com/oracle-samples/mlops-bench) · [parity fork](https://github.com/pixel3user/mlops-bench/tree/harbor-parity) · Adapter PR: [#154](https://github.com/harbor-framework/adapters/pull/154) · Dataset PR: pending · HF parity PR: pending

## Notes & Caveats

- **Oracle verification** (Harbor 0.26.0, Docker, pinned images, separate verifier): the
  `oracle` agent reaches reward 1.0 on all 212 tasks (0 exceptions; 636/636 F2P and
  856/856 P2P tests passing). The `nop` agent scores 0.0 task completion on every task,
  with all P2P tests passing and all F2P tests failing, as upstream intends.
- **No upstream runner or prompt.** The upstream repository says it "does not prescribe
  a single runner or agent integration," and the paper does not publish the prompt given
  to evaluated agents. Its Appendix C prompt is the oracle-generation prompt used during
  benchmark construction, not the agent prompt. This adapter renders `problem.json`
  verbatim (minus `metadata`) plus one line giving the workspace location, and the
  parity fork sends the identical prompt.
- **Starting workspace contains a disabled reference implementation.** In every task,
  `repo/` and `oracle/` differ by exactly three string literals (a mode switch from
  `'baseline'` to `'oracle'`). The full implementation is already in the starting file
  behind an always-true early return. The upstream maintainers raised this in
  [PR #6](https://github.com/oracle-samples/mlops-bench/pull/6) ("three-token template
  unlocks"), which was closed unmerged. The adapter keeps the released task content
  unchanged, so scores reflect the released benchmark as-is. In the smoke test, Claude
  Code on both sides found the guard, removed it and passed all tests.
- **Released tasks differ from the paper's examples.** The paper's Figure 3 shows tasks
  from repositories (e.g. `Chandru-21/MLOps_Project`) and multi-file, repo-native
  patches that are not in the public release. All released `repo/` workspaces contain
  only the `mlops_bench_contracts` module (every task is tagged
  `source_kind: hard_stage_contract`), and the 212 code files reduce to 7 stage
  templates once repository names and thresholds are removed. Paper results (e.g.
  Codex/GPT-5.5 at 31.2% task completion) were measured on that setup and are not
  directly comparable. The arXiv and ACL versions of the paper also report different
  headline numbers.
- **apt without recommends.** The task image sets `APT::Install-Recommends "false"`. It
  only affects packages that agents install for themselves at setup time (tasks never
  use apt), and the parity fork's image sets the same.
- **Time-dependent tests.** Tests build timestamps with `datetime.now(timezone.utc)`, so
  the container clock must be roughly correct.
- **Agent visibility of tests.** As upstream specifies, the agent sees only the
  specification and workspace. F2P/P2P tests are uploaded only at verification time.

## Installation / Prerequisites

- Docker installed and running
- Harbor CLI installed (`uv tool install harbor`)
- Python 3.12+ and `uv` for the adapter package:
  ```bash
  cd src/mlops-bench
  uv sync
  ```
- `git` and network access to clone the upstream repository (or pass `--source-dir`)
- API keys for the agent/model you run (exported as environment variables)

## Troubleshooting

- **`Unknown task id(s)`**: pass upstream ids like
  `MLO-25_GREAT_EXPECTATIONS__GREAT_EXPECTATIONS-04_MODEL_SERVING` or slugs like
  `mlo-25-great-expectations-great-expectations-04-model-serving`.
- **Oracle reward 0 on a task**: check `verifier/pytest_f2p.log` and
  `verifier/pytest_p2p.log` in the trial directory. `git apply` in `solve.sh` fails if
  the workspace was modified before the oracle ran.
- **Docker build slowness**: all tasks share the same base layers; the first build pulls
  the pinned `python:3.11.18-slim-trixie` image and installs pytest, and later builds are
  cached.
- **Disk usage with CLI agents**: each running trial holds its agent's own install
  (about 0.7 GB for Claude Code), so lower `n_concurrent_trials` on small disks.

## Citation

```bibtex
@inproceedings{tran-etal-2026-mlops-bench,
  title = {{MLOps}-{B}ench: Benchmarking {AI} Agents on Production {ML} Engineering in Real Repositories},
  author = {Tran, Quoc Co and Patel, Hitesh Laxmichand and Mahajan, Diwakar and Bakliwal, Kshitij and Sil, Avi and Kirchhoff, Katrin},
  booktitle = {Empirical Methods in Natural Language Processing EMNLP 2026, Findings},
  year = {2026},
  publisher = {Association for Computational Linguistics},
  url = {https://arxiv.org/abs/2610.23506},
  note = {To appear}
}
```

## Authors & Contributions

Original benchmark: Quoc Co Tran, Hitesh Laxmichand Patel, Diwakar Mahajan, Kshitij
Bakliwal, Avi Sil and Katrin Kirchhoff (Oracle). Harbor adapter: pixel3user ([adapter PR #154](https://github.com/harbor-framework/adapters/pull/154)).

**Issues and Contributions:**
- Submit issues and pull requests to [harbor-framework/adapters](https://github.com/harbor-framework/adapters)
- Benchmark content issues belong upstream at [oracle-samples/mlops-bench](https://github.com/oracle-samples/mlops-bench)

## Acknowledgement

Thanks to the MLOps-Bench authors for releasing the tasks, tests and oracle patches
under Apache-2.0.

API inference compute for parity experiments is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
