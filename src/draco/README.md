## DRACO → Harbor Adapter

## Overview

This adapter converts **DRACO** ([Zhong et al., 2026](https://arxiv.org/abs/2602.11685)) from Perplexity into Harbor task format. DRACO (Deep Research Accuracy, Completeness, and Objectivity) evaluates deep research agents on complex, open-ended research requests, grading each long-form response against expert-written, weighted rubric criteria with an LLM judge.

- **Source**: [perplexity-ai/draco](https://huggingface.co/datasets/perplexity-ai/draco) on HuggingFace (MIT), revision `ce076749`; grader library [paper-instruments/rubric](https://github.com/paper-instruments/rubric) (MIT, formerly `The-LLM-Data-Company/rubric`, the repository the paper links to), commit `eb0755a`.
- **Split**: a single split of 100 queries with 3,934 rubric criteria (16–77 per query, 415 with negative weight).
- **Domains**: Finance (20), Shopping/Product Comparison (16), Academic (12), Technology (10), General Knowledge (9), UX Design (9), Law (6), Medicine (6), Needle in a Haystack (6), Personalized Assistant (6).
- **Task type**: open-ended web research producing a Markdown report, graded by LLM-as-a-judge.
- **This adapter produces 100 tasks**, one per upstream `id`, with no exclusions.
- **Main adaptation**: the upstream query is passed through verbatim, with a short suffix telling the agent to write its report to `/app/report.md`. Upstream graded responses that deep research systems produced outside any harness, so it defines no agent prompt for the benchmark itself.

## What is DRACO?

DRACO is a benchmark of 100 deep research tasks sampled from real Perplexity Deep Research queries, reformulated and filtered to remove personal information and to keep only genuinely hard requests. Each task comes with a rubric written and validated by 26 domain experts (medical professionals, attorneys, financial analysts, software engineers, designers) through multi-stage review and a saturation test. Criteria are grouped into four axes: Factual Accuracy, Breadth and Depth of Analysis, Presentation Quality, and Citation Quality. Each criterion has an integer weight; positive weights reward desirable content, negative weights (from −5 down to −500 for dangerous medical advice) penalize errors.

The original metric is the **normalized score**. An LLM judge (Gemini-3-Pro in the paper) receives the query, the response and one criterion at a time and returns MET or UNMET. The score is

```
normalized = clamp( Σ (weight_i × met_i) / Σ (positive weights), 0, 1 )
```

A MET negative criterion lowers the score. The benchmark score is the mean normalized score across tasks. The paper also reports a pass rate (positive criteria MET and negative criteria UNMET, unweighted). With the Gemini-3-Pro judge, the best system in the paper (Perplexity Deep Research on Opus 4.6) reaches 70.5%.

## Adapter Features

- Loads the dataset from a pinned HuggingFace revision (or a local `--data-file`), so tasks and task names are reproducible.
- Stable task IDs: each task directory and name uses the upstream `id` (`perplexity-ai/draco__<id>`).
- Domain, rubric slug and criterion counts (`domain`, `rubric_id`, `n_criteria`, `n_negative_criteria`) are stored in `task.toml` `[metadata]` for slicing results.
- The verifier calls the official grader library rather than re-implementing it:
  - `PerCriterionGrader` with its default system prompt and user prompt template, which match the paper's Appendix C.5 grading prompt
  - one judge call per criterion with the query, the report and the criterion type (positive or negative), binary MET / UNMET verdicts
  - the library's own aggregation for the normalized score, including the clamp to [0, 1]
  - the judge is asked for the library's `PerCriterionOutput` JSON schema, as the library's reference generate function does
- Judge defaults follow the paper's primary judge configuration (Table 16): `gemini/gemini-3-pro-preview`, thinking level low (`JUDGE_REASONING_EFFORT=low`), temperature 0.2. Any LiteLLM-supported judge can be used via `JUDGE_MODEL`, with optional `JUDGE_API_BASE` / `JUDGE_API_KEY` for proxies and `JUDGE_API_VERSION` for Azure-style gateways (`JUDGE_MODEL=azure/<deployment>`).
- Per-criterion verdicts and judge explanations are written to `/logs/verifier/rubric_results.jsonl`. `/logs/verifier/summary.json` records the normalized score, raw weighted score, pass rate, per-axis scores, the judge settings, and the model names the endpoint reported (`judge_models_served`), since a gateway may route a requested name to a different model.
- Rubrics live only in `tests/`, so the agent never sees them.

## Generated Task Structure

```
draco/
├── {id}/
│   ├── task.toml                 # Task config; domain and rubric stats in [metadata]; judge env in [verifier.env]
│   ├── instruction.md            # Upstream query + output location (/app/report.md)
│   ├── environment/
│   │   └── Dockerfile            # python:3.12-slim + litellm + rubric (grader library)
│   ├── solution/
│   │   ├── solve.sh              # Copies report.md to /app/report.md
│   │   └── report.md             # Staged oracle report
│   └── tests/
│       ├── test.sh               # Runs evaluate.py
│       ├── evaluate.py           # Calls the grader library with a LiteLLM judge; writes reward.txt
│       └── task.json             # This task's query and weighted rubric
```

Adapter code directory:

```
src/draco/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_draco.yaml
└── src/draco/
    ├── __init__.py
    ├── adapter.py
    ├── main.py
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/
        │   └── Dockerfile
        ├── solution/
        │   └── solve.sh
        └── tests/
            ├── test.sh
            └── evaluate.py
```

## Run Evaluation / Harness

Harbor Registry & Datasets makes running adapter evaluation easy and flexible. Every run except an `ORACLE_MODE=true` pipeline check calls the LLM judge in the verifier, so export the judge provider's key first (`GEMINI_API_KEY` for the default judge).

### Running with Datasets Registry

Simply run:

```bash
export GEMINI_API_KEY=...   # judge key (default judge: gemini/gemini-3-pro-preview)

# Oracle pipeline check (no judge calls; see Notes & Caveats)
ORACLE_MODE=true uvx --from harbor==0.25.0 harbor run -d perplexity-ai/draco

# Oracle graded by the real judge
uvx --from harbor==0.25.0 harbor run -d perplexity-ai/draco

# Use your specified agent and model
uvx --from harbor==0.25.0 harbor run -d perplexity-ai/draco -a <agent_name> -m "<model_name>"
```

from the adapters repository root to evaluate on the entire dataset.

However, if you choose to prepare the task directories locally and/or with custom versions/subsets for evaluation, you may either use `harbor run` or `harbor trial`. Instructions for using the adapter code to prepare task directories are provided in the [Usage](#usage-create-task-directories) section.

### Using Job Configurations

The example configuration file for the adapter is provided at `src/draco/run_draco.yaml`.

```bash
# From the repository root
# Run a job with the default adapter configuration
uvx --from harbor==0.25.0 harbor run -c src/draco/run_draco.yaml -a <agent_name> -m "<model_name>"

# Or run a job without configuration yaml but instead with locally prepared dataset path
uvx --from harbor==0.25.0 harbor run -p datasets/draco -a <agent_name> -m "<model_name>"

# Use a different judge, e.g. the paper's GPT-5.2 configuration (reasoning effort none, temperature 0)
JUDGE_MODEL=openai/gpt-5.2 JUDGE_REASONING_EFFORT=none JUDGE_TEMPERATURE=0 OPENAI_API_KEY=... \
  uvx --from harbor==0.25.0 harbor run -p datasets/draco -a <agent_name> -m "<model_name>"

# Resume a previously started job
uvx --from harbor==0.25.0 harbor job resume -p /path/to/jobs/directory
```

Results are saved in the `jobs/` directory by default (configurable via `jobs_dir` in the YAML config).

### Running Individual Trial

For quick testing or debugging a single task:

```bash
# Run a single task with oracle (pipeline check, no judge calls)
ORACLE_MODE=true uvx --from harbor==0.25.0 harbor trial start -p datasets/draco/<id>

# Run a single task with a specific agent and model
uvx --from harbor==0.25.0 harbor trial start -p datasets/draco/<id> -a <agent_name> -m "<model_name>"
```

Trial outputs are saved in the `trials/` directory by default (configurable via `--trials-dir`).

## Usage: Create Task Directories

```bash
cd src/draco
uv sync
uv run draco --output-dir ../../datasets/draco
```

Available flags:
- `--output-dir`: directory to write generated tasks to (defaults to `datasets/draco` at the repo root)
- `--limit`: generate only the first N tasks (sorted by `id`)
- `--overwrite`: overwrite existing tasks
- `--task-ids`: only generate these `id`s
- `--data-file`: use a local `test.jsonl` instead of downloading the pinned HF revision
- `--oracle-reports-dir`: stage `<id>.md` files from this directory as oracle reports (see Notes & Caveats)

Tasks are written to `datasets/draco/` with one directory per task. Each task follows the structure shown in ["Generated Task Structure"](#generated-task-structure) above.

## Comparison with Original Benchmark (Parity)

Parity has not been run yet. The plan (agents, models, number of runs, judge model) will be agreed with the Harbor team before any runs.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| TBD | TBD | Normalized score | TBD | 100 tasks (100% of full set) | TBD | TBD |

Planned reproduction:

- **Original side**: upstream ships no runner, only the dataset and the grader library. Produce one `<id>.md` response per query with the agent under test outside Harbor, then grade them with `PerCriterionGrader` from [paper-instruments/rubric](https://github.com/paper-instruments/rubric) at commit `eb0755a` and the same judge settings. The scripts for this side will live in a fork and be linked here.
- **Harbor side**:
  ```bash
  uvx --from harbor==0.25.0 harbor run -c src/draco/run_draco.yaml -a <agent> -m "<model>"
  ```
- **Metric**: the mean of per-task `reward` is the benchmark's average normalized score (0 to 1; the paper reports it as a percentage).

## Notes & Caveats

- **LLM judge required**: every verification calls the judge once per criterion (about 39 calls per task and 3,934 per full run), so judge cost scales with report length.
- **Judge model and settings**: the paper's primary judge is Gemini-3-Pro with thinking level low and temperature 0.2 (Table 16); the adapter uses these by default. The library's own reference generate function instead calls `gemini-3-pro-preview` at temperature 0 with no thinking setting; the adapter follows the paper. LiteLLM maps `JUDGE_REASONING_EFFORT=low` to Gemini 3's `thinkingLevel: low`; its warning about temperatures below 1.0 on Gemini 3 is expected here. The paper notes that absolute scores vary across judges (Table 15) while rankings stay stable, so parity must use the same judge and settings on both sides, and `judge_models_served` in `summary.json` should be checked to confirm which model actually graded.
- **Judge prompt version**: the grader library is installed from GitHub at commit `eb0755a` rather than from PyPI. The PyPI release (`rubric==2.2.0`) asks the judge for the verdict before the explanation; the paper's Appendix C.5 prompt, and the library from commit `fd34de1` onward, ask for the explanation first. Two small wording differences remain between the PDF and the library prompt ("strict about factual accuracy **and** flexible about wording" in the PDF versus "**but**" in the library, and one example criterion reading "base margin 17.2%" versus "base margin as 17.2%"); the library prompt is used unchanged.
- **Oracle**: DRACO ships no reference reports, so oracle validation has two parts (the plan is to be confirmed with the Harbor team):
  1. **Pipeline check, `ORACLE_MODE=true`** (same approach as the clbench adapter). The verifier confirms that `/app/report.md` was written and non-empty and that the task's rubric loads, then writes reward 1.0 without calling the judge. This is expected to give 100% on all 100 tasks at no judge cost. It validates the environment, solution and verifier wiring only, **not** grading correctness. Never set `ORACLE_MODE` for agent runs.
  2. **Grading check, real judge.** Run the oracle with `ORACLE_MODE` unset to grade the staged reports with the LLM judge. By default, `solution/report.md` is a rubric-derived report that restates each task's positive criteria under their axis. Pass `--oracle-reports-dir` to stage real reports instead, for example the best agent report per task from parity runs. Judge scores are not deterministic and are not expected to reach 1.0. Measured on all 100 tasks with the default rubric-derived reports, judged by `gpt-5.2-2025-12-11` with the paper's GPT-5.2 settings (`JUDGE_REASONING_EFFORT=none`, `JUDGE_TEMPERATURE=0`; confirmed in `judge_models_served`): 3,934/3,934 criteria graded, mean reward 0.741 (median 0.789, range 0.054 to 0.980), mean pass rate 0.768. Four tasks first hit the judge endpoint's per-minute rate limit and were re-run at lower concurrency. The score is high because many DRACO criteria are phrased as statements ("States X"), so restating them reads as content; GPT-5.2 still marks a criterion UNMET when the report only lists it as a requirement.
- **Judge failures**: each judge call is retried up to `JUDGE_MAX_ATTEMPTS` times (default 5) with exponential backoff, and a response that is not bare JSON is parsed from the first `{...}` block. The library has no fallback for a criterion that cannot be graded, and dropping or zeroing one would change the score, so if any criterion still fails the verifier exits non-zero without writing a reward.
- **Reward range**: the reward is the clamped normalized score in [0, 1], as in the paper. The unclamped weighted sum is kept as `raw_score` in `summary.json`.
- **Empty reports**: a missing or empty `/app/report.md` scores 0.0 without calling the judge. Graded by the judge, it would have every positive criterion UNMET and the same clamped score of 0.
- **Agent prompt**: the paper's Appendix C.4 system prompt is specific to its Claude Opus baseline (server-side web search and code execution tools, and an "Exact Answer / Confidence" answer format); it is not part of the benchmark and is not used. Agents receive the query verbatim plus the output-location suffix.
- **Long reports**: each judge call carries the whole report. The default judge has a 1M-token context, so no chunking is needed; with a smaller-context judge, very long reports may fail.
- **Time-sensitive queries**: rubrics reflect information available when the benchmark was built (late 2025), and web content changes over time, so scores can drift between runs on different dates.
- **Web access**: agents need internet access (`network_mode = "public"`) and a web search/fetch capability.

## Installation / Prerequisites

Adapters are managed as standalone uv Python packages. You can add or remove dependencies using `uv add` / `uv remove` from the adapter directory:

```bash
cd src/draco
uv add <package>     # add a dependency
uv remove <package>  # remove a dependency
```

- Docker installed and running
- Harbor (commands above use `uvx --from harbor==0.25.0`)
- Python 3.13+ with `uv` for task generation:
  ```bash
  cd src/draco
  uv sync
  ```
- API keys (export as environment variables):
  - Judge: `GEMINI_API_KEY` for the default judge, or the key for whichever provider `JUDGE_MODEL` points at (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), or `JUDGE_API_KEY` + `JUDGE_API_BASE` for a LiteLLM proxy (plus `JUDGE_API_VERSION` and an `azure/<deployment>` model id for an Azure-style gateway)
  - Agent: model keys as needed by your agent

## Troubleshooting

- **`RewardFileNotFoundError` / verifier exit code 1**: at least one criterion could not be graded after all retries, usually a missing judge key, a bad `JUDGE_MODEL`, or a rate limit. Judge errors are in the verifier stdout.
- **`UnsupportedParamsError` for `temperature` or `reasoning_effort`**: the judge does not accept that setting. Export it as an empty string (e.g. `JUDGE_REASONING_EFFORT=`) to leave it unset.
- **Judge rate limits**: lower `JUDGE_MAX_CONCURRENT` (default 20) or `n_concurrent_trials`.
- **Verifier timeout**: reports with many criteria can take minutes. `[verifier].timeout_sec` is 1800.
- **HF download fails behind a corporate proxy**: download `test.jsonl` manually and pass `--data-file`.

## Citation

```bibtex
@misc{draco2026,
  title={DRACO: A Cross-Domain Benchmark for Deep Research Accuracy, Completeness, and Objectivity},
  author={Joey Zhong and Hao Zhang and Clare Southern and Jeremy Yang and Thomas Wang and Kate Jung and Shu Zhang and Denis Yarats and Johnny Ho and Jerry Ma},
  year={2026},
  url={https://arxiv.org/abs/2602.11685}
}
```

## Authors & Contributions
This adapter is developed and maintained by [Jianing Yin](mailto:jianingyin@alumni.upenn.edu).

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines

## Acknowledgement

If you used API keys provided via [parity_api_instructions.md](../parity_api_instructions.md) for running parity experiments, please include the following acknowledgement:

> API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
