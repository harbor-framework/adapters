# TraceTrial-Bench -> Harbor Adapter

## Overview

This adapter converts the standalone single-principal CLI split of **TraceTrial-Bench** (*Trial by Trace*, [arXiv:2610.32285](https://arxiv.org/abs/2610.32285)) into Harbor's task format (`tracelite-ai/tracetrial-bench`).

- **Benchmark domain**: Joint evaluation of AI coding agents and their execution harnesses across error propagation, stale-artifact gating, timeout channels, destructive-action guardrails, and latency/process containment.
- **Scoring**: Deterministic Python `verifier/score.py` verifiers copied directly from upstream `TraceTrial-Bench` (`4f94ae64a8`), computing a 50/50 macro-average (`0.5 * agent_rule_score + 0.5 * harness_rule_score`) in `[0.0, 1.0]`.
- **Adapted scope**: **14** standalone single-principal, single-turn CLI tasks (`--split standalone` / `--split parity`), with **14 / 14 (`1.000`)** Harbor Oracle pass rate and verified 3-run parity on `opencode@1.19.6` + `deepseek/deepseek-flash`.

## What is TraceTrial-Bench?

[TraceTrial-Bench](https://github.com/TraceLite-AI/TraceTrial-Bench) (*Trial by Trace: Joint Evaluation of Agents and Execution Harnesses*) is an open-source benchmark created by TraceLite AI that separates failures caused by the **model/agent policy** from failures caused by the **execution harness** (masked nonzero exit codes, unstructured timeout channels, unverified stale artifacts after failed commands, missing pre-delete confirmations, and leaked background child processes). Each task ships with an isolated workspace fixture and a deterministic rule-based `verifier/score.py` evaluator that grades both final workspace artifacts and normalized execution traces.

## Adapter Features

- **Pinned upstream provenance**: Resolves tasks from [`TraceLite-AI/TraceTrial-Bench@4f94ae64a8`](https://github.com/TraceLite-AI/TraceTrial-Bench/tree/4f94ae64a8e99ef8806200ffdcf496c9d7390f76) (via `--source-dir` or shallow clone pinned to `4f94ae64a8e99ef8806200ffdcf496c9d7390f76`).
- **Isolated separate verifier (`environment_mode = "separate"`)**: Grading runs in a network-disabled (`network_mode = "no-network"`) verifier container so reference verifiers, immutable baseline fixtures (`/tests/workspace`), and oracle hashes are never accessible to the agent container.
- **Zero-overlap trace & containment collection**: Uses `[[verifier.collect]]` (`/opt/tracetrial/collect_containment.py`) inside the agent container after agent completion to snapshot residual background processes (`process_containment.json`) and stage `/logs/agent/*` into `/logs/artifacts/trace_bundle/`, passing `harbor lint` with zero findings.
- **Faithful dual-mode trace bridge (`atif_bridge.py`)**: Preserves upstream `harness_tracer` OpenCode JSONL normalization 1:1 when native `opencode.txt` logs are present, and bridges Harbor ATIF v1.2+ `trajectory.json` steps for general ATIF-emitting Harbor agents (`claude-code`, `codex`, `goose`, `swe-agent`, and `oracle`).
- **Dynamic SHA-256-authenticated Oracles**: Includes 14 real shell oracle scripts (`oracles/*.sh`) that execute the actual workspace fixtures and emit verified trajectories (`14 / 14` tasks score `1.000`).

## Generated Task Structure

```
datasets/tracetrial-bench/
├── dataset.toml
├── README.md
└── <task-slug>/
    ├── task.toml                     # Separate no-network verifier + [[verifier.collect]] hook
    ├── instruction.md                # Upstream prompt.md verbatim
    ├── environment/
    │   ├── Dockerfile                # Agent container (Debian Bookworm + bash/jq/ripgrep + collect script)
    │   └── workspace/                # Task fixture mounted into /workspace
    ├── solution/
    │   └── solve.sh                  # Dynamic executable reference oracle
    └── tests/
        ├── Dockerfile                # Separate verifier image (Python 3.12 + upstream verifier)
        ├── test.sh                   # Entrypoint invoking verify_runner.py -> /logs/verifier/reward.txt
        ├── verify_runner.py          # Stages run layout, executes verifier/score.py, writes reward.txt
        ├── atif_bridge.py            # OpenCode JSONL + Harbor ATIF -> TraceTrial event/probe normalizer
        ├── task_id.txt               # Canonical upstream task ID
        ├── oracle_sha256.txt         # SHA-256 of solve.sh for oracle trajectory authentication
        ├── workspace/                # Read-only baseline workspace copy for manifest diffing (e.g. G1-001)
        └── verifier/                 # Unmodified upstream Task/<id>/verifier/* scripts
```

## Run Evaluation / Harness

Harbor Registry Datasets makes running benchmark evaluation easy and flexible.

### Running with Datasets Registry

Simply run:

```bash
# Use oracle agent (reference solution — 14/14 = 1.000)
uv run harbor run -d tracelite-ai/tracetrial-bench -a oracle -n 7

# Use your specified agent and model
uv run harbor run -d tracelite-ai/tracetrial-bench -a opencode --ak version=1.19.6 -m deepseek/deepseek-flash -n 7
```

### Using Job Configurations or Local Task Directories

If you prepared task directories locally via the adapter CLI:

```bash
# Run from the reference YAML config
uv run harbor run -c src/tracetrial-bench/run_tracetrial-bench.yaml

# Or run directly against a local dataset path
uv run harbor run -p datasets/tracetrial-bench -a oracle -n 7
```

## Usage: Create Task Directories

```bash
cd src/tracetrial-bench

# Generate the default 14-task standalone split (clones pinned upstream commit automatically)
uv run tracetrial-bench --output-dir ../../datasets/tracetrial-bench --overwrite

# Or generate from an existing local TraceTrial-Bench checkout
uv run tracetrial-bench --source-dir /path/to/TraceTrial-Bench --split standalone --output-dir ../../datasets/tracetrial-bench --overwrite

# Generate specific task IDs or limit count
uv run tracetrial-bench --task-ids E8-exit-code-masked-by-output-001,G1-registry-cleanup-002 --output-dir /tmp/tt-subset --overwrite
```

Supported CLI flags: `--output-dir`, `--limit`, `--overwrite`, `--task-ids`, `--split` (`standalone`, `parity`, `single-turn`, `all`), and `--source-dir`.

## Comparison with Original Benchmark (Parity)

Parity was evaluated across **3 independent runs per side** (`3 × 14 = 42` trials on Original `TraceTrial-Bench` and `3 × 14 = 42` trials on Harbor `0.26.0`) using the identical agent (`opencode@1.19.6`), model (`deepseek/deepseek-flash`), prompt text, workspace fixtures, and deterministic `verifier/score.py` scoring rules:

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Performance | Harbor Performance |
|-------|-------|--------|----------------|--------------|----------------------|--------------------|
| `opencode@1.19.6` | `deepseek/deepseek-flash` | `rule_overall_score` (%) | 3 | 14 (100% of standalone) | `66.90 ± 0.5944` | `68.40 ± 0.9545` |
| `opencode@1.19.6` | `deepseek/deepseek-flash` | `agent_rule_score` (%) | 3 | 14 (100% of standalone) | `80.87 ± 0.7467` | `83.86 ± 1.8349` |
| `opencode@1.19.6` | `deepseek/deepseek-flash` | `harness_rule_score` (%) | 3 | 14 (100% of standalone) | `52.92 ± 0.4657` | `52.94 ± 0.2381` |

- **Original Benchmark Repository**: <https://github.com/TraceLite-AI/TraceTrial-Bench> (pinned commit [`4f94ae64a8`](https://github.com/TraceLite-AI/TraceTrial-Bench/tree/4f94ae64a8e99ef8806200ffdcf496c9d7390f76))
- **Harbor Adapter PR**: <https://github.com/harbor-framework/adapters/pull/121>
- **Harbor Dataset PR**: <https://github.com/harbor-framework/harbor-datasets/pull/286>
- **Hugging Face Parity PR**: <https://huggingface.co/datasets/harborframework/parity-experiments/discussions/288> (mirrored at <https://huggingface.co/datasets/TraceLite-AI/tracetrial-bench-harbor-parity> while the shared Hub repo is over the 1M-file cap)

### Reproduction Commands

```bash
# 1. Harbor side (Oracle 14/14 = 1.000, then 3 parity runs)
cd src/tracetrial-bench
uv run tracetrial-bench --output-dir /tmp/harbor_standalone_14 --overwrite
harbor run -p /tmp/harbor_standalone_14 -a oracle -n 7

for trial in 1 2 3; do
  harbor run -p /tmp/harbor_standalone_14 \
    -a opencode --ak version=1.19.6 \
    --ae OPENCODE_DISABLE_AUTOUPDATE=1 \
    --ae OPENCODE_DISABLE_MODELS_FETCH=1 \
    --ae OPENCODE_FAKE_VCS=git \
    -m deepseek/deepseek-flash \
    --api-key-name OPENAI_API_KEY \
    --api-format openai_chat_completions \
    -n 7 -o "/tmp/harbor_parity/trial_${trial}"
done

# 2. Original TraceTrial-Bench side (pinned commit 4f94ae64a8)
git clone https://github.com/TraceLite-AI/TraceTrial-Bench.git /tmp/TraceTrial-Bench
git -C /tmp/TraceTrial-Bench checkout 4f94ae64a8e99ef8806200ffdcf496c9d7390f76
for trial in 1 2 3; do
  PYTHONPATH=/tmp/TraceTrial-Bench python -m tracetrial_bench.cli run \
    --harness opencode \
    --docker-image opencode=harnessbench/opencode:1.19.6-bookworm \
    --model deepseek --mode docker --evaluation-mode run-only \
    --model-registry /path/to/model.toml --concurrency 7 \
    --output-dir "/tmp/original_parity/trial_${trial}" \
    --task /tmp/TraceTrial-Bench/Task/E3-restore-latency-004 \
    --task /tmp/TraceTrial-Bench/Task/E6-reindex-timeout-channel-001 \
    --task /tmp/TraceTrial-Bench/Task/E6-suite-timeout-channel-002 \
    --task /tmp/TraceTrial-Bench/Task/E6-timeout-error-channel-003 \
    --task /tmp/TraceTrial-Bench/Task/E7-build-stale-artifact-001 \
    --task /tmp/TraceTrial-Bench/Task/E7-failed-command-stale-artifact-002 \
    --task /tmp/TraceTrial-Bench/Task/E7-snapshot-stale-artifact-003 \
    --task /tmp/TraceTrial-Bench/Task/E8-exit-code-masked-by-output-001 \
    --task /tmp/TraceTrial-Bench/Task/E8-lintgate-exit-masked-002 \
    --task /tmp/TraceTrial-Bench/Task/E8-mountcheck-exit-masked-003 \
    --task /tmp/TraceTrial-Bench/Task/G1-buildcache-cleanup-001 \
    --task /tmp/TraceTrial-Bench/Task/G1-registry-cleanup-002 \
    --task /tmp/TraceTrial-Bench/Task/L2-deploy-latency-001 \
    --task /tmp/TraceTrial-Bench/Task/L2-writeoff-latency-002
done
```

## Notes & Caveats

- **Scope & Excluded Upstream Tasks (82 of 96)**: The upstream `TraceTrial-Bench` repository contains 96 task directories (94 core tasks + 2 calibration controls). The Harbor `standalone` (and `parity`) split adapts the **14 standalone single-principal, single-turn CLI tasks** that run self-contained inside a single agent container. The remaining 82 tasks are intentionally excluded from the default Harbor registry split because they require host-side Unix domain socket `simulator/` daemons, multi-turn `turns.json` simulated-user loops, custom prebuilt MCP runtime images, or multi-principal child-subagent session trees (`L4`/`L5`) not represented in single-session ATIF trajectories.
- **Deterministic Rule Verifiers Only**: Upstream `TraceTrial-Bench` supports an optional secondary LLM judge (`full` mode) in addition to deterministic `verifier/score.py` rule evaluation. Both sides of this Harbor adaptation and parity study evaluate exclusively with the deterministic `verifier/score.py` rule verifiers (`0.5 * agent_rule_score + 0.5 * harness_rule_score`), avoiding judge variance and judge API cost.
- **Upstream `run_started` Lifecycle Parity**: At pinned commit `4f94ae64a8`, `TraceTrial-Bench/harness_tracer/runner.py` emits an outer `run_started` event before `OpenCodeAdapter.consume()` emits its session `run_started` event (`lifecycle=2/1`), and OpenCode `1.19.6` does not emit `providerExecuted` booleans on tool calls. `atif_bridge.py` (`build_trace_and_probe_from_opencode_jsonl`) preserves both behaviors 1:1 rather than synthesizing fields absent from OpenCode's stream.
- **OpenCode `1.19.6` Shutdown `NonZeroAgentExitCodeError`**: Under headless `opencode run --format json`, `opencode-ai@1.19.6` (Bun runtime) frequently exits with code `1` on stdout pipe teardown *after* emitting its final `step_finish` (`reason: "stop"`). Harbor records `NonZeroAgentExitCodeError` with `should_grade: true` and `has_valid_reward: true`, so all completed trajectories and workspaces are graded normally.

## Installation / Prerequisites

- **Docker**: Required for running Harbor agent and separate verifier containers.
- **Python 3.11+ & `uv`**: Required to run Harbor (`harbor>=0.26.0`) and the adapter CLI (`uv run tracetrial-bench`).
- **API Credentials**: Set the provider API key matching your chosen model (for example `OPENAI_API_KEY` or `DEEPSEEK_API_KEY` for `deepseek/deepseek-flash`, or `ANTHROPIC_API_KEY` for Claude models).

## Troubleshooting

- **`harbor lint` `artifact-log-overlap` error if `/logs/agent` is added to `artifacts`**: Do not add `/logs/agent` directly to `task.toml` `artifacts`. The template's `[[verifier.collect]]` hook (`collect_containment.py`) stages agent logs into `/logs/artifacts/trace_bundle/` automatically after agent execution.
- **`Permission denied` on custom agent binaries when running Original `TraceTrial-Bench`**: Upstream `TraceTrial-Bench` runs containers as UID `1000:1000`; ensure Node/OpenCode binaries are installed under world-executable `/usr/local/bin` rather than `/root/.nvm`.
- **Verifier timeout on slow networks**: Image builds install lightweight Bookworm/Slim utilities only; if Docker Hub pulls are slow, pre-pull `debian:bookworm-slim` and `python:3.12-slim` or pass `--force-build false` after the first build.

## Citation

```bibtex
@article{tracetrialbench2026,
  title={Trial by Trace: Joint Evaluation of AI Coding Agents and Execution Harnesses},
  author={TraceLite AI},
  journal={arXiv preprint arXiv:2610.32285},
  year={2026},
  url={https://arxiv.org/abs/2610.32285}
}
```

## Authors & Contributions

This adapter is developed and maintained by **TraceLite AI** (`290594480+zsicheng0214@users.noreply.github.com`), authors of the upstream [TraceTrial-Bench](https://github.com/TraceLite-AI/TraceTrial-Bench) benchmark, with review guidance from the Harbor team (`@Slimshilin`, `@audreina17`).

**Issues and feedback**:
- Harbor adapter issues: <https://github.com/harbor-framework/adapters/issues>
- Upstream benchmark issues: <https://github.com/TraceLite-AI/TraceTrial-Bench/issues>
