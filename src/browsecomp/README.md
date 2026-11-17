# BrowseComp → Harbor Adapter

## Overview

This adapter converts OpenAI **BrowseComp** into Harbor tasks: 1,266 questions requiring web search, source retrieval, and a short factual answer. It migrates the contribution from [Harbor PR #1521](https://github.com/harbor-framework/harbor/pull/1521) into the standalone [Harbor Adapters repository](https://github.com/harbor-framework/adapters) in [migration PR #62](https://github.com/harbor-framework/adapters/pull/62).

The migration preserves the historical three-run comparison on 30 tasks and a separate full-dataset oracle check. It adds no new model, cloud, or benchmark runs. Dataset publication and acceptance of the historical parity methodology remain pending.

## What is BrowseComp?

[BrowseComp](https://openai.com/index/browsecomp/) is OpenAI's benchmark for difficult browsing questions whose answers are short and verifiable. Its reference implementation is in [OpenAI simple-evals](https://github.com/openai/simple-evals/blob/main/browsecomp_eval.py). The adapter downloads the encrypted `browse_comp_test_set.csv` from the official simple-evals data endpoint and decrypts each question and answer using its canary field.

The adapted split contains all 1,266 BrowseComp test questions. **BrowseComp-Plus is outside this adapter's scope.** Refer to the original code license and dataset terms before redistributing benchmark material.

## Adapter Features

- Generates stable task IDs `browsecomp_001` through `browsecomp_1266`.
- Supports `--output-dir`, `--limit`, `--overwrite`, `--task-ids`, `--csv-path`, and `--split {test,parity}`. The parity split selects the historical first 30 questions.
- Uses Harbor's installed Claude Code agent for the recorded model comparison. No custom agent implementation is included in this package.
- Requires the agent to write its answer to `/app/answer.txt`; the verifier writes binary reward to `/logs/verifier/reward.txt`.
- Grades by normalized exact match first, then an LLM judge when credentials are available. Without usable judge credentials, a nonmatching answer receives zero. This grading flow is not fully deterministic.
- Provides a reference solution that writes the known answer, for structural and verifier checks.

Package files live under `src/browsecomp/`, with Python code and task templates under `src/browsecomp/src/browsecomp/`. Harbor is installed separately.

## Generated Task Structure

```text
datasets/browsecomp/
└── browsecomp_001/
    ├── task.toml
    ├── instruction.md
    ├── environment/
    │   ├── Dockerfile
    │   ├── docker-compose.yaml
    │   └── tests/
    │       ├── test.sh
    │       └── test_outputs.py
    ├── solution/
    │   └── solve.sh
    └── tests/
        ├── test.sh
        └── test_outputs.py
```

The question and output instructions are agent-facing. Expected answers are stored in verifier and oracle material. Base64 encoding of reference answers is an encoding convention, not a security boundary.

## Run Evaluation / Harness

### Dataset registry

[Dataset PR #226](https://github.com/harbor-framework/harbor-datasets/pull/226) remains open as of October 28, 2026. No registry dataset ID is claimed by this migration. After the Harbor team publishes the dataset, use the actual published ID:

```bash
harbor run --dataset <published-org>/<published-dataset> \
  --agent <agent-name> --model <model-id>
```

### Local tasks and configurations

These are reference commands for users running an evaluation; they were not executed as benchmark experiments for this migration. Run from the adapters repository root after generating tasks:

```bash
# Default configuration: oracle with local Docker
harbor run --config src/browsecomp/run_browsecomp.yaml

# Agent evaluation against locally generated tasks
harbor run --path datasets/browsecomp \
  --agent <agent-name> --model <model-id>

# Individual structural check
harbor trial start --path datasets/browsecomp/browsecomp_001 --agent oracle
```

Job outputs default to `jobs/`; individual trial outputs default to `trials/`. The separate 30-task configuration is described in the parity section.

## Usage: Create Task Directories

From the adapters repository root:

```bash
cd src/browsecomp
uv sync

# Full test split
uv run browsecomp --output-dir ../../datasets/browsecomp

# Fixed historical parity subset, in a separate directory
uv run browsecomp --split parity --output-dir ../../datasets/browsecomp-parity

# Selected stable IDs using an existing CSV
uv run browsecomp --csv-path /path/to/browse_comp_test_set.csv \
  --task-ids browsecomp_001,browsecomp_010 --output-dir /path/to/tasks
```

The default split is `test` and the default output/cache location is `datasets/browsecomp/` at the adapters repository root. `--limit` restricts selected tasks; `--task-ids` intersects with the chosen split. `--overwrite` replaces existing selected task directories. Without `--csv-path`, the adapter downloads the official CSV if no cached copy exists.

## Comparison with Original Benchmark (Parity)

### Historical results

These results are carried over from the April 2026 submission. They cover the **first 30 questions**, corresponding to original indices 0–29 and Harbor IDs `browsecomp_001`–`browsecomp_030` (30/1,266, approximately 2.37%). This is a fixed prefix, not a random sample or a full-dataset model evaluation. `parity_experiment.json` preserves the original date and run arrays.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original (mean ± sample SEM) | Harbor (mean ± sample SEM) |
| --- | --- | --- | --- | --- | --- | --- |
| `claude-code@2.1.79` | `claude-haiku-4-5-20251001` | Accuracy (%) | 3 per side | 30 | 24.4 ± 2.2 | 22.2 ± 1.1 |

Original run scores are `[26.67, 20.0, 26.67]`; Harbor scores are `[23.33, 23.33, 20.0]`, in percentage points. These ranges overlap, satisfying the guide's numerical overlap criterion. **Overlap alone does not resolve protocol differences or establish acceptance of matched parity.**

| Historical Harbor run | Correct / scheduled | Trials with rewards | Recorded errors |
| --- | --- | --- | --- |
| v39, Try 1 | 7/30 | 27 | 10 agent timeouts, 3 runtime errors |
| v41, Try 2 | 7/30 | 30 | 7 agent timeouts |
| v44, Try 3 | 6/30 | 28 | 4 agent timeouts, 2 Daytona errors |

Reported Harbor accuracy uses all 30 scheduled tasks as its denominator. Some timeout trials still have verifier rewards. The second run archive includes 37 trial directories after retries; its root result selects the reported set of 30. These error-bearing records are retained as historical evidence rather than presented as clean repeated runs.

Harbor trajectories identify Claude Code 2.1.79 and the dated Haiku model. Original run arguments identify `claude_code`, a Haiku alias, temperature 0.0, and **gpt-5-mini as judge**; surviving run-three response metadata identifies the dated Haiku solver. Historical Harbor configurations select **claude-haiku-4-5 as judge**, a 600-second solver timeout, and 100 turns on Daytona. Original installation/version, prompts, tools, limits, effective judge routing, and retry policies cannot all be reconstructed from the linked sources. The table retains the historical agent label; it does not certify identical installations on both sides.

### Separate oracle evidence

The archived April 6, 2026 oracle job records **1,266 trials, zero errors, mean reward 1.0**. Its directory is named `oracle_1266_all_tasks_3 passed`; this is one archived job, not evidence of three full oracle repeats. The reference solution writes the known answer, so this checks task/verifier structure rather than model browsing performance. The result predates subsequent adapter revisions and is not a fresh validation of the migrated package.

### Review context and artifact links

- [Original benchmark implementation](https://github.com/openai/simple-evals/blob/main/browsecomp_eval.py).
- [Historical original-side fork](https://github.com/wizard1203/browsecomp-adapter/tree/ee3b0318d8d1d9d72755a4120879be65f7c07e9e): custom runner missing, as described below.
- [Historical Harbor adapter PR #1521](https://github.com/harbor-framework/harbor/pull/1521).
- [Standalone migration PR #62](https://github.com/harbor-framework/adapters/pull/62).
- [Dataset PR #226](https://github.com/harbor-framework/harbor-datasets/pull/226): open, publication pending as of October 28, 2026.
- [HF parity PR #244](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/244): public **draft**, unmerged as of October 28, 2026. It retains result summaries, Harbor artifacts, a separate oracle archive, and incomplete original-side artifacts. Treat raw archived configurations as sensitive; do not reuse credentials from historical logs.
- Related contributions: [Adapters PR #44](https://github.com/harbor-framework/adapters/pull/44) and its [historical Harbor PR #2355](https://github.com/harbor-framework/harbor/pull/2355). This submission independently migrates #1521; these cross-links preserve overlapping review context without claiming the other contribution's implementation or evidence.

### Historical original-side invocation: source unavailable

The former README recorded the following invocation. It is retained for provenance and **cannot currently be reproduced from the linked public fork**: its inspected main commit `ee3b0318d8d1d9d72755a4120879be65f7c07e9e` contains neither `run_browsecomp.py` nor the required Dockerfile/custom Claude Code runner.

```text
# Historical reference only; requires the missing runner and Dockerfile.
docker build -t browsecomp-adapter:test .
docker run --rm -v "$(pwd):/workspace" -w /workspace \
  -e ANTHROPIC_API_KEY -e ANTHROPIC_BASE_URL \
  -e OPENAI_API_KEY -e OPENAI_BASE_URL -e BROWSECOMP_CLAUDE_HAIKU_MODEL \
  browsecomp-adapter:test bash -lc \
  "python run_browsecomp.py --mode run-all --model claude-haiku-4-5 --grader-model gpt-5-mini --examples 30 --greedy --output-root ./output/exp_dual_30tasks"
# Other recorded output roots: exp_dual_30tasks_2nd, exp_dual_30tasks_3rd.
```

The draft archive retains three sets of arguments, per-index grading results, and experiment summaries, plus run-three `samples.before_dedup.jsonl` containing 53 records for 30 distinct indices. Canonical `samples.jsonl` and per-task original traces are absent from its current tree. Missing source, canonical samples, and duplicate-selection provenance remain reproducibility gaps.

### Harbor-side reference commands

The migrated configuration retains the historical subset and agent settings while spelling out the dated model identifier and using the new source layout. It is a reference configuration, not a byte-identical copy of every archived run configuration.

```bash
cd src/browsecomp
uv run browsecomp --output-dir ../../datasets/browsecomp
cd ../..

# Reference only; this migration does not launch a new parity run.
harbor run --config src/browsecomp/run_browsecomp_parity.yaml \
  --job-name browsecomp-parity-reference
```

This migration carries forward existing evidence for maintainer review. It schedules no additional experiments and makes no claim that unresolved methodology has been accepted.

## Notes & Caveats

- **Scope and coordination:** all 1,266 original BrowseComp tasks are convertible; no Plus corpus or retrieval environment is included. Maintainers can compare this migrated #1521 contribution with #44/#2355 using the linked history. Migration does not settle which overlapping implementation should be accepted.
- **Prompts and grading:** the adapter adds answer-file and web-tool instructions. Symmetric prompts/tools cannot be verified without the original runner. The verifier uses exact-match-first grading and its own concise yes/no judge prompt; these differences from the original evaluator remain relevant to parity review.
- **Judge configuration:** `JUDGE_MODEL` selects the judge. The verifier prefers `OPENAI_API_KEY` plus `OPENAI_BASE_URL` when both exist, otherwise Anthropic credentials plus `ANTHROPIC_BASE_URL`. Effective backend selection thus depends on the environment as well as the model label. Missing credentials cause strict matching; exhausted API retries or an unparsable response produce zero reward.
- **Historical provenance:** archived Harbor jobs used `datasets/browsecomp/BrowseComp`; the current generator uses `datasets/browsecomp`. The cached official CSV inspected during migration has SHA-256 `7b24471cd5b3eb2a46830a14802b5c029ea62f488ff75a0f88af7923d1454abf`; historic experiment files do not record a CSV digest or a complete source/runtime manifest.
- **Artifact handling:** this repository imports adapter source and structured summaries. It does not copy raw logs, sessions, benchmark answers, or credential-bearing configurations. Historical artifacts require sanitization before reuse or redistribution; public draft availability does not establish that raw artifacts are safe to republish.
- **Cost and validation:** historical API/cloud costs are unknown. No new paid inference, cloud job, or benchmark experiment is part of this migration. Offline package checks do not replace runtime validation or matched-model parity review.
- **Offline migration checks:** eight focused unit tests passed, along with Ruff and type checks. Three synthetic tasks produced 27 files byte-identical to the previous generator; all six inherited template assets remained unchanged. The built wheel includes the packaged instruction template, and its installed CLI generated a complete synthetic task without model or cloud access. These checks establish packaging and transformation behavior, not benchmark performance.
- **Upstream maintenance:** simple-evals announced in July 2025 that it would stop updating model results; its BrowseComp reference remains useful, but source/runtime pins matter for reproducibility.

## Installation / Prerequisites

Use Python 3.12+ and `uv`. Install Harbor as an external CLI and this adapter independently:

```bash
uv tool install harbor
cd src/browsecomp
uv sync
uv run browsecomp --help
```

Task generation requires the official CSV or a local copy. Evaluations require Docker or the configured environment provider and internet access. Model and non-exact judge calls additionally require independently obtained API credentials. Record the actual Harbor revision/version for any evaluation.

## Troubleshooting

- **Tasks not found:** generate tasks first and launch reference YAMLs from the adapters repository root. Historical archives use an older nested dataset path.
- **Strict matching fallback:** check which credential/base-URL pair is visible to the verifier. OpenAI-compatible judge URLs should point at the API prefix, typically ending in `/v1`; Anthropic handling accepts the host or its `/v1` prefix.
- **Invalid Claude model or missing credentials:** check the dated solver model and runtime agent environment. Historical gateway aliases may resolve differently today.
- **Daytona errors or timeouts:** retain infrastructure status separately from rewards. A changed denominator would describe a different result from the historical scores.
- **Original reproduction command fails:** the linked fork lacks the custom runner/Dockerfile. The recorded invocation is provenance, not a working installation procedure.

## Citation

```bibtex
@misc{openai_browsecomp_2025,
  title = {BrowseComp: a benchmark for browsing agents},
  author = {OpenAI},
  year = {2025},
  url = {https://openai.com/index/browsecomp/}
}
```

## Authors & Contributions

Adapter contribution: [Zhenheng Tang](mailto:coolzhtang@gmail.com), preserved from [Harbor PR #1521](https://github.com/harbor-framework/harbor/pull/1521).

Original BrowseComp authors: Jason Wei, Zhiqing Sun, Spencer Papay, Scott McKinney, Jeffrey Han, Isa Fulford, Hyung Won Chung, Alex Tachard Passos, William Fedus, and Mia Glaese.

Submit adapter issues and pull requests to [harbor-framework/adapters](https://github.com/harbor-framework/adapters). Cross-link related work when coordinating review.

API inference compute for the historical parity tests was generously supported by [2077AI](https://www.2077ai.com/).
