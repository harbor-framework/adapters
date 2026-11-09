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
Docker must be installed and its daemon running. Agent/model experiments are
outside the current pre-parity scope.

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

**Not run. User requested pre-parity work only.** `parity_experiment.json` is
intentionally an empty array rather than fabricated agent/model/results entries.
Full submission validation therefore reports missing parity evidence.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| Not run | Not run | Accuracy | 0 | Not selected | Not measured | Not measured |

No agent/model compatibility claim is made. Upstream currently supports direct
LLM inference, so Scenario 2 of the guide applies if the team chooses a CLI agent:
add the same agent to an upstream fork before running matched experiments.
Never compare a tool-enabled CLI agent directly with a published direct-LLM score.

Reproducible pre-parity source and scorer checks (requires Harbor and upstream
reporting dependencies in the active Python environment):

```bash
git clone https://github.com/SuperGPQA/SuperGPQA.git /path/to/SuperGPQA
git -C /path/to/SuperGPQA checkout e31e8bf3e7089aef808be5ddecafd4538dee6e41
PYTHONPATH=src/supergpqa/src python src/supergpqa/scripts/validate_source.py \
  --upstream-repo /path/to/SuperGPQA --generated-dir datasets/supergpqa \
  --report pre-parity-validation.json
```

These are deterministic local tests, **not** model parity or Harbor container
oracle evidence. After team coordination, both sides must use the same agent,
model ID, prompt suffix, permissions and budgets; run 5–10 tasks on each side,
then one complete agreed bank per side, then repeat symmetrically. Report raw run
scores plus Mean ± sample SEM; complete JSON and PR links only after real runs.

## Notes & Caveats

- Local verification completed: all 26,529 generated tasks load through Harbor's task model; 26,529 gold labels pass and 53,058 wrong/empty controls fail as expected. A 26,529-response deterministic mixed corpus matches the original evaluator and micro/macro/difficulty aggregations. Sixteen behavioral tests pass. These results are not container oracle or model parity evidence.
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
  exceptions). Full-bank container validation is still pending; the smoke trial
  and pilot do not establish full oracle coverage. The Linux installation
  uses `uv sync --locked --no-dev --python 3.13` to avoid macOS native builds.
- For large local runs on macOS, place generated tasks and job results on the
  Linux VM's native disk. Scanning the full bank through the macOS shared mount
  exhausted host file handles during a pilot startup. This occurred before
  trial execution and does not count as a completed oracle experiment.
- Full-bank oracle verification, registry publication, dataset upload and parity
  remain pending. The WIP PR does not claim full-bank oracle success.

## Installation / Prerequisites

- Python 3.12+, uv 0.13.7+; `uv sync --project src/supergpqa` installs adapter deps.
- A complete compatible Harbor installation and working Docker (or approved
  cloud sandbox) are additionally required for container oracle runs.
- Task generation and oracle need no model API key or GPU. Future model trials
  require separately provisioned keys and team coordination.
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
