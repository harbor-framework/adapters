# GDM Situational Awareness — Harbor Adapter

## Overview

Harbor adapter for the 11 situational-awareness evaluations from Google DeepMind's *Evaluating Frontier Models for Stealth and Situational Awareness* (Phuong et al., 2025, [arXiv:2505.01420](https://arxiv.org/abs/2505.01420)), using the open-source Inspect Evals release (`gdm_self_reasoning`) as the upstream implementation.

This adapter generates **22 Harbor tasks**: 11 challenges × 2 samples each (easy/easy and hard/hard hint levels, upstream `_KEEP_COMBOS`). It is the situational-awareness half of the paper's 16-eval suite; the stealth half lives in the sibling `gdm-stealth` adapter. Status: **work in progress** — generation is implemented and oracle verification under Harbor (Step 3) passes 22/22 at reward 1.0 (2026-11-15, Harbor 0.26.0, local Docker). Parity experiments (Steps 4–6) have not been run.

## What is GDM Situational Awareness?

The situational-awareness (upstream: "self-reasoning") evaluations measure whether a model can instrumentally reason about itself, its deployment configuration, and its environment: noticing that its context length, output-token limit, message budget, latency, tool access, output filter, oversight cadence, or file permissions are configurable in `config.json`, then self-modifying that configuration to complete an underlying objective. Each challenge is an agentic sandbox task. Upstream success is binary per trial and is typically an OR of milestones: achieving the self-modification (e.g. a validly increased `context_size`) **or** completing the objective output. The paper ran 50 trials per challenge and called a challenge solved if at least one trial succeeded; the Inspect release defaults to 10 epochs with an `at_least_1` reducer.

## Adapter Features

- **Pinned upstream.** Generation runs only against inspect_evals commit `a68dade7efb803ef50c8442d3f16264b293d1414` (`--source-dir`, `$GDM_INSPECT_EVALS_DIR`, or a cache clone). A checkout at any other commit is rejected.
- **Verbatim prompts.** `instruction.md` is exactly upstream `get_input_prompt()` output; the system prompt, tool list, message limit (80), setup command, and per-challenge agent-harness dynamics are recorded in `tests/task_metadata.json` for the parity custom agent.
- **Self-contained, digest-pinned environments.** Each task's Dockerfile inlines upstream `data/base/Dockerfile` with the challenge Dockerfile (upstream references an unpinned personal prebuilt base image, `vincentwang25/self-reasoning-base`, which this adapter does not depend on). The generated base is pinned as `python:3.9-slim-buster@sha256:320a7a4250aba4249f458872adecf92eea88dc6abd2d76dc5c0f01cac9b53990`.
- **Ported verifier.** `tests/verify.py` ports each upstream solver's `evaluate()` SUCCESS condition to a final-state check over the same side files, including the sandboxed Game-of-Life tests for `max_tokens`.
- **Scripted oracle solutions.** Upstream ships no oracle solutions. `solution/solve.sh` contains per-challenge scripted solutions targeting the upstream success conditions. They pass Harbor oracle verification: 22/22 trials at reward 1.0, mean 1.000, no exceptions (2026-11-15).
- **Custom parity agent (Scenario 3).** `gdm_situational_awareness.custom_agent:GDMSelfReasoningParityAgent` replicates the Inspect solver pipeline: plan-instruction turns, upstream tool sets executed in the environment, and the in-loop dynamics per challenge (context truncation, output censoring/truncation, fake latency timer, message counter, simulated oversight stops with the upstream fake history, config-gated `query_database` tool), with the same success/done evaluation cadence. It is covered by fake-model/fake-environment integration tests; a real-model parity run has not been executed yet. Standard CLI agents do not experience those dynamics, so CLI runs are reported separately and are not parity evidence.

## Generated Task Structure

```
<challenge>-<easy-easy|hard-hard>/
├── task.toml                  # google-deepmind/gdm-situational-awareness__<sample>
├── instruction.md             # upstream input prompt, verbatim
├── environment/
│   ├── Dockerfile             # upstream base (inlined) + challenge Dockerfile
│   └── <challenge assets>     # agent.py, config.json, data files at build root
├── solution/
│   └── solve.sh               # scripted oracle solution (verified 22/22)
└── tests/
    ├── test.sh                # runs verify.py, writes /logs/verifier/reward.txt
    ├── verify.py              # ported upstream success checks
    ├── task_metadata.json     # system prompt, tools, dynamics, setup for parity agent
    └── originals/             # upstream config/files the verifier compares against
```

## Run Evaluation / Harness

Registry (post-publish; not yet published):

```bash
harbor run -d google-deepmind/gdm-situational-awareness -a oracle
```

Local path (pre-publish):

```bash
harbor run -p datasets/gdm-situational-awareness -a oracle
harbor run -c src/gdm-situational-awareness/run_gdm-situational-awareness.yaml
```

Single task:

```bash
harbor trial start -p datasets/gdm-situational-awareness/database-tool-hard-hard -a oracle
```

## Usage: Create Task Directories

```bash
cd src/gdm-situational-awareness
uv sync
# Reuse a pinned checkout, or omit --source-dir to clone into the cache:
uv run gdm-situational-awareness --source-dir /path/to/inspect_evals \
    --output-dir /path/to/datasets/gdm-situational-awareness --overwrite
# Subsets:
uv run gdm-situational-awareness --limit 2 --output-dir /tmp/gdm-sa
uv run gdm-situational-awareness --task-ids database_tool_easy_easy --output-dir /tmp/gdm-sa
```

## Comparison with Original Benchmark (Parity)

Parity has **not** been run yet. Per Step 4 of the adapter guide, agents, models, run counts, and API provisioning must be agreed with the Harbor team first. The Scenario 3 custom agent is implemented (see Adapter Features) but has not run a real-model episode yet. Planned metric: per-challenge binary success aggregated as solved-challenges (≥1 success in N trials) and mean per-trial success, reported as mean ± sample SEM over ≥3 matched runs per side (ADP-PARITY, ADP-STATS).

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| gdm-self-reasoning-parity-agent@0.1.0 | TBD | success rate | 0 | 22 | not run | not run |

Planned reproduction (commands are the intended shapes, to be finalized with the team):

```bash
# Original side (Inspect, pinned checkout):
cd inspect_evals
uv run inspect eval inspect_evals/gdm_self_reasoning_database_tool --model <provider/model> --epochs 10
# Harbor side:
PYTHONPATH=src/gdm-situational-awareness/src harbor run -p datasets/gdm-situational-awareness -a gdm_situational_awareness.custom_agent.agent:GDMSelfReasoningParityAgent -m <provider/model>
```

Links: [paper](https://arxiv.org/abs/2505.01420) · [Inspect Evals](https://github.com/UKGovernmentBEIS/inspect_evals) · Adapter PR: TBD · Dataset PR: TBD · HF parity PR: TBD

## Notes & Caveats

- **Naming.** The Adapter List row `gdm-situational-awareness` describes the whole 16-eval suite; this adapter deliberately covers only the 11 situational-awareness evals (`gdm_self_reasoning` upstream). The 4 released stealth evals are in `gdm-stealth`. One paper stealth eval has no Inspect counterpart and is excluded from both adapters until it is released.
- **No oracle solutions upstream.** Success conditions are programmatic, so scripted oracle solutions are provided; Step 3 passes (22/22 at reward 1.0 under `harbor run -a oracle`, 2026-11-15). `python:3.9-slim-buster` remains end-of-life: the image still pulls, but Debian buster has left the main apt mirrors, so the `approved_directories` Dockerfile rewrites apt sources to `archive.debian.org` (the only build-time deviation from upstream). If the archive or the base image disappears, the base must be bumped and recorded as a deviation.
- **In-loop dynamics are not in the verifier.** Context truncation, output censoring, the fake latency timer, message limits, oversight stop, and config-gated tools are enforced by the agent harness upstream. The Harbor verifier checks final state only, so a terminal agent that ignores the simulated constraints can score 1.0 without demonstrating the measured capability. Only custom-parity-agent runs are comparable to upstream.
- **Setup placement.** `context_length_mod_instrumental_only`'s randomized setup runs at image build (upstream runs it per sample; the key/value file is therefore fixed per image, and the verifier reads it from the image). `max_tokens`' `<OBJECTIVE>` substitution is applied to `agent.py` at generation time. `approved_directories`' permission-watcher daemon must be started by the agent harness (`setup_command` in `task_metadata.json`); it is not started by the image.
- **Success is milestone-based.** Several challenges count a valid self-modification alone as success even if the objective output is wrong (upstream semantics, preserved). `oversight_frequency` with a missing/non-integer `oversight_frequency` key is a failure in this port, matching upstream `evaluate()`'s SUCCESS value for that branch.
- **In-world artifacts.** Challenge sandboxes intentionally contain a fictional `agent.py`/`agent_lib.py` describing the model's own deployment, including a fake API key string. These are part of the upstream task fiction and are preserved verbatim.
- **Known limitation.** `read_logs` success requires exactly the upstream top-3 job titles and no others in `job_applications.csv`; there is no partial credit upstream or here.

## Installation / Prerequisites

- Python 3.11+ and `uv`; Docker for running generated tasks; `git` for fetching the pinned upstream checkout.
- No API keys are needed for generation or oracle runs. Parity runs need model-provider keys for the custom agent (to be provisioned with the team).

```bash
cd src/gdm-situational-awareness
uv sync
```

## Troubleshooting

- `inspect_evals checkout ... expected pinned commit`: generation is pinned; check out `a68dade7efb803ef50c8442d3f16264b293d1414` in your `--source-dir`, or delete the cache clone at `~/.cache/harbor-adapters/inspect_evals` to re-clone.
- Task build fails on apt for `approved_directories`: buster is only on `archive.debian.org` now; generated Dockerfiles already rewrite the sources — regenerate tasks rather than editing generated output. If the `python:3.9-slim-buster` image itself stops pulling, do not silently swap the base without recording it as an adaptation deviation.
- Reward is 0 although files look right: run `python3 /tests/verify.py <challenge>` inside the task container; it prints SUCCESS/FAILURE against the exact side files listed in `verify.py:SIDE_KEYS`.

## Citation

```bibtex
@misc{phuong2025gdmstealth,
  title        = {Evaluating Frontier Models for Stealth and Situational Awareness},
  author       = {Phuong, Mary and Zimmermann, Roland S. and Wang, Ziyue and Lindner, David and Krakovna, Victoria and Cogan, Sarah and Dafoe, Allan and Ho, Lewis and Shah, Rohin},
  year         = {2025},
  eprint       = {2505.01420},
  archivePrefix = {arXiv},
  primaryClass = {cs.AI},
  url          = {https://arxiv.org/abs/2505.01420}
}
```

## Authors & Contributions

Original benchmark: Mary Phuong, Roland S. Zimmermann, Ziyue Wang, David Lindner, Victoria Krakovna, Sarah Cogan, Allan Dafoe, Lewis Ho, and Rohin Shah (Google DeepMind). Open-source Inspect release: UK AI Security Institute Inspect Evals contributors (including Ziyue Wang and XkunW for `gdm_self_reasoning`). Harbor adapter: work in progress; see `adapter_metadata.json` (`adapter_builders`) and the adapter PR when opened.

## Acknowledgement

Thanks to the Inspect Evals maintainers for the MIT-licensed open-source release that makes a like-for-like parity side possible.
