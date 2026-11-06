## ResearchRubrics → Harbor Adapter

## Overview

This adapter converts **ResearchRubrics** ([Sharma et al., 2025](https://arxiv.org/abs/2511.07685), ICLR 2026) from Scale AI into Harbor task format. ResearchRubrics evaluates deep research (DR) agents on open-ended research requests, grading each long-form report against expert-written, weighted rubric criteria with an LLM judge.

- **Source**: [ScaleAI/researchrubrics](https://huggingface.co/datasets/ScaleAI/researchrubrics) on HuggingFace (MIT), revision `85de3115`; grading code at [scaleapi/researchrubrics](https://github.com/scaleapi/researchrubrics) (MIT), commit `2dc80e2`.
- **Split**: a single split of 101 prompts with 2,593 rubric criteria (20–43 per prompt).
- **Domains**: AI & ML (17), Historical Analysis (13), Business Planning & Research (12), Technical Documentation (12), General Consumer Research (11), Hypotheticals & Philosophy (11), STEM (8), Creative Writing (6), Other (6), Current Events (5).
- **Task type**: open-ended web research producing a Markdown report, graded by LLM-as-a-judge.
- **This adapter produces 101 tasks**, one per upstream `sample_id`, with no exclusions.
- **Main adaptation**: the upstream prompt is passed through verbatim, with a short suffix telling the agent to write its report to `/app/report.md`. Upstream grades reports that DR systems produced outside any harness, so it defines no agent prompt of its own.

## What is ResearchRubrics?

ResearchRubrics is a benchmark for deep research agents, built with 2,800+ hours of expert annotation. Each prompt comes with fine-grained rubric criteria grouped into six axes: Explicit Criteria, Implicit Criteria, Synthesis of Information, References & Citation Quality, Communication Quality, and Instruction Following. Each criterion has a weight from −5 to +5 (plus one +10 and one 0 in the released data). Negative weights penalize undesirable content such as hallucinations or off-topic material. Prompts are also tagged along three complexity axes: conceptual breadth, logical nesting, and exploration.

The original metric is the **rubric compliance score**. An LLM judge (Gemini 2.5 Pro in the released code) grades each criterion as Satisfied (1.0) or Not Satisfied (0.0). The score is

```
compliance = Σ (weight_i × score_i) / Σ (positive weights)
```

Negative-weight criteria appear only in the numerator, so a satisfied negative criterion lowers the score. The benchmark score is the mean compliance across prompts. The paper reports that leading DR systems (Gemini Deep Research, OpenAI Deep Research) reach under 68% average compliance.

## Adapter Features

- Loads the dataset from a pinned HuggingFace revision (or a local `--data-file`), so tasks and task names are reproducible.
- Stable task IDs: each task directory and name uses the upstream `sample_id` (`scaleai/researchrubrics__<sample_id>`).
- Complexity and domain tags (`domain`, `conceptual_breadth`, `logical_nesting`, `exploration`, `n_rubrics`) are stored in `task.toml` `[metadata]` for slicing results.
- The verifier is a faithful port of the upstream evaluator:
  - the four upstream prompt templates are copied verbatim into `tests/prompts/`
  - one judge call per rubric, binary grading, JSON response format, `max_tokens=50000`, three attempts with exponential backoff, 20 concurrent calls
  - reports over 150k estimated tokens use the upstream chunk + synthesis path
  - a rubric that still fails after retries scores 0.0, as upstream
- Any LiteLLM-supported judge can be used via `JUDGE_MODEL` (default `gemini/gemini-2.5-pro`), with optional `JUDGE_API_BASE` / `JUDGE_API_KEY` for proxies and `JUDGE_API_VERSION` for Azure-style gateways (`JUDGE_MODEL=azure/<deployment>`).
- Per-rubric verdicts, judge reasoning and a summary are written to `/logs/verifier/rubric_results.jsonl` and `/logs/verifier/summary.json`. Both record the model name the endpoint reported for each judgement (`judge_model_served` / `judge_models_served`), since a gateway may route a requested name to a different model.
- Rubrics live only in `tests/`, so the agent never sees them.

## Generated Task Structure

```
researchrubrics/
├── {sample_id}/
│   ├── task.toml                 # Task config; complexity tags in [metadata]; judge env in [verifier.env]
│   ├── instruction.md            # Upstream prompt + output location (/app/report.md)
│   ├── environment/
│   │   └── Dockerfile            # python:3.12-slim + litellm (judge client)
│   ├── solution/
│   │   ├── solve.sh              # Copies report.md to /app/report.md
│   │   └── report.md             # Staged oracle report
│   └── tests/
│       ├── test.sh               # Runs evaluate.py
│       ├── evaluate.py           # Upstream rubric evaluator port; writes reward.txt
│       ├── rubrics.json          # This task's weighted rubric criteria
│       └── prompts/              # Upstream judge prompts (verbatim)
```

Adapter code directory:

```
src/researchrubrics/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_researchrubrics.yaml
└── src/researchrubrics/
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
            ├── evaluate.py
            └── prompts/
```

## Run Evaluation / Harness

Harbor Registry & Datasets makes running adapter evaluation easy and flexible. Every run except an `ORACLE_MODE=true` pipeline check calls the LLM judge in the verifier, so export the judge provider's key first (`GEMINI_API_KEY` for the default judge).

### Running with Datasets Registry

Simply run:

```bash
export GEMINI_API_KEY=...   # judge key (default judge: gemini/gemini-2.5-pro)

# Oracle pipeline check (no judge calls; see Notes & Caveats)
ORACLE_MODE=true uvx --from harbor==0.23.0 harbor run -d scaleai/researchrubrics

# Oracle graded by the real judge
uvx --from harbor==0.23.0 harbor run -d scaleai/researchrubrics

# Use your specified agent and model
uvx --from harbor==0.23.0 harbor run -d scaleai/researchrubrics -a <agent_name> -m "<model_name>"
```

from the adapters repository root to evaluate on the entire dataset.

However, if you choose to prepare the task directories locally and/or with custom versions/subsets for evaluation, you may either use `harbor run` or `harbor trial`. Instructions for using the adapter code to prepare task directories are provided in the [Usage](#usage-create-task-directories) section.

### Using Job Configurations

The example configuration file for the adapter is provided at `src/researchrubrics/run_researchrubrics.yaml`.

```bash
# From the repository root
# Run a job with the default adapter configuration
uvx --from harbor==0.23.0 harbor run -c src/researchrubrics/run_researchrubrics.yaml -a <agent_name> -m "<model_name>"

# Or run a job without configuration yaml but instead with locally prepared dataset path
uvx --from harbor==0.23.0 harbor run -p datasets/researchrubrics -a <agent_name> -m "<model_name>"

# Use a different judge (any LiteLLM model id)
JUDGE_MODEL=openai/gpt-4.1 JUDGE_MAX_TOKENS=32768 OPENAI_API_KEY=... \
  uvx --from harbor==0.23.0 harbor run -p datasets/researchrubrics -a <agent_name> -m "<model_name>"

# Resume a previously started job
uvx --from harbor==0.23.0 harbor job resume -p /path/to/jobs/directory
```

Results are saved in the `jobs/` directory by default (configurable via `jobs_dir` in the YAML config).

### Running Individual Trial

For quick testing or debugging a single task:

```bash
# Run a single task with oracle (pipeline check, no judge calls)
ORACLE_MODE=true uvx --from harbor==0.23.0 harbor trial start -p datasets/researchrubrics/<sample_id>

# Run a single task with a specific agent and model
uvx --from harbor==0.23.0 harbor trial start -p datasets/researchrubrics/<sample_id> -a <agent_name> -m "<model_name>"
```

Trial outputs are saved in the `trials/` directory by default (configurable via `--trials-dir`).

## Usage: Create Task Directories

```bash
cd src/researchrubrics
uv sync
uv run researchrubrics --output-dir ../../datasets/researchrubrics
```

Available flags:
- `--output-dir`: directory to write generated tasks to (defaults to `datasets/researchrubrics` at the repo root)
- `--limit`: generate only the first N tasks (sorted by `sample_id`)
- `--overwrite`: overwrite existing tasks
- `--task-ids`: only generate these `sample_id`s
- `--data-file`: use a local `processed_data.jsonl` instead of downloading the pinned HF revision
- `--oracle-reports-dir`: stage `<sample_id>.md` files from this directory as oracle reports (see Notes & Caveats)

Tasks are written to `datasets/researchrubrics/` with one directory per task. Each task follows the structure shown in ["Generated Task Structure"](#generated-task-structure) above.

## Comparison with Original Benchmark (Parity)

Parity has not been run yet. The plan (agents, models, number of runs, judge model) will be agreed with the Harbor team before any runs.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| TBD | TBD | Rubric compliance score | TBD | 101 tasks (100% of full set) | TBD | TBD |

Planned reproduction:

- **Original side**: produce one `<sample_id>.md` report per prompt with the agent under test, place them in `agent_responses/` of [scaleapi/researchrubrics](https://github.com/scaleapi/researchrubrics) at commit `2dc80e2`, then run `src/evaluate_rubrics/evaluate_reports_batch.py` and `src/calculate_metrics/calculate_compliance_score.py` with the same judge model.
- **Harbor side**:
  ```bash
  uvx --from harbor==0.23.0 harbor run -c src/researchrubrics/run_researchrubrics.yaml -a <agent> -m "<model>"
  ```
- **Metric**: the mean of per-task `reward` is the benchmark's average compliance score. Rewards can be negative for reports that satisfy many negative-weight criteria.

## Notes & Caveats

- **LLM judge required**: every verification calls the judge once per rubric (about 26 calls per task and 2,593 per full run), so judge cost scales with report length. The released code estimates $0.01–$0.05 per call with Gemini 2.5 Pro.
- **Judge model**: upstream hardcodes the dated preview `gemini-2.5-pro-preview-06-05` behind a LiteLLM proxy (`litellm_proxy/...`). The adapter defaults to `gemini/gemini-2.5-pro`, the GA release of the same model, called directly. As of October 2026 Google no longer serves the 2.5 models to new API users (existing users keep access), so new accounts may need a different judge or a gateway that still serves 2.5 Pro. Any LiteLLM id works via `JUDGE_MODEL`. Parity must use the same judge on both sides, and `judge_models_served` in `summary.json` should be checked to confirm which model actually graded.
- **Oracle**: ResearchRubrics ships no reference reports, so oracle validation has two parts (the plan is to be confirmed with the Harbor team):
  1. **Pipeline check, `ORACLE_MODE=true`** (same approach as the clbench adapter). The verifier confirms that `/app/report.md` was written and non-empty and that the task's rubrics load, then writes reward 1.0 without calling the judge. This is expected to give 100% on all 101 tasks at no judge cost. It validates the environment, solution and verifier wiring only, **not** grading correctness. Never set `ORACLE_MODE` for agent runs.
  2. **Grading check, real judge.** Run the oracle with `ORACLE_MODE` unset to grade the staged reports with the LLM judge. By default, `solution/report.md` is a rubric-derived report that restates each task's positive criteria. Pass `--oracle-reports-dir` to stage real reports instead, for example the best agent report per task from parity runs. Judge scores are not deterministic and are not expected to reach 1.0. Measured on all 101 tasks with the default rubric-derived reports, judged by `gemini-2.5-pro` (as reported in `judge_models_served`): 2,593/2,593 rubrics graded, 0 judge errors, 0 trial exceptions, mean reward 0.210 (median 0.132, range −0.125 to 0.750, 6 tasks below 0). The low score is expected: these reports restate the criteria instead of doing the research, and the judge marks most content criteria as not met.
- **Negative rewards**: the reward is the upstream compliance score, unclamped. A report that satisfies more negative-weight criteria than positive ones scores below 0.
- **JSON mode through Azure-style gateways**: LiteLLM drops `response_format` for Azure deployments it does not recognize (e.g. a Gemini model behind an Azure-style gateway), and the judge then wraps its JSON in a Markdown fence that upstream's `json.loads` rejects. The verifier passes `allowed_openai_params=["response_format"]` so the setting is always sent. Parsing is unchanged from upstream.
- **Judge failures**: as upstream, a rubric whose judge call fails three times scores 0.0. If *every* judge call for a task fails (usually a missing key or a bad model id), the verifier exits non-zero without writing a reward, so a configuration error does not show up as a score of 0.
- **Empty reports**: a missing or empty `/app/report.md` scores 0.0. Upstream skips reports it cannot load, which has the same effect on the mean.
- **Context limit**: chunking triggers above 150k estimated tokens (600k characters), as in upstream, which assumes Gemini 2.5 Pro's context window. With a smaller-context judge, very long reports may fail. Set `JUDGE_MAX_TOKENS` below the judge's output limit for non-Gemini judges.
- **Time-sensitive prompts**: some prompts (e.g. Current Events) refer to dated events, and web content changes over time, so scores can drift between runs on different dates.
- **Web access**: agents need internet access (`network_mode = "public"`) and a web search/fetch capability.

## Installation / Prerequisites

Adapters are managed as standalone uv Python packages. You can add or remove dependencies using `uv add` / `uv remove` from the adapter directory:

```bash
cd src/researchrubrics
uv add <package>     # add a dependency
uv remove <package>  # remove a dependency
```

- Docker installed and running
- Harbor (commands above use `uvx --from harbor==0.23.0`)
- Python 3.13+ with `uv` for task generation:
  ```bash
  cd src/researchrubrics
  uv sync
  ```
- API keys (export as environment variables):
  - Judge: `GEMINI_API_KEY` for the default judge, or the key for whichever provider `JUDGE_MODEL` points at (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), or `JUDGE_API_KEY` + `JUDGE_API_BASE` for a LiteLLM proxy (plus `JUDGE_API_VERSION` and an `azure/<deployment>` model id for an Azure-style gateway)
  - Agent: model keys as needed by your agent

## Troubleshooting

- **`RewardFileNotFoundError` / verifier exit code 1**: every judge call failed. Check that the judge key is exported on the host and that `JUDGE_MODEL` is a valid LiteLLM model id. Judge errors are in the verifier stdout.
- **Judge rejects `max_tokens`**: non-Gemini judges often allow fewer than 50,000 output tokens. Set `JUDGE_MAX_TOKENS` (e.g. `32768`).
- **Judge rate limits**: lower `JUDGE_MAX_CONCURRENT` (default 20) or `n_concurrent_trials`.
- **Verifier timeout**: long reports with many rubrics can take minutes. `[verifier].timeout_sec` is 1800.
- **HF download fails behind a corporate proxy**: download `processed_data.jsonl` manually and pass `--data-file`.

## Citation

```bibtex
@misc{sharma2025researchrubricsbenchmarkpromptsrubrics,
  title={ResearchRubrics: A Benchmark of Prompts and Rubrics For Evaluating Deep Research Agents},
  author={Manasi Sharma and Chen Bo Calvin Zhang and Chaithanya Bandi and Clinton Wang and Ankit Aich and Huy Nghiem and Tahseen Rabbani and Ye Htet and Brian Jang and Sumana Basu and Aishwarya Balwani and Denis Peskoff and Marcos Ayestaran and Sean M. Hendryx and Brad Kenstler and Bing Liu},
  year={2025},
  eprint={2511.07685},
  archivePrefix={arXiv},
  primaryClass={cs.AI},
  url={https://arxiv.org/abs/2511.07685}
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
