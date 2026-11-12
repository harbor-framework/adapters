# FrontierScience-Research → Harbor Adapter

**Status.** The oracle passes on all 60 tasks in Harbor 0.25.0. Parity has not been run yet; see [Comparison with Original Benchmark](#comparison-with-original-benchmark-parity).

## Overview

This adapter turns the Research split of OpenAI's FrontierScience benchmark into Harbor tasks. Each task is an open-ended research sub-problem in physics, chemistry or biology. The agent writes a free-form answer to `/workspace/answer.md`, and the verifier grades it with an LLM judge against the task's 10-point expert rubric, using the judge prompt from the paper.

- **Source:** Hugging Face [`openai/frontierscience`](https://huggingface.co/datasets/openai/frontierscience), file `research/test.jsonl`, Apache-2.0. The adapter pins revision `25ed67db7da8f4591484e764008ff585544f5a30` and checks the file's SHA-256.
- **Original harness:** OpenAI released no evaluation code. The closest public implementation is [`inspect_evals/frontierscience`](https://github.com/UKGovernmentBEIS/inspect_evals/tree/main/src/inspect_evals/frontierscience) with `format=research`. It sends the problem to a model with no tools and grades the reply with the same judge prompt.
- **Adapted size:** 60 tasks, one per row of the file: 20 physics, 20 chemistry and 20 biology. Rows 6 and 11 are an exact duplicate, so there are 59 distinct problems. Both rows are kept, as in inspect_evals.
- **Main adaptation:** the agent receives the problem verbatim, followed by one paragraph that names the answer file.
- **Not included:** the Olympiad split, which uses short reference answers instead of rubrics.

## What is FrontierScience-Research?

[FrontierScience](https://arxiv.org/abs/2601.21165) (Wang et al., OpenAI, 2026) measures expert-level scientific reasoning. Its Research split contains open-ended sub-problems of the kind a scientist meets in research. Each problem comes with a rubric of gradable items worth 10 points in total. A judge model reads the problem, the rubric and the answer, reasons about each item, and ends its reply with `VERDICT: <points>`. The paper uses GPT-5 with high reasoning effort as the judge and counts an attempt as a success when it earns at least 7 of the 10 points. inspect_evals reports the mean of points / 10 instead.

## Adapter Features

- **Pinned, verified data.** The adapter downloads `research/test.jsonl` at the pinned revision, or reads a local copy given with `--data-file`, and refuses to build on a SHA-256 mismatch.
- **Stable task names.** Tasks are named `openai/frontierscience-research__<subject>-<first 8 characters of task_group_id>`, for example `physics-222e24bf`. The second copy of the duplicate is `physics-af50243e-2`.
- **Rubric isolation.** The rubric is written only to `tests/task.json`, which Harbor uploads at verification time. A unit test generates tasks from a sentinel rubric and checks that it never appears in a file the agent can see.
- **Grading as in inspect_evals.** `tests/grader.py` uses the inspect_evals research judge prompt verbatim, which is the paper's Appendix B prompt. It takes the first `VERDICT:` number in the reply, clamps it to [0, 10], and scores an empty or missing answer as 0 without calling the judge.
- **Two rewards.** `reward.json` holds `reward`, which is 1 when the answer earns at least 7 points (the paper's success criterion), and `score`, which is points / 10 (the inspect_evals metric).
- **Judge failures are not zeros.** If the judge refuses (`stop_reason == "refusal"`) on all three attempts, or the API call fails after the SDK's retries, the verifier exits non-zero without writing a reward, and Harbor reports a verifier error. `grading.json` keeps the judge's reply, the model that answered, token usage and any refusal details.
- **Configurable judge.** `JUDGE_MODEL` (default `claude-sonnet-5-5`), `JUDGE_EFFORT` (default `high`) and `ANTHROPIC_BASE_URL` are passed to the verifier from the host environment.
- **Oracle answers.** `oracle_solutions/` holds an answer for each of the 59 distinct problems; see [Notes & Caveats](#notes--caveats).

## Generated Task Structure

```
datasets/frontierscience-research/
└── <subject>-<tgid8>/            # e.g. physics-222e24bf
    ├── task.toml                 # name, metadata, judge environment, timeouts
    ├── instruction.md            # the problem and where to write the answer
    ├── environment/
    │   └── Dockerfile            # python:3.12-slim with anthropic 2.8.0 for the grader
    ├── solution/
    │   ├── solve.sh              # copies answer.md to /workspace/answer.md
    │   └── answer.md             # oracle answer
    └── tests/
        ├── test.sh               # runs grader.py
        ├── grader.py             # LLM judge
        └── task.json             # problem, rubric, ids
```

Adapter code:

```
src/frontierscience-research/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_frontierscience-research.yaml
├── oracle_solutions/             # <subject>-<tgid8>.md, one per distinct problem
├── src/frontierscience_research/
│   ├── __init__.py
│   ├── adapter.py
│   ├── main.py
│   └── task-template/
│       ├── task.toml
│       ├── instruction.md
│       ├── environment/Dockerfile
│       ├── solution/solve.sh
│       └── tests/
│           ├── test.sh
│           └── grader.py
└── tests/test_adapter.py
```

## Run Evaluation / Harness

The verifier calls the judge through the Anthropic Messages API, so `ANTHROPIC_API_KEY` must be set in the shell that runs Harbor, or passed in a `.env` file with `harbor run --env-file .env`.

```bash
export ANTHROPIC_API_KEY=...
# optional: JUDGE_MODEL (default claude-sonnet-5-5), JUDGE_EFFORT (default high), ANTHROPIC_BASE_URL
```

### Running with Datasets Registry

After the dataset is published:

```bash
# Oracle
harbor run -d openai/frontierscience-research

# An agent and model
harbor run -d openai/frontierscience-research -a <agent> -m "<model>"
```

### Using Job Configurations

From the repository root, after generating the tasks (see [Usage](#usage-create-task-directories)):

```bash
# Oracle; edit the agents block in the YAML to run another agent
harbor run -c src/frontierscience-research/run_frontierscience-research.yaml
```

### Running with Local Path

```bash
harbor run -p datasets/frontierscience-research -a <agent> -m "<model>"

# A single task
harbor trial start -p datasets/frontierscience-research/<task_id> -a <agent> -m "<model>"
```

One full grading pass is 60 judge calls. For the oracle answers it used about 640k input and 55k output tokens with `claude-sonnet-5-5`, roughly US$1.8 at list prices.

## Usage: Create Task Directories

```bash
cd src/frontierscience-research
uv run frontierscience-research --output-dir ../../datasets/frontierscience-research
```

Flags:

- `--output-dir DIR`: where to write the tasks (default `datasets/frontierscience-research` at the repository root).
- `--limit N`: generate only the first N tasks.
- `--overwrite`: replace existing task directories.
- `--task-ids ID [ID ...]`: generate only these tasks, for example `physics-222e24bf`.
- `--data-file PATH`: use a local copy of `research/test.jsonl`; its SHA-256 is still checked.
- `--oracle-dir DIR`: oracle answers, `<subject>-<tgid8>.md` (default `oracle_solutions/`). A task with no file there gets no `answer.md`, and its `solve.sh` exits 1.

Unit tests (offline, no API key):

```bash
cd src/frontierscience-research
uv run --with pytest --with anthropic==2.8.0 pytest tests -q
```

## Comparison with Original Benchmark (Parity)

Parity has not been run. The plan below is still to be agreed with the Harbor team:

- **Original side:** `inspect_evals/frontierscience` with `format=research`, on a fork that runs the same agent as the Harbor side with the same instruction text (Scenario 2), unless the team prefers another setup.
- **Judge:** the same judge model and settings on both sides (`grader_model` in inspect_evals, `JUDGE_MODEL` / `JUDGE_EFFORT` here). Which judge to use is an open question; the paper used GPT-5 with high reasoning.
- **Tasks:** all 60. The benchmark is small, so no parity subset is needed.
- **Metrics:** success rate (share of tasks with at least 7 points) and mean score (points / 10), each reported as mean ± sample SEM over runs.

Commands, to be finalized with the plan (one invocation per run):

```bash
# Harbor side, from the repository root
export JUDGE_MODEL=<judge model> JUDGE_EFFORT=<effort>
harbor run -p datasets/frontierscience-research -a <agent> -m "<model>"

# Original side: inspect_evals research format with the same judge
# (the agent and the instruction paragraph are added on the parity fork)
inspect eval inspect_evals/frontierscience -T format=research -T grader_model=<judge model> --model <model>
```

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| TBD | TBD | Success rate (points ≥ 7) | TBD | 60 | pending | pending |
| TBD | TBD | Mean score (points / 10) | TBD | 60 | pending | pending |

**Oracle check (not parity).** Harbor 0.25.0, Docker 28.3.2 on macOS arm64, 8 concurrent trials, judge `claude-sonnet-5-5` with effort `high`: 60 trials, 0 exceptions, `reward` 1.000 and `score` 0.999. 58 tasks scored 10/10 and two scored 9.75 (see Notes & Caveats). The judge refused none of the 60 tasks, including the 20 biology tasks.

## Notes & Caveats

**Duplicate row.** Rows 6 and 11 of `research/test.jsonl` are identical (task_group_id `af50243e…`). inspect_evals keeps both, so this adapter does too, as `physics-af50243e` and `physics-af50243e-2`. That problem therefore counts twice in the 60-task mean, as it does in inspect_evals. Match tasks across the two sides by task_group_id, not by inspect sample id: inspect_evals numbers the duplicate with a module-level counter, so its ids change if the task is built twice in one process.

**Instruction.** The problem text is passed verbatim. It already ends with the paper's request to show all intermediate derivations, formulas, important steps and justifications. The adapter adds a horizontal rule and one paragraph telling the agent to write the complete answer to `/workspace/answer.md`, the only file that is graded. inspect_evals sends the bare problem, so for parity the original side has to add the same paragraph.

**Tools and network.** The paper evaluated models without browsing, and inspect_evals calls the model with no tools. Harbor agents work in a container with network access, which the verifier also needs to reach the judge. The problems and rubrics are public on Hugging Face, so an agent with web access could look up a rubric. The adapter does not prevent this, so parity runs should apply the same tool policy on both sides.

**Judge.** The paper's judge is GPT-5 with high reasoning effort. inspect_evals grades with the model under test unless `grader_model` is set. This adapter defaults to `claude-sonnet-5-5` with effort `high`, which was used to validate the oracle. Scores are comparable only under the same judge. The grader supports only the Anthropic API.

**Judge refusals.** A refusal is retried twice. If all three attempts are refused, the trial ends in a verifier error and is not scored 0, so refusals stay visible. For the same reason the API's server-side refusal fallback, which would silently switch to another model, is not enabled.

**Oracle answers.** The release has no reference solutions. The 59 answers in `oracle_solutions/` were written for this adapter with AI assistance against each task's rubric. Each answer was then reviewed item by item against its rubric and revised where needed. Where a rubric item asks for a specific expression or value, the answer states it as the rubric does, even where the rubric looks wrong (see below), because the judge prompt treats the rubric as the gold standard. The answers are therefore an answer key for the rubrics, not a vetted set of scientific solutions. In the oracle run, two tasks scored 9.75 instead of 10:

- `chemistry-845a3693`: the rubric's carbon numbering is ambiguous. The same answer scored 10 in an earlier run, so the difference is judge variance.
- `physics-bc82c611`: the answer gives a physically consistent τ(Ψ), while the rubric's expression omits the 1/Γ term.

**Rubric defects.** Rubrics are used exactly as released. They are not patched for two reasons: the judge prompt treats the rubric as the gold standard, and a patched rubric would no longer match the original benchmark or the parity side. While the oracle answers were being written, the issues below were flagged in 33 problems or rubrics. They have not been confirmed with the authors and have not been reported upstream yet.

<details>
<summary>Flagged problem and rubric issues (33 tasks)</summary>

| Task | Issue |
|------|-------|
| `physics-07fd78cd` | The singlet identity (U⊗I)\|S⟩ = (I⊗U†)\|S⟩ used in the rubric holds only for d = 2. |
| `physics-1a5d24e0` | The dual-Fock state needs a (−1)^k factor; ⟨N²⟩ is written where ⟨N⟩² is meant; the "expected" QFI belongs to a different state and exceeds the rubric's own bound. |
| `physics-222e24bf` | The Im A_w term and a Var(F) prefactor are missing in the k = 1 case of I^(k). |
| `physics-3182a1e3` | F2 is not Hermitian ([F1, F2] = −1/2, not i/2); the displaced-Fock coefficient is off by √(k!); "the original state is Gaussian" is false for LG00 + LG01; "r = 1–4" is undefined. |
| `physics-3f380f88` | The joint state is missing a "+" sign. |
| `physics-70c1246f` | Coefficient B misses a −D/(2ka) term and breaks continuity at x = a with the rubric's own A. |
| `physics-790baca4` | The small-angle chain for r, area, Θ and Δt is algebraically inconsistent (the final Δt/T is off by (1+e)/(1−e)); F_s/F_q misses a/q. |
| `physics-7fbca2d0` | Non-standard sign on İ; the 1/4 prefactor holds only in units ħ = 2m = 1; no values are given for ρ_n, φ_n, ε_n, w_n, f_n. |
| `physics-8fac71ae` | Super-Kamiokande-specific numbers (54 %/99 %, more than 20 hits within 300 ns, 50 µs) cannot be derived from the problem. |
| `physics-9557097c` | S_Q (exact match required) misses a minus sign; T_Q(P) = P/√λ contradicts T_Q(a) and T_Q(a†); ln(2πeΣ/ħ) = ln(Σ/ħ) + 1 is false. |
| `physics-bc82c611` | The amplitude's e^{+Γ_H t/2} contradicts the probability e^{−Γ_H t}; the third term of R is dimensionally wrong unless Γ = 1; τ(Ψ) omits the 1/Γ term. |
| `physics-bf7d23f3` | The φ̇1 equation (sin θ, no eV/ħ term) contradicts φ̇2 and the AC item; the signs hold only for θ = φ2 − φ1, the opposite of the problem's φ1 − φ2. |
| `physics-d3acd2cb` | Index typo in S_3; 40.5 MeV uses M = 1638 MeV while the problem gives 1634 MeV; no numbers are given for C or the first excited state. |
| `physics-d50f3722` | The sign of Eq. (5) is inconsistent with H (convention-dependent); −βεS_z/√2 needs a 1/2π frequency measure. |
| `chemistry-0eb69a4c` | The catalyst is given both as [Ir(OMe)cod]2 and as [Ir(OMe)2cod]. |
| `chemistry-0f13c295` | An excitation rate (s⁻¹) is multiplied by an "initial rate" (molecules/s), so the units are inconsistent. |
| `chemistry-1567b1bb` | The problem gives no structures, so the electrophile-to-product mapping has to be inferred from the rubric's π counts. |
| `chemistry-2d0a5720` | "Slower chemical shift anisotropy relaxation time" is internally inconsistent. |
| `chemistry-7c94f50a` | 25 nm and 1000 nm are called "hydrodynamic volumes"; they are sizes. |
| `chemistry-845a3693` | The CBD numbering "1–10, 1′–6′, 1″–2″" does not cover CBD's 21 carbons; the pentyl chain needs 1″–5″. |
| `chemistry-91a30120` | ΔL for Cl uses the TCB plateau (0.59 nm), while the I case uses TIB. |
| `chemistry-a6176b58` | Comp-4 and NS9283 (3.40 ± 0.85 vs 3.21 ± 0.55) overlap within one SD, yet the gain is attributed to NO2; "cyclohexenyl … for 23–26" is off by one. |
| `chemistry-b818c26a` | The required ranking puts caproic acid (C6) above capric acid (C10), which is not monotonic in chain length. |
| `chemistry-fec1882e` | A neutral mass of about 823.6 Da matches no BMP 18:2/20:3 (monoisotopic 808.53 Da); "DAG mass 620–630" fits only the water-loss DAG ion. |
| `biology-163a8ed3` | The item title and its criterion disagree on H3.3 deposition after ATRX/DAXX loss; JQ1 is listed as an ALT inhibitor in Phase II trials. |
| `biology-2f43ac4a` | The problem spells SCH772984 as "SCH722984"; "p-RSK unchanged" under an ERK inhibitor is mechanistically odd. |
| `biology-4525a8e7` | NIH 3T3 (a mouse line) is required for lentivirus production; HEK293T is the standard producer line. |
| `biology-7e32b7a6` | Part 1A's "large shift in kDa" only makes sense for a non-denaturing gel, which Part 1D leaves unspecified. |
| `biology-824508b0` | Cdc42 is called "a g-protein (part of GPCR signaling pathways)", but it is a Rho-family small GTPase; Q2 asks for loss-of-function fin patterning, but the rubric's only answer is embryonic lethality. |
| `biology-9c098058` | The AND gate is called "CRISPRi-based" while a split activator is described. |
| `biology-a466aab3` | The problem labels parts 1A–1E and then 1G; there is no 1F. |
| `biology-b93b8a19` | "Unregulated" in items 4 and 5 probably means "upregulated". |
| `biology-dcfa830a` | Paraxial mesoderm is called "evolutionarily younger" than lateral plate mesoderm, which is debatable; the forelimb, hindlimb and interlimb HOX assignments overlap. |

</details>

**Training-data notice.** The dataset card asks that the benchmark data never appear in training corpora and gives a canary string. Harbor's adapter validator rejects canary strings in adapter files, so neither the adapter files nor the generated tasks carry it.

## Installation / Prerequisites

- Docker, and Harbor 0.25.0 or later (tested with 0.25.0).
- [uv](https://docs.astral.sh/uv/) for the adapter package: `cd src/frontierscience-research && uv sync`. The adapter itself uses only the standard library.
- Network access to Hugging Face when generating tasks, to PyPI when building the task image, and to the judge API at verification time.
- An Anthropic API key with access to the judge model in `ANTHROPIC_API_KEY`. `ANTHROPIC_BASE_URL`, `JUDGE_MODEL` and `JUDGE_EFFORT` are optional.

## Troubleshooting

- **`research/test.jsonl SHA-256 mismatch`:** the downloaded file is not the pinned revision. Pass a correct copy with `--data-file`.
- **Verifier error, `grading.json` status `judge_error`:** the judge API call failed after retries. Check `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` and `JUDGE_MODEL`.
- **Verifier error before any `grading.json` is written:** usually `ANTHROPIC_API_KEY` was not set in the shell or `--env-file` that ran Harbor.
- **Verifier error, status `judge_refused`:** the judge refused all three attempts. `grading.json` records the refusal category and request ids. Rerun the trial or use another `JUDGE_MODEL`.
- **Reward 0 with status `unparsed_verdict`:** the judge's reply had no `VERDICT:` line. inspect_evals also scores this as 0.
- **Oracle `solve.sh` exits 1 ("No oracle answer was generated"):** the task was generated with an `--oracle-dir` that has no file for it. The generator prints a warning listing such tasks.

## Citation

```bibtex
@misc{wang2026frontierscience,
  title         = {FrontierScience: Evaluating AI's Ability to Perform Expert-Level Scientific Tasks},
  author        = {Wang, Miles and Lin, Robi and Hu, Kat and Jiao, Joy and Chowdhury, Neil and Chang, Ethan and Patwardhan, Tejal},
  year          = {2026},
  eprint        = {2601.21165},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2601.21165}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Yanchuan Tang](mailto:yctangcse@gmail.com) ([@sakura657](https://github.com/sakura657)).

**Issues and Contributions:**
- Open an issue or pull request in this repository, or ask in the Harbor Discord.
