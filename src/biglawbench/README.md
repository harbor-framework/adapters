## BigLawBench → Harbor Adapter

## Overview

BigLaw Bench (BLB) by Harvey evaluates LLMs/agents on real-world legal work product (transactional and litigation tasks drawn from billable-time entries and Share Purchase Agreements). This adapter covers **all 16 publicly adaptable tasks** from https://github.com/harveyai/biglaw-bench (pinned to commit `138fd481b459a00bbd98eeb710f69ada1052bd47`):

- **BLB-Core (6 tasks):** `blb-core-004`, `blb-core-005`, `blb-core-019`, `blb-core-049`, `blb-core-060`, `blb-core-096` (from `blb-core/core-samples.csv`).
- **BLB-Workflows SPA (10 tasks):** `blb-spa-001` through `blb-spa-010` (from `blb-workflows/spa/spa-samples.csv`, `schema.json`, and 10 SPA PDFs).

**Excluded:** `blb-retrieval` (30 retrieval queries over contracts and discovery emails with no gold labels in the repository) and the private full BLB datasets.

## What is BigLawBench?

"A new standard for evaluating AI on legal & professional tasks" (Harvey, 2024). See https://www.harvey.ai/blog/introducing-biglaw-bench.
- **BLB-Core:** Each task has a rubric of affirmative points (`Does the response state X? (1 point)`) and negative points (`-1` per hallucination, `-0.5` per extraneous statement). Answer score = `(met points - penalties) / total affirmative points`, clamped to `[0, 1]`.
- **BLB-Workflows SPA:** Structured deal-point extraction from Share Purchase Agreements (SPAs) into a 29-field JSON schema (`schema.json`) evaluated against human-curated ground truth in `spa-samples.csv`.

## Adapter Features

- Fetches `core-samples.csv` and `spa-samples.csv` from the pinned upstream commit at generation time, while generated `Dockerfile`s `curl` each task's PDFs (and `/app/schema.json` for SPA tasks) directly from the pinned commit at `docker build` time; **no upstream PDFs or CSVs are committed to `adapters` or `harbor-datasets`**.
- Task IDs: `blb-core-004`, ..., `blb-core-096` and `blb-spa-001`, ..., `blb-spa-010`; task names `harvey/biglawbench__blb-core-XXX` and `harvey/biglawbench__blb-spa-XXX`.
- **Separate verifier isolation:** Tasks declare `artifacts` (`/app/answer.md` or `/app/answer.json`) and `[verifier].environment_mode = "separate"`, keeping the agent and verifier phases isolated (`harbor lint` clean).
- **Verifier (`tests/judge.py`, stdlib-only):**
  - `--mode core`: LLM-as-judge over an OpenAI-compatible chat-completions endpoint grading affirmative rubric criteria (`true`/`false`) and negative item counts.
  - `--mode spa`: Scores all 29 deal-point fields against `tests/ground_truth.json` using deterministic normalization (dates, currency, N/A equivalences, party `{name, entity_type, jurisdiction}` tokens, and unordered list matching) with a batched LLM-judge semantic-equivalence fallback for free-text legal clauses. Reward = `matched_fields / 29`.
- **Oracle:**
  - `blb-core`: Authored rubric-satisfying legal work products in `src/biglawbench/solutions/` (or `reference_answer()` fallback) copied to `/app/answer.md` by `solution/solve.sh`.
  - `blb-spa`: Ground-truth JSON in `solution/answer.json` parsed from `spa-samples.csv` and copied to `/app/answer.json` by `solution/solve.sh`.

## Generated Task Structure

```
biglawbench/
├── blb-core-004/
│   ├── task.toml
│   ├── instruction.md
│   ├── environment/Dockerfile    # fetches upstream PDFs at build time
│   ├── solution/{solve.sh, answer.md}
│   └── tests/{test.sh, judge.py, rubric.md}
├── blb-spa-001/
│   ├── task.toml
│   ├── instruction.md
│   ├── environment/Dockerfile    # fetches upstream PDF + schema.json at build time
│   ├── solution/{solve.sh, answer.json}
│   └── tests/{test.sh, judge.py, ground_truth.json}
```

## Run Evaluation / Harness

Judge configuration is read from the environment via `[verifier.env]`:

```bash
export JUDGE_API_KEY=...                          # required for core tasks and SPA semantic fallback
export JUDGE_BASE_URL=https://api.openai.com/v1    # OpenAI-compatible endpoint (default shown)
export JUDGE_MODEL=gpt-5-mini                     # default shown (configurable)

cd src/biglawbench
uv run biglawbench --output-dir ../../datasets/biglawbench --overwrite
harbor run -p ../../datasets/biglawbench -a oracle -n 3
harbor run -c run_biglawbench.yaml -a <agent> -m "<model>"
harbor trial start -p ../../datasets/biglawbench/blb-core-004
```

## Usage: Create Task Directories

```bash
cd src/biglawbench
uv run biglawbench --output-dir ../../datasets/biglawbench --split full --overwrite
```

Flags:
- `--split {full,core,spa}`: task split to generate (default: `full` = all 16 tasks; `core` = 6 tasks; `spa` = 10 tasks)
- `--output-dir`: directory to write generated tasks
- `--limit`: generate only the first N tasks
- `--overwrite`: overwrite existing task directories
- `--task-ids`: filter by task IDs (e.g., `blb-core-004 blb-spa-001` or `4 spa-1`)

## Comparison with Original Benchmark (Parity)

Symmetric Scenario 2 parity passed across **3 full 16-task runs** per side (`96` total trials, `0` errors) using `codex@0.159.1` with `openai/gpt-5.4` (`reasoning_effort=low`) and `JUDGE_MODEL=gpt-5.4`:
- **Original runs (`parity_runner.py`):** `[0.6153, 0.5854, 0.6042]` → **`0.6016 ± 0.0087`**
- **Harbor runs (`harbor run`):** `[0.6062, 0.6154, 0.6637]` → **`0.6284 ± 0.0178`** (`$14.78` Harbor-side agent cost; run-score ranges `[0.5854, 0.6153]` vs `[0.6062, 0.6637]` overlap cleanly per `ADP-PARITY`).

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| `codex@0.159.1` | `openai/gpt-5.4` | Mean task score | 3 | 16 (100%) | `0.6016 ± 0.0087` | `0.6284 ± 0.0178` |

```bash
# Original-side Scenario 2 parity runner (local clone)
JUDGE_MODEL=gpt-5.4 python3 parity_runner.py \
  --split full --agent codex --model openai/gpt-5.4 --reasoning-effort low \
  --concurrency 2 --runs 1 --output-dir parity_results/full_codex_gpt54_run1

# Harbor-side parity run
JUDGE_MODEL=gpt-5.4 harbor run -y -p datasets/biglawbench \
  -a codex -m openai/gpt-5.4 --ak version=0.159.1 --ak reasoning_effort=low -n 2
```

## Notes & Caveats

- Upstream has no `LICENSE` file and publishes only samples; PDFs/CSVs/schema are fetched at generation time and never committed. Confirm terms with Harvey before publishing generated datasets.
- Upstream provides no judge prompt, judge model, or SPA scoring script; both `core` and `spa` verifiers are Harbor adapter implementations and should be documented as benchmark additions.
- Endpoint note: `https://api.openai.com/v1` with `gpt-5-mini` is the default judge endpoint/model (override `JUDGE_BASE_URL` for any OpenAI-compatible gateway). The 3-run parity experiment used `JUDGE_MODEL=gpt-5.4`, and both `judge.py` and `parity_runner.py` retry judge calls up to 16 times to absorb transient HTTP 403/5xx gateway errors.
- Tasks `blb-core-049` and `blb-core-096` have no attached documents.
- In `blb-workflows/spa/spa-samples.csv`, `Conditions Precedent to Closing Transaction` combines Mutual/Buyer/Seller sections into one column while `schema.json` separates `conditions_to_sellers_obligations` and `conditions_to_buyers_obligations`; the adapter splits the column deterministically into those two arrays so all 29 deal-point fields align with `schema.json`.

## Installation / Prerequisites

- Docker Desktop, Harbor (`uv tool install harbor`), `uv sync` in `src/biglawbench`, network access to GitHub raw at generation time, and a `JUDGE_API_KEY`.

## Troubleshooting

- `judge unavailable; no reward written`: check `JUDGE_API_KEY` / `JUDGE_BASE_URL` / `JUDGE_MODEL`.

## Citation

```bibtex
@misc{harvey_biglawbench,
  title={BigLaw Bench},
  author={Pereyra, Julio and Lebens, Elizabeth and Guillod, Matthew and Toulme, Laura and others},
  year={2024},
  url={https://github.com/harveyai/biglaw-bench}
}
```

## Authors & Contributions

Adapter developed by the Harbor team. Issues and PRs go to the main repository.
