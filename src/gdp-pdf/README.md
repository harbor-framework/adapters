## GDP.pdf → Harbor Adapter

## Overview

GDP.pdf tests whether a model can answer professional questions from real PDF documents. Each task pairs a question from a working professional with one PDF (filings, engineering drawings, datasheets, policies, clinical papers and similar) and is graded against an expert-written rubric.

- **Source:** 100 tasks across 10 domains: construction, engineering, finance & investing, healthcare, HR, insurance, legal, manufacturing & supply chains, real estate, and STEM research (7 to 15 tasks each). The language is English.
- **This adapter:** 99 tasks. legal-03 is excluded because two of its rubric points contradict each other, so no answer can pass both (see [Notes & Caveats](#notes--caveats)).
- **Rubrics:** 1,269 rubric points across the 99 tasks, 3 to 30 per task (median 11).
- **Data:** Surge's Hugging Face dataset is no longer public, so the adapter reads a public copy, `cloudybean/GDP.pdf`, pinned at revision `1b73b865` with the parquet's sha256 checked. This is the September 2026 version, MIT licensed.
- **Main change for agents:** the original harness attaches the PDF to a single model call. Here the PDF sits in the container at `/workspace/document.pdf` and the agent writes its answer to `/workspace/answer.md`. Grading is unchanged.

## What is GDP.pdf?

GDP.pdf is a benchmark from Surge AI ([paper](https://arxiv.org/abs/2607.11192), [leaderboard](https://surgehq.ai/benchmarks/gdp-pdf)) that measures grounded, multimodal reasoning over professional documents. The questions and rubrics were written by 78 domain experts. In the original setup the PDF is attached to the prompt, the model answers once with no tools, and an LLM judge (Gemini 3.5 Flash) grades each rubric point separately, seeing only the response and that one criterion. It reports two metrics:

- `all_pass`: the share of tasks where every rubric point passes. This is the headline number.
- `mean_criteria`: the share of rubric points passed, averaged over tasks.

## Adapter Features

- **Task data from a pinned source.** The adapter downloads the parquet and PDFs from the pinned Hugging Face revision and checks the parquet's sha256 before generating anything.
- **PDF tools in the container.** The image is `python:3.12-slim` plus `poppler-utils` (`pdftotext`, `pdftoppm`), because 9 of the 100 PDFs are scans with no text layer and need to be rendered as images.
- **Surge's grader, ported without Inspect** (`tests/grader.py`):
  - the judge prompt and JSON schema are verbatim;
  - one judge call per rubric point, and the judge sees only the answer and that criterion;
  - strict parsing with 4 retries;
  - a point passes when its score rounds to at least 1 at 4 decimals.
- **Rewards.** `reward.json` holds `reward` (1.0 if every point passes, else 0.0, which is `all_pass`) and `mean_criteria`.
- **Grading in a separate container.** The verifier runs with `environment_mode = "separate"`: Harbor grades in a fresh container from the same image and copies in only `answer.md`, so nothing the agent changes can affect grading.
- **No leaks to the agent.** Task names look like `hr-03` (domain plus number). Upstream ids, the benchmark name and links are kept out of everything the agent sees.
- **Parity subset.** `--split parity` generates the 30 tasks used for parity.

## Generated Task Structure

```
gdp-pdf/
├── hr-03/
│   ├── task.toml                 # Task config: 1 CPU, 4 GB RAM, 30 min agent / 15 min verifier timeouts
│   ├── instruction.md            # The expert's question, plus where the PDF is and where to write the answer
│   ├── environment/
│   │   ├── Dockerfile            # python:3.12-slim + poppler-utils + the judge's virtualenv
│   │   └── document.pdf          # The task's PDF
│   ├── solution/
│   │   ├── solve.sh              # Copies the oracle answer to /workspace/answer.md
│   │   └── answer.md             # Oracle answer (empty unless generated with --oracle-dir)
│   └── tests/
│       ├── test.sh               # Runs grader.py
│       ├── grader.py             # Rubric grader (one judge call per point)
│       └── rubric.json           # The task's rubric points
```

Adapter code layout:

```
src/gdp-pdf/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_gdp-pdf.yaml
├── scripts/                      # build_oracle.py: the oracle-answer workflow
├── tests/                        # grader, naming, parity-split and oracle-builder tests
└── src/gdp_pdf/
    ├── __init__.py
    ├── adapter.py                # GdpPdfAdapter: download, name, filter, render tasks
    ├── main.py                   # CLI
    └── task-template/            # task.toml, instruction.md, environment/, solution/, tests/
```

## Run Evaluation / Harness

Once the dataset is published to the Harbor registry (the harbor-datasets PR is pending), it can be run by name with `harbor run -d`. Until then, generate the tasks locally (see [Usage](#usage-create-task-directories)) and run them from the repository root.

The verifier needs judge credentials in the environment: `OPENAI_API_KEY`, `OPENAI_BASE_URL` (any OpenAI-compatible endpoint that serves the judge, e.g. Gemini's `https://generativelanguage.googleapis.com/v1beta/openai/`) and optionally `JUDGE_MODEL` (default `gemini-3.5-flash`).

```bash
# Oracle on the full dataset (default job config)
harbor run -c src/gdp-pdf/run_gdp-pdf.yaml

# Any Harbor agent on a locally generated dataset
harbor run -p datasets/gdp-pdf -a claude-code -m "anthropic/claude-haiku-4-5"

# One task
harbor run -p datasets/gdp-pdf -i hr-03 -a claude-code -m "anthropic/claude-haiku-4-5"

# Resume a job
harbor job resume -p /path/to/jobs/directory
```

Results go to `jobs/` by default. The oracle only works on tasks generated with `--oracle-dir` (see Notes & Caveats).

## Usage: Create Task Directories

```bash
cd src/gdp-pdf
uv run gdp-pdf --output-dir ../../datasets/gdp-pdf

# With oracle answers, so the oracle agent can run
uv run gdp-pdf --output-dir ../../datasets/gdp-pdf --oracle-dir /path/to/oracle-answers

# Only the 30-task parity subset
uv run gdp-pdf --split parity --output-dir ../../datasets/gdp-pdf-parity
```

Available flags:
- `--output-dir` — Directory to write generated tasks (defaults to `datasets/gdp-pdf` at the repo root)
- `--limit` — Generate only the first N tasks
- `--overwrite` — Overwrite existing tasks
- `--task-ids` — Only generate these tasks (Harbor names like `hr-03`, or upstream task ids)
- `--split` — `full` (default, all 99 tasks) or `parity` (the 30-task parity subset)
- `--oracle-dir` — Directory of oracle answers named `<upstream task_id>.md`

The generated tasks take about 450 MB, almost all of it PDFs.

## Comparison with Original Benchmark (Parity)

GDP.pdf's own harness (an Inspect eval) sends the PDF to a model in one call and has no agent, so this is Scenario 2. The [fork](https://github.com/Pranavv-dev/gdp-pdf/tree/harbor-parity) adds an agent mode that launches Claude Code exactly the way Harbor 0.25.0's `claude-code` agent does: the same binary, env vars, setup and command. Both sides grade with the same judge (`gemini-3.5-flash`) and Surge's rubric prompt, one judge call per rubric point.

Parity ran on 30 of the 99 tasks, 3 per domain, picked with `random.Random(0)` over the domains in sorted order. `uv run gdp-pdf --split parity` generates exactly these tasks. Each side ran a 5-task sanity check and then 3 runs, one task at a time.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| claude-code@2.1.311 | claude-haiku-4-5 | mean_criteria (%) | 3 | 30 (of 99) | 60.21 ± 0.35 | 59.57 ± 2.76 |
| claude-code@2.1.311 | claude-haiku-4-5 | all_pass (%) | 3 | 30 (of 99) | 6.67 ± 0.00 | 8.89 ± 1.11 |

Scores are mean ± sample SEM over the 3 runs. Per run, mean_criteria was 60.73 / 60.36 / 59.55 on the original side and 64.60 / 55.07 / 59.03 on Harbor; all_pass was 6.67 on every original run and 10.00 / 10.00 / 6.67 on Harbor. The run ranges overlap for both metrics. No trial errored on either side (90 per side). Full details are in `parity_experiment.json`.

Parity and oracle artifacts: [harborframework/parity-experiments#285](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/285). That repository is over the Hub's file limit, so for now the files are in [PranavVashistha/gdp-pdf-parity-experiments](https://huggingface.co/datasets/PranavVashistha/gdp-pdf-parity-experiments) in the same layout.

**Metrics** (Surge's two):
- `mean_criteria`: for each task, the fraction of rubric points the judge passes, averaged over tasks. Harbor writes it to `reward.json` as `mean_criteria`.
- `all_pass`: the share of tasks where every rubric point passes. This is Harbor's `reward` (1.0 or 0.0 per task).

**Reproduce the original side** with the fork's `harbor-parity` branch (the runs used commit `5dfa939`). Its README has the setup; in short:

```bash
git clone -b harbor-parity https://github.com/Pranavv-dev/gdp-pdf && cd gdp-pdf
# CLAUDE_BIN_DIR = dir with the linux-arm64 claude 2.1.311 binary
# ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL for the agent, PPAPI_API_KEY / PPAPI_BASE_URL for the judge
uv run inspect eval src/gdp_pdf/agent_task.py@gdp_pdf_agent \
  --model anthropic/claude-haiku-4-5 \
  -T agent_model=claude-haiku-4-5 -T agent_version=2.1.311 \
  -T judge_model=openai-api/ppapi/gemini-3.5-flash \
  --max-samples 1 --sample-id "$(cut -f2 parity_subset.tsv | paste -sd, -)"
```

**Reproduce the Harbor side:**

```bash
cd src/gdp-pdf
uv run gdp-pdf --split parity --output-dir ../../datasets/gdp-pdf-parity
cd ../..
# ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL for the agent
# OPENAI_API_KEY / OPENAI_BASE_URL for the judge, JUDGE_MODEL=gemini-3.5-flash
harbor run -p datasets/gdp-pdf-parity -a claude-code -m anthropic/claude-haiku-4-5 \
  --ak version=2.1.311 -n 1
```

For the parity runs, the same `claude` binary was bind-mounted read-only at `/root/.local/bin`, so Harbor skipped downloading it in every container. It's the same version either way.

**Notes on the parity runs:**
- **Model ID.** The guide asks for a dated model ID, but the 2077AI API only serves the alias `claude-haiku-4-5`; the dated `claude-haiku-4-5-20251001` returns `model_not_found`. Both sides used the same alias through the same API on the same days (Nov 15-16, 2026).
- **Same grading.** Harbor's run-1 answers were re-graded with Surge's own scorer: 64.89%, against 64.60% from Harbor's grader. 98.2% of rubric points (449/457) got the same verdict.
- **Agent cost.** The original side's agent cost 0.85-0.92x Harbor's. Settings, turns and tool calls match; the difference comes from prompt-cache misses at the API proxy ($1.97 over 90 task-runs) and doesn't change scores.
- **Separate grader.** After the parity runs, the verifier moved to its own container (`environment_mode = "separate"`), so the agent can't change the grader. What the agent sees is unchanged, and no parity trajectory touched the grader's files, so the results carry over. The oracle passes all 99 tasks with the separate grader.
- **Attempts not counted.** A 5-task sanity check and a first full run (stopped at original 33/99, Harbor 36/99) used Inspect's own Claude Code wrapper on the original side, which used about 40% more tokens. They were replaced by the Harbor-identical launch, which passed its own 5-task sanity check (one earlier attempt failed to start its container). All attempts are listed in the parity upload.
- **Cost.** About $81 on the 2077AI key for parity, judge included; the 3 counted runs cost $55.72.

## Notes & Caveats

**Excluded task.** legal-03 asks for two lists, but two of its rubric points each say the response should "only identify" one of them. The judge scores one point at a time, so any complete answer fails one of the two. Seven different answer layouts were tried, and each failed at least one "only" point. The rubric is the same in every public copy of the dataset, so the flaw is upstream, and no model can pass this task in Surge's harness either. It is listed in `EXCLUDED_TASKS` in `adapter.py`; every other task keeps its name.

**Oracle answers.** GDP.pdf ships rubrics but no reference answers, so the oracle answers were written with AI help (`scripts/build_oracle.py`):
- Claude Code drafted each answer from the question, the PDF (page images for the scanned ones) and the rubric.
- The task's own grader judged the draft, and failed points went back with the judge's reasoning. An answer was accepted only after passing every point 3 times in a row.
- A separate check compared every claim in each answer against the PDF, since the judge never sees the PDF. About 25 answers had small errors (wrong page numbers, an overstated sentence, a misread chart value); they were fixed and graded again.
- The oracle passes all 99 tasks with the separate grader.
- The answers are not in this repo. They ship with the published dataset, and the adapter takes them with `--oracle-dir`. Tasks generated without them have an empty `answer.md`, so the oracle fails on them.

**Rubric points that disagree with the PDF.** While building the oracle, some rubric points turned out to expect things the PDF doesn't support. The oracle answers follow the rubric so they still pass, but a correct agent can lose points on these:
- The rubric expects something the PDF contradicts:
  - construction-05: says roof pitch, foundation and framing details are missing, but sheets S1, SD1 and SPEC contain them.
  - construction-07: a "recessed ceiling speaker" that isn't labelled anywhere.
  - finance-investing-04: −87.0% where the PDF's figures give −86.6%.
  - finance-investing-05: says cost of goods sold rose, but it fell 2%.
  - finance-investing-07: 1,000 bps where the PDF gives 100 bps.
  - finance-investing-08: treats a year-to-date figure as Q2; the credit-card record is actually Q3 2011.
  - healthcare-08: PESI 138 as Class IV, but Table 6 puts it in Class V.
  - hr-02: 42 days, but the service bracket gives about 36.
  - insurance-02: a definition the policy text actually meets.
  - legal-01: cites two cases that are not in the PDF.
  - manufacturing-supply-chains-09: part 316L616, but the PDF prints 361L616.
  - real-estate-10: A-coil replaced in 2020, but the PDF says 9/2022.
  - stem-research-02: 40–60%, but the figure shows about 51–65%.
- The rubric relies on readings the PDF doesn't clearly support: engineering-03 (chart values), hr-08 ("paid" leave isn't stated), insurance-05 (an assumed payment date), insurance-09 (hail damage not visible in the photo), manufacturing-supply-chains-01 (head count not stated), real-estate-04 (what "Pending" means).
- The rubric's rounding doesn't match the PDF's numbers, though the answers stay within its ranges: manufacturing-supply-chains-06, manufacturing-supply-chains-08, real-estate-08.
- manufacturing-supply-chains-05 can't be fully done as asked: not every quantity fits in the required time window. The oracle answer schedules what fits and lists the shortfall.

**Points the judge reads inconsistently.** Some "only" and "avoid" points occasionally flip between runs on the same answer. construction-08, manufacturing-supply-chains-09 and stem-research-08 each needed their oracle answer reworded to pass reliably: in each, a required value or label looked to the judge like the thing an "avoid" point forbids.

**Grading differences from Surge's harness.**
- An empty or missing `answer.md` scores 0 without calling the judge. Surge's harness would send the empty string to the judge.
- If a rubric point can't be scored after every retry, the verifier exits without writing a reward, so the trial shows as a verifier error. Surge leaves such responses out of `all_pass` instead of scoring them 0.

**Agent vs single completion.** An agent reading a PDF from disk with command-line tools is a different test from a model receiving the PDF natively in one call. Harbor scores are not comparable with the public leaderboard.

## Installation / Prerequisites

- Docker, installed and running.
- Harbor; this adapter was tested with Harbor 0.25.0.
- Python 3.12+ and `uv`. Install the adapter's dependencies with:
  ```bash
  cd src/gdp-pdf
  uv sync
  ```
- Network access to Hugging Face to download the dataset (about 450 MB of PDFs).
- API keys:
  - for the agent, e.g. `ANTHROPIC_API_KEY` for Claude Code;
  - for the judge: `OPENAI_API_KEY`, `OPENAI_BASE_URL` and optionally `JUDGE_MODEL` (see [Run Evaluation](#run-evaluation--harness)).

## Troubleshooting

- **Every trial ends in a verifier error.** The judge settings are probably missing: `OPENAI_API_KEY` must be set on the host, because `[verifier.env]` in `task.toml` passes it in.
- **An occasional verifier error on one task.** A rubric point couldn't be scored after 5 attempts (judge timeouts or unparseable output). Re-run that task.
- **Oracle fails with "No reference answer for this task".** The tasks were generated without `--oracle-dir`.
- **Agents struggle with some PDFs.** 9 PDFs are scans with no text layer, so `pdftotext` returns nothing. Agents need `pdftoppm` to render pages as images.

## Citation

```bibtex
@misc{garre2026gdppdfbenchmarkinggroundedmultimodal,
      title={GDP.pdf: Benchmarking Grounded Multimodal Reasoning over Professional PDF Documents},
      author={Suhaas Garre and Emily Ritchie and Sushant Mehta and Edwin Chen},
      year={2026},
      eprint={2607.11192},
      archivePrefix={arXiv},
      primaryClass={cs.CV},
      url={https://arxiv.org/abs/2607.11192},
}
```

## Authors & Contributions

- **Adapter:** [@Pranavv-dev](https://github.com/Pranavv-dev) (Pranav Vashistha).
- **Benchmark:** Surge AI (see [Citation](#citation)).
- **AI use:** Claude Code wrote most of the adapter code and tests, drafted and checked the oracle answers, and ran the parity experiments; the author reviewed the results.
- Issues and improvements are welcome via the adapters repository.

## Acknowledgement

API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
