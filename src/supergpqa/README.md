# SuperGPQA → Harbor Adapter

## Overview

Converts all **26,529** unique rows of the pinned upstream `SuperGPQA-all.jsonl`
into one Harbor task per question, with no exclusions. The bank spans 13 broad
disciplines, 72 fields and 285 subfields; questions have 4–10 options.
This initial adapter supports **zero-shot only**. Five-shot and robustness
experiments are not silently mixed into this release.

Source: https://github.com/SuperGPQA/SuperGPQA at
`e31e8bf3e7089aef808be5ddecafd4538dee6e41`.
Dataset checksum and source hashes are recorded in `source_pins.json`.
The source bank is ODC-BY with upstream third-party-content notices; see
`UPSTREAM_NOTICE.md` and the included upstream license.

## What is SuperGPQA?

SuperGPQA tests graduate-level knowledge and reasoning via multiple-choice
questions. Original reporting includes sample-wise accuracy, macro accuracy
over subfields/fields/disciplines, and accuracy by difficulty.
Paper: https://arxiv.org/abs/2502.14739.
This is distinct from GPQA Diamond; it is not a software-engineering benchmark.

## Adapter Features

- Stable UUID-based task names under the proposed `m-a-p` namespace.
- Pinned data download with SHA-256 verification, or offline `--data-path`.
- Unchanged source option ordering and official zero-shot prompt.
- Verbatim upstream parser functions, including five-second regex timeout.
- Gold labels and oracle scripts excluded from the agent Docker build context.
- Separate verifier image bundles grading code and gold records; only the declared
  `/app/answer.txt` artifact crosses from the agent sandbox into verification.
- Explicit overwrite, task filtering, limit and deterministic parity-subset utility.
- Binary per-task reward; original macro and difficulty aggregation available
  in `supergpqa.scoring.aggregate`, not replaced by a generic task mean.

## Generated Task Structure

```text
supergpqa/
├── generation_manifest.json
└── supergpqa-<uuid>/
    ├── task.toml
    ├── instruction.md
    ├── environment/Dockerfile
    ├── solution/solve.sh
    └── tests/
        ├── Dockerfile
        ├── test.sh
        ├── grade.py
        ├── record.json
        ├── scoring.py
        └── upstream_parser.py
```

Adapter code uses `src/supergpqa/{adapter,main,scoring}.py`, an unchanged
`upstream_parser.py`, the upstream `zero-shot.yaml`, and `task-template/`.
`main.py` calls `SuperGPQAAdapter.run()`.

## Run Evaluation / Harness

### Running with Datasets Registry

Not published. Do not assume `m-a-p/supergpqa` resolves yet. After the team
approves namespace, publishes the bank and assigns the requested `v1.0` tag:

```bash
harbor run -d m-a-p/supergpqa@v1.0 -a oracle
```

### Using Job Configurations

Before publishing, generate the local dataset, then from the adapters repository root:

```bash
harbor run -c src/supergpqa/run_supergpqa.yaml
# Equivalent full-bank oracle command:
harbor run -p datasets/supergpqa -a oracle
```

Default configuration uses oracle and Docker, one attempt, four-way concurrency.
Docker must be installed and its daemon running. The direct-agent parity setup and results are documented below.

### Running Individual Trial

```bash
harbor trial start -p datasets/supergpqa/supergpqa-<uuid> -a oracle
```

Harbor saves logs under `jobs/` / `trials/`. Inspect verifier errors separately
from incorrect answers. A missing answer earns zero; grader exceptions leave no
reward file and must be investigated as infrastructure/scoring errors.

## Usage: Create Task Directories

Canonical package entry point:

```bash
cd src/supergpqa
uv run supergpqa --output-dir ../../datasets/supergpqa
```

Alternatively, from the adapters repository root:

```bash
# From adapters repository root. Adapter is a standalone uv project.
uv run --project src/supergpqa python -m supergpqa.main \
  --output-dir datasets/supergpqa

# Use a pinned local source file; no dataset network access:
uv run --project src/supergpqa python -m supergpqa.main \
  --data-path /path/to/SuperGPQA/data/SuperGPQA-all.jsonl \
  --output-dir datasets/supergpqa

# Small developer smoke bank, using a separate directory:
uv run --project src/supergpqa python -m supergpqa.main \
  --output-dir datasets/supergpqa-smoke --limit 10
```

Flags: `--output-dir`, `--data-path`, `--cache-dir`, `--limit`, `--overwrite`,
`--task-ids UUID [UUID ...]`, `--split full|parity`, `--parity-size`, `--seed`.
Default output is `datasets/supergpqa` relative to the working directory; run
from the adapters repository root. Existing tasks require explicit `--overwrite`; directories
containing unselected tasks are rejected to prevent accidental subset contamination.

`--split parity --parity-size N --seed 42` selects proportionally across
full taxonomy × difficulty using largest-remainder quotas and SHA-256 rankings.
Small subsets cannot represent every stratum. This is a selection utility only;
the team must agree on sampling and size before model experiments.

## Comparison with Original Benchmark (Parity)

**Completed on 2026-11-21:** 100 fixed questions (0.3769% of 26,529), seed 42,
three passes per side, 600/600 formal results with exact UUID coverage.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| supergpqa-direct@0.1.0 | gpt-6-luna-2026-09-22 (returned ID) | Sample accuracy (%) | 3 | 100 | 45.3333 ± 0.8819 | 44.6667 ± 0.6667 |

Raw runs are original **[44, 45, 47]%** and Harbor **[46, 44, 44]%**. The ranges
44–47% and 44–46% overlap, satisfying the guide's primary range-overlap criterion.
Uncertainty is sample SEM across run scores. All four aggregate accuracy metrics
and all three difficulty metrics are reported in `parity_experiment.json`.

See [the full analysis](PARITY_REPORT.md), [the evidence release](https://github.com/jialen2/adapters/releases/tag/supergpqa-parity-2026-11-21), and
[the complete download](https://github.com/jialen2/adapters/releases/download/supergpqa-parity-2026-11-21/SuperGPQA-parity-evidence-2026-11-21.tar.gz). [HF evidence PR #293](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/293) tracks the archive upload. [Dataset registration PR #291](https://github.com/harbor-framework/harbor-datasets/pull/291) is submitted; registry publication remains pending. [The original-side implementation](https://github.com/jialen2/adapters/tree/fdef3d1469a9ebf213082e9cf2c67b73989115a1/src/supergpqa)
is shipped in the adapter fork and reads unmodified pinned upstream function
bodies. It uses the same single-turn client as the Harbor wrapper.

Requests use `gpt-6-luna` via `https://app.ppapi.ai/v1`, with every returned ID
required to equal `gpt-6-luna-2026-09-22`. Prompts, tool policy, parameters and
scoring are symmetric. Four workers run per active side. The user requested
cross-round overlap during execution; the exact sequence and explicit transport
retries are disclosed under Notes & Caveats and in the full report.

Offline source/scorer checks, from the adapters repository root:

```bash
PYTHONPATH=src/supergpqa/src python src/supergpqa/scripts/validate_source.py \
  --upstream-repo /path/to/pinned/SuperGPQA --generated-dir datasets/supergpqa \
  --report pre-parity-validation.json

PYTHONPATH=src/supergpqa/src python src/supergpqa/scripts/summarize_parity.py \
  --experiment-dir /path/to/reconstructed-experiment --output-dir /path/to/report
```

### Direct-agent parity runner

The shared `direct.py` client sends one user message through Chat Completions,
with no model-accessible tools or hidden retries. Both sides use the same Python
stdlib HTTP transport and effective settings: `reasoning_effort=none`,
`temperature=0`, `max_completion_tokens=2048`, and `stream=false`.
`harbor_agent.py` writes the unmodified response to `/app/answer.txt` through
Harbor's upload API; the model does not execute shell commands.

`parity_upstream.py` independently loads the pinned original data-loader and
parser function bodies. AST selection avoids importing unused reporting
packages; upstream function bodies and decorators are not rewritten. The same
adapter suffix and newline normalization are applied to original-side prompts.
`parity.py` checks every selected prompt pair and scorer controls before running.

From the adapters repository root, using an environment with this adapter and
Harbor installed (the original parity runtime was Python 3.13.18 / Harbor 0.25.0;
separate-verifier validation uses Harbor 0.27.0):

```bash
# Offline preparation only: generates exactly 100 tasks and a UUID/code manifest.
PYTHONPATH=src/supergpqa/src python -m supergpqa.parity \
  --upstream-repo /path/to/pinned/SuperGPQA \
  --output-dir /path/to/parity-experiment

# Set SUPERGPQA_BASE_URL and SUPERGPQA_API_KEY in the process environment.
# This experiment uses the provider-confirmed https://app.ppapi.ai/v1 endpoint.
# First validate the credential, exact model/version, parameter compatibility,
# spending limit, and current Harbor revision with the agreed experiment plan.
# Run the 8-task paired sanity check before scaling.
PYTHONPATH=src/supergpqa/src python -m supergpqa.parity \
  --upstream-repo /path/to/pinned/SuperGPQA \
  --output-dir /path/to/parity-experiment --execute --sanity-only --concurrency 4

# Continue the same experiment after inspecting sanity artifacts.
# Completed same-run responses are reused; distinct sides/repetitions make fresh calls.
PYTHONPATH=src/supergpqa/src python -m supergpqa.parity \
  --upstream-repo /path/to/pinned/SuperGPQA \
  --output-dir /path/to/parity-experiment --execute --concurrency 4
```

The runner completes each paired stage before advancing. It stores request JSON
(without authorization headers), complete response JSON/text, model-returned IDs,
usage, timings, per-task scores and native Harbor trial artifacts. It calculates
per-run sample/macro accuracies, between-run sample SEM, and observed score-range
overlap. `summary.json` is an intermediate report; publish reviewed results in
`parity_experiment.json` and this README only after actual execution.

Completed results are reused only with an identical frozen configuration.
Pending/failed calls are never retried automatically because a timeout may have
consumed a paid request. Diagnose these first and record any explicit retry or
configuration change; do not select the better response. Stop scheduling queued
tasks after the first infrastructure failure, allowing in-flight requests to finish.

For a zero-model-call integration check through real Docker, run:

```bash
PYTHONPATH=src/supergpqa/src python src/supergpqa/scripts/parity_docker_smoke.py \
  --upstream-repo /path/to/pinned/SuperGPQA \
  --output-dir /path/to/separate-offline-smoke
```

This uses fake HTTP responses for one correct and one wrong control and tests
resume deduplication. Its artifacts explicitly identify it as offline harness
validation, **not model parity evidence**. Use a fresh output directory for a
new integration test. Keep credentials outside experiment artifacts and source.

### Separate-verifier migration

Generated tasks now explicitly use `verifier.environment_mode = "separate"`
and declare `/app/answer.txt` as an artifact. `tests/Dockerfile` bundles the
unchanged grader, upstream parser, gold record, and pinned scoring dependency.
The agent image contains no grading dependency or gold record. Instructions,
answer paths, task names and scoring semantics remain unchanged.

On Harbor 0.27.0, task `supergpqa-060d1632f1644d4990af62065b597fdd`
passed the same-task Docker controls: Oracle `Answer: D` scored 1; the valid
incorrect option `Answer: A` scored 0. Both trials recorded separate verification
and no infrastructure exception. This is a representative migration check,
not a repeat of the full-bank Oracle on the new template.

All **300 saved Harbor responses** were subsequently regraded with the separate
verifier: **300/300 rewards unchanged**, zero final exceptions and zero model
calls. Run scores remain **46%, 44%, 44%**. See
[SEPARATE_VERIFIER_REPORT.md](SEPARATE_VERIFIER_REPORT.md) for provenance and scope.

To reproduce the controls and regrade saved parity replies without model calls:

```bash
PYTHONPATH=src/supergpqa/src python src/supergpqa/scripts/verify_separate.py \
  --experiment-dir /path/to/reconstructed-original-experiment \
  --output-dir /path/to/new-migration-evidence --concurrency 4
```

Add `--controls-only` for just the same-task Oracle and incorrect-answer checks.
The original shared-verifier trials did not declare the answer artifact. The
script therefore creates **derived source copies**, reconstructs that artifact
from each saved raw API response, records checksums and reconstruction provenance,
and uses Harbor's native `source_trial.action = "regrade"` workflow. It never
modifies the original trials, invokes the model, or reinterprets the response.
Each new reward is checked against its original reward. Derived sources must
not be presented as original artifact-collection events.

## Notes & Caveats

- The actual provider accepts the alias `gpt-6-luna`; a dated-ID request returned
  HTTP 503. Every formal reply passes a `gpt-6-luna-2026-09-22` response guard.
  Null system fingerprints limit backend-configuration verification.
- The user requested original round 2 alongside Harbor round 1 and original
  round 3 alongside Harbor round 2, departing from strictly paired ramp-up.
  Inference parameters and task IDs stayed fixed. Transport failures, retries
  and interrupted native trials are archived separately; no received answer was
  rerun to select a higher score. Billed USD is unknown and metadata records null.
- The 100-question subset represents eight of thirteen disciplines. Results and
  SEM describe this fixed subset and shared direct agent; CLI agents were not
  evaluated. The e-approximation sanity item has multiple options within the
  stated tolerance; upstream gold/parser behavior was preserved.

- Local verification completed: all 26,529 generated tasks load through Harbor's task model; 26,529 gold labels pass and 53,058 wrong/empty controls fail as expected. A 26,529-response deterministic mixed corpus matches the original evaluator and micro/macro/difficulty aggregations. Thirty behavioral tests pass. These results are not container oracle or model parity evidence.
- The original prompt is unchanged, with an appended file-output and closed-book
  instruction. Apply the identical suffix to both sides in future agent parity.
  The instruction alone does not technically enforce tool restrictions; the
  approved harness must enforce or otherwise match the chosen tool policy.
- Fifteen upstream prompts contain embedded carriage returns. Stored prompt bytes are preserved, but Harbor loads instructions using universal-newline normalization. Future original-side agent input must apply the same CRLF/CR-to-LF normalization before claiming parity.
- Parser case and content-fallback quirks are preserved. For example, lowercase
  answer labels need not grade like uppercase ones. Do not normalize silently.
- The native label is a reference answer, not a worked reasoning solution.
- `middle` is mapped to Harbor metadata `medium`; `source_difficulty` preserves
  the original label for reporting.
- Per-task Harbor mean is micro accuracy. Use `scoring.aggregate` for taxonomy
  macro metrics and difficulty metrics; missing runs must not disappear from the
  aggregation denominator.
- Harbor baseline: `ff2a1ef48070a8df374669138e4d4db79b77f013`, schema 1.4,
  package version 1.0. The guide's legacy version examples are reconciled with
  the current runtime and repository create-adapter skill.
- On 2026-11-08, a real Harbor Docker oracle trial passed with reward 1.0 and
  no exception, using Harbor 0.25.0, Python 3.13.18, Docker 29.9.3 and Lima 2.3.0
  on Linux aarch64. An eight-task pilot also passed (8/8 rewards 1.0, zero
  exceptions). The full bank later passed 26,529/26,529 with zero final exceptions; see the
  full Oracle evidence included with the parity report. The Linux installation
  uses `uv sync --locked --no-dev --python 3.13` to avoid macOS native builds.
- For large local runs on macOS, place generated tasks and job results on the
  Linux VM's native disk. Scanning the full bank through the macOS shared mount
  exhausted host file handles during a pilot startup. This occurred before
  trial execution and does not count as a completed oracle experiment.
- Full-bank Oracle and the recorded direct-agent parity experiment are complete.
  [Dataset registration PR #291](https://github.com/harbor-framework/harbor-datasets/pull/291) includes the full bank and fixed parity subset; registry publication remains pending.

## Installation / Prerequisites

- Python 3.12+, uv 0.13.7+; `uv sync --project src/supergpqa` installs adapter deps.
- A complete compatible Harbor installation and working Docker (or approved
  cloud sandbox) are additionally required for container oracle runs.
- Task generation and oracle need no model API key or GPU. Model trials require separately provisioned keys and team coordination.
- Developer differential checks additionally use upstream reporting dependencies:
  pandas, openpyxl, prettytable and tqdm. Do not install the upstream GPU inference
  stack merely to validate task generation.

## Troubleshooting

- Checksum failure: use the pinned source revision; do not disable verification.
- Existing/unselected tasks: select a fresh output directory; use `--overwrite`
  only to deliberately replace tasks in an identical selection.
- Correct-looking answer gets zero: inspect `result.json` and upstream parser
  behavior; use the requested `Answer: X` format with an uppercase letter.
- No reward file: investigate verifier exceptions rather than counting the run
  as a model failure. Grader startup removes stale rewards.
- Docker unavailable: install/start an authorized container runtime, then run
  the full oracle bank. Host scoring controls cannot substitute for that run.

## Citation

```bibtex
@misc{pteam2025supergpqascalingllmevaluation,
  title={SuperGPQA: Scaling LLM Evaluation across 285 Graduate Disciplines},
  author={M-A-P Team and Xinrun Du and Yifan Yao and others},
  year={2025},
  eprint={2502.14739},
  archivePrefix={arXiv},
  url={https://arxiv.org/abs/2502.14739}
}
```

## Authors & Contributions

jiale.ning1 contributed this adapter with Codex assistance for source analysis,
implementation, local validation and documentation.

## Acknowledgement

No paid API inference or parity compute has been used. Add the prescribed
2077AI acknowledgement if their provisioned keys are used in future parity.

The shared HF evidence PR #293 remains open but its artifact push is blocked by the shared repository file-count limit. The complete original evidence and separate-verifier validation are now published in [the personal HF mirror](https://huggingface.co/datasets/jialen2/supergpqa-parity-experiments/tree/3b972e12416341af37116fda29edd0bb94181ac3/adapters/supergpqa), pinned to `3b972e12416341af37116fda29edd0bb94181ac3`. The [root checksum manifest](https://huggingface.co/datasets/jialen2/supergpqa-parity-experiments/blob/3b972e12416341af37116fda29edd0bb94181ac3/SHA256SUMS) has SHA-256 `cf02a761951411cbb3bd853d1f9e35382b81e67a28583349c2b9b90f237655ff`. All 55 remote file hashes were verified. GitHub release attachments remain available as a backup.
