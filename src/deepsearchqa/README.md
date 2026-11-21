## DeepSearchQA → Harbor Adapter

## Overview

This adapter converts **DeepSearchQA** (Google DeepMind) into Harbor tasks.

- **Size:** 900 tasks — one per row of `DSQA-full.csv` (the single `eval` split). No prompts are excluded.
- **Domains:** 17 `problem_category` values (e.g. Politics & Government, Media & Entertainment, Education, Geography, ...).
- **Answer types:** `Set Answer` (~65%, an exhaustive list of entities) and `Single Answer`.
- **Source:** [huggingface.co/datasets/google/deepsearchqa](https://huggingface.co/datasets/google/deepsearchqa) (Apache-2.0); leaderboard on [Kaggle](https://www.kaggle.com/benchmarks/google/dsqa/leaderboard); paper [arXiv:2601.20975](https://arxiv.org/abs/2601.20975).
- **Main adaptation:** the original harness passes the raw prompt to a model and grades its final response. Here the agent receives the same prompt in `instruction.md` plus a short footer asking it to write its final answer to `/workspace/answer.txt`; that file is graded with the official autorater prompt and metrics.

## What is DeepSearchQA?

DeepSearchQA evaluates deep research agents on difficult multi-step information-seeking tasks over the open web. Each prompt is a causal chain of lookups, and most answers are *sets* that must be found exhaustively, so the benchmark measures both comprehensiveness (recall) and precision (not hedging with extra candidates).

Scoring in the original benchmark: an LLM autorater (**Gemini 2.5 Flash**, zero-shot, with the prompt from the official Kaggle starter notebook) returns, for each gold item, whether the response contains it, plus a list of excessive answers. Per prompt:

- precision = found / (found + excessive), recall = found / |gold|, **F1** = harmonic mean (primary metric, averaged over prompts);
- outcome categories: **Fully Correct** (S = G), **Fully Incorrect** (S ∩ G = ∅), **Partially Correct**, **Correct with Extraneous Answers** (G ⊂ S).

## Adapter Features

- **Data loading:** downloads `DSQA-full.csv` from Hugging Face with the Python standard library (no third-party deps); `--source-csv` accepts a local copy. Honors `HF_TOKEN` if set.
- **Stable task IDs:** `deepsearchqa-000` … `deepsearchqa-899` from CSV row order; `task.toml` name is `google/deepsearchqa__<NNN>`.
- **Answer type is hidden** from the agent (as the dataset card requires); it is only in `tests/ground_truth.json`, which is not visible during the agent phase.
- **Official grader:** `tests/grade.py` embeds the official autorater prompt verbatim and computes per-prompt precision / recall / F1 and the four outcome categories.
- **Multi-metric reward:** `/logs/verifier/reward.json` contains `reward` (= F1), `f1`, `precision`, `recall`, `fully_correct`, `fully_incorrect`, `partially_correct`, `correct_with_extraneous`. Full judge output is saved to `/logs/verifier/grading_details.json`.
- **Judge backends (stdlib HTTP):** Gemini API by default (`GEMINI_API_KEY`, model `gemini-2.5-flash`); any OpenAI-compatible endpoint if `DSQA_JUDGE_MODEL` is a non-Gemini model (`OPENAI_API_KEY`, optional `OPENAI_BASE_URL`). Lenient JSON parsing (code fences, trailing commas) and up to 4 retries with backoff.
- **Fail loudly on judge errors:** if the judge cannot be reached or returns unparseable output after retries, no reward file is written, so the trial shows as an error (resumable) rather than a silent 0.
- **Oracle without API cost:** a response identical to the gold answer (case/punctuation/whitespace-insensitive) is scored as fully correct without calling the judge. Disable with `DSQA_EXACT_MATCH_SHORTCUT=0`.
- **Parity split:** `--split parity` generates a deterministic subset (default 100 prompts, seed 42) stratified by `problem_category` × `answer_type`.
- **Internet access:** tasks use Harbor's default public network so agents can search and browse.

## Generated Task Structure

```
deepsearchqa/
├── deepsearchqa-000/
│   ├── task.toml                 # name, authors, keywords, timeouts, judge env
│   ├── instruction.md            # original prompt + answer-file footer
│   ├── environment/
│   │   └── Dockerfile            # python:3.12-slim + curl
│   ├── solution/
│   │   └── solve.sh              # oracle: writes the gold answer to /workspace/answer.txt
│   └── tests/
│       ├── test.sh               # runs grade.py
│       ├── grade.py              # official autorater prompt + P/R/F1
│       └── ground_truth.json     # problem, gold answer, answer_type, category
└── ...
```

Adapter code:

```
src/deepsearchqa/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_deepsearchqa.yaml
└── src/deepsearchqa/
    ├── __init__.py
    ├── adapter.py
    ├── main.py
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/Dockerfile
        ├── solution/solve.sh
        └── tests/{test.sh, grade.py}
```

## Run Evaluation / Harness

### Running with the registry (after the dataset is published)

```bash
export GEMINI_API_KEY=...            # judge (not needed for the oracle)
harbor run -d google/deepsearchqa                        # oracle
harbor run -d google/deepsearchqa -a <agent> -m "<model>"
harbor run -d google/deepsearchqa@parity -a <agent> -m "<model>"   # parity subset
```

### Using the job configuration

```bash
harbor run -c src/deepsearchqa/run_deepsearchqa.yaml
```

The config defaults to the oracle agent; uncomment an agent block to switch.

### Using a locally prepared dataset

```bash
harbor run -p datasets/deepsearchqa                        # oracle
harbor run -p datasets/deepsearchqa -a <agent> -m "<model>"
harbor job resume -p jobs/<job-dir>                        # resume (e.g. after judge errors)
```

### Running an individual trial

```bash
harbor trial start -p datasets/deepsearchqa/deepsearchqa-000
harbor trial start -p datasets/deepsearchqa/deepsearchqa-000 -a <agent> -m "<model>"
```

Use the mean of `reward` (F1) as the headline score; also report the mean of `fully_correct`, as the Kaggle leaderboard does.

## Usage: Create Task Directories

```bash
cd src/deepsearchqa
uv run deepsearchqa --output-dir ../../datasets/deepsearchqa
```

Flags:

- `--output-dir` — where tasks are written (default `datasets/deepsearchqa`)
- `--limit N` — first N tasks only
- `--overwrite` — replace existing task directories
- `--task-ids ...` — specific tasks (`deepsearchqa-007`, `007` or `7`)
- `--split {full,parity}` — all 900 prompts, or the stratified parity subset
- `--parity-size N`, `--parity-seed S` — parity subset size (default 100) and seed (default 42)
- `--source-csv PATH` — use a local `DSQA-full.csv` instead of downloading

## Comparison with Original Benchmark (Parity)

Parity has not been run yet. The plan (agents, model, number of runs, subset size) will be agreed with the Harbor team before running; results will be recorded here and in `parity_experiment.json` as mean ± sample SEM.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| TBD | TBD | F1 | TBD | TBD | TBD | TBD |

Oracle: 900/900 tasks at `reward` = 1.0, 0 exceptions (`harbor run -c src/deepsearchqa/run_deepsearchqa.yaml`, harbor 0.25.0). Note that every oracle trial is graded via the exact-match shortcut, so the oracle run does not exercise the LLM autorater.

Links:
- Original benchmark: https://www.kaggle.com/benchmarks/google/dsqa/leaderboard
- Dataset: https://huggingface.co/datasets/google/deepsearchqa
- Adapter PR: https://github.com/harbor-framework/adapters/pull/127
- Dataset PR: TBD
- Parity experiment PR: TBD

### Reproduction

Original side: TBD (fork with a Harbor-compatible agent, grading with the same autorater prompt and Gemini 2.5 Flash).

Harbor side:

```bash
cd src/deepsearchqa && uv run deepsearchqa --split parity --output-dir ../../datasets/deepsearchqa-parity
harbor run -p datasets/deepsearchqa-parity -a <agent> -m "<model>"
```

## Notes & Caveats

- **Output file instead of chat response.** The original harness grades a model's final chat response. CLI agents in Harbor do not return a single response, so the instruction adds a footer asking for the final answer in `/workspace/answer.txt` and noting that missing and extra items both lower the score. The prompt itself is unchanged. Any parity run must use the same footer on the original side.
- **Answer type hidden.** As required by the dataset card, `answer_type` is never shown to the agent; it is passed only to the autorater.
- **Single-answer hedging.** The paper says that for Single Answer prompts, returning several candidates counts as a failure. The official autorater prompt and F1 formula (which this adapter reproduces) give partial F1 in that case (e.g. 1 correct + 1 extra → F1 0.667); `correct_with_extraneous` flags these cases, and `fully_correct` treats them as failures.
- **Empty answers** (no file or empty file) score 0 on all metrics and count as `fully_incorrect`. Some third-party harnesses exclude empty responses from the F1 mean instead.
- **Judge model matters.** The dataset card warns that a different autorater or prompt can change results significantly. Use `gemini-2.5-flash` for comparability; other models (via `DSQA_JUDGE_MODEL`) are for convenience only.
- **Exact-match shortcut.** Responses that equal the gold answer after normalization skip the judge and get F1 = 1. The autorater would grade such responses as fully correct; set `DSQA_EXACT_MATCH_SHORTCUT=0` to always call the judge.
- **Web drift.** Answers reflect the web when the benchmark was built; later web changes can make some answers stale for live-search agents. This is inherent to the original benchmark.
- **Timeouts.** Agent timeout is 3600 s per task; verifier timeout is 600 s to allow for judge retries.

## Installation / Prerequisites

- Docker installed and running
- Harbor CLI: `uv tool install harbor`
- `uv` for the adapter package (no third-party dependencies): `cd src/deepsearchqa && uv sync`
- Network access to `huggingface.co` to download `DSQA-full.csv` (or pass `--source-csv`)
- API keys:
  - `GEMINI_API_KEY` — autorater (default `gemini-2.5-flash`); not needed for the oracle
  - optional `DSQA_JUDGE_MODEL` + `OPENAI_API_KEY` (+ `OPENAI_BASE_URL`) for an OpenAI-compatible judge
  - the agent's own model key(s)

## Troubleshooting

- **Trials error with "judge failed, no reward written"**: `GEMINI_API_KEY` is missing or the judge API failed. Check `/logs/verifier/grading_details.json` in the trial directory, fix the key, then `harbor job resume -p jobs/<job-dir>`.
- **Download fails (HTTP 401/403)**: set `HF_TOKEN`, or download `DSQA-full.csv` manually and use `--source-csv`.
- **Tasks are skipped**: existing task directories are kept unless `--overwrite` is passed.
- **Using a different judge**: `export DSQA_JUDGE_MODEL=gpt-5-mini OPENAI_API_KEY=...` (any non-Gemini model name routes to the OpenAI-compatible client).

## Citation

```bibtex
@misc{gupta2026deepsearchqa,
  title={DeepSearchQA: Bridging the Comprehensiveness Gap for Deep Research Agents},
  author={Nikita Gupta and Riju Chatterjee and Lukas Haas and Connie Tao and Andrew Wang and Chang Liu and Hidekazu Oiwa and Elena Gribovskaya and Jan Ackermann and John Blitzer and Sasha Goldshtein and Dipanjan Das},
  year={2026},
  eprint={2601.20975},
  archivePrefix={arXiv},
  primaryClass={cs.CL},
  url={https://arxiv.org/abs/2601.20975},
}
```

## Authors & Contributions

This adapter is developed and maintained by [Erin Wang](mailto:erinwang27y@gmail.com).

**Issues and Contributions:**
- Submit issues and pull requests to the [harbor-framework/adapters](https://github.com/harbor-framework/adapters) repository.
