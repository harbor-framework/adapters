# CharXiv → Harbor Adapter

## Overview

This adapter converts the validation split of [CharXiv](https://github.com/princeton-nlp/CharXiv) into Harbor tasks for multimodal chart understanding.

- **Source:** QA files from GitHub [`princeton-nlp/CharXiv`](https://github.com/princeton-nlp/CharXiv) at commit `7ebe88f78dee387691551f071abcb2b9e1a8025b`; chart images from Hugging Face [`princeton-nlp/CharXiv`](https://huggingface.co/datasets/princeton-nlp/CharXiv) at revision `f441eb632fc62f6f777830a0f47619e6e86459b0` (`images.zip`, sha256 `c4b151ce…efbd855`, checked at generation time).
- **Adapted size:** 5,000 tasks = 1,000 charts × (4 descriptive + 1 reasoning) questions.
- **Metric:** accuracy (binary reward per question, graded by an LLM judge with the upstream CharXiv rubric prompts). Upstream reports descriptive and reasoning accuracy separately.
- **Task naming:** `princeton-nlp/charxiv-descriptive-<figure_id>-<subq_idx>` and `princeton-nlp/charxiv-reasoning-<figure_id>`.

Each task gives the agent one chart image and one question, the same as one upstream query. The agent writes its answer to `/app/answer.txt`.

## What is CharXiv?

CharXiv (Wang et al., NeurIPS 2024 Datasets & Benchmarks) is an evaluation suite of 2,323 natural, diverse charts taken from arXiv papers. Human experts picked the charts and wrote and checked every question. Each chart has:

- **4 descriptive questions** (19 templates such as title, axis labels, tick values, legend labels, number of lines, subplot layout; 3 answerable plus 1 unanswerable per chart, where the expected answer is "Not Applicable"), and
- **1 reasoning question** that requires synthesizing information across the chart, with four answer types: text-in-chart, text-in-general, number-in-chart and number-in-general.

All answers are short, open-vocabulary strings. A GPT-4o judge grades each response against the ground truth using template-specific rubrics. The validation split (1,000 charts) has public answers. Test answers are withheld.

## Adapter Features

- **Faithful prompts.** Question text is built with the upstream query builders (`descriptive_query_helper`, `build_reasoning_queries`, `get_number_instruction`) from a verbatim vendored copy of upstream `src/constants.py` (`src/charxiv/upstream_constants.py`). A unit test checks that all 5,000 generated questions and judge prompts are byte-identical to the upstream code's output.
- **Image delivery.** Each task's chart is copied into its Docker image at the fixed path `/app/images/chart.jpg`, and the instruction names that path. The file name carries no upstream figure id. Image bytes are unchanged from the pinned `images.zip`.
- **Upstream LLM judge.** `tests/judge.py` reproduces `src/evaluate.py` and `src/get_stats.py`: the same rubric prompts, `temperature=0`, `top_p=1`, `seed=42`, `response_format=json_object`, `max_tokens` of 256 doubling up to 1024 on truncated JSON, and up to 10 attempts. A score outside {0, 1} counts as 0. The judge is configured through `[verifier.env]`: `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, and `CHARXIV_JUDGE_MODEL`. The default judge is `gpt-4o-2024-08-06`, because the upstream `gpt-4o-2024-05-13` has been retired by OpenAI (see Notes & Caveats).
- **Deterministic oracle.** `solution/solve.sh` writes the ground-truth answer. If the answer exactly matches the ground truth after stripping surrounding whitespace, the verifier awards 1 without calling the judge (see Notes & Caveats). So the oracle needs no API key.
- **Isolated verifier.** Ground truth exists only in `tests/config.json` and `solution/solve.sh`, and neither is ever copied into the agent's container. The judge runs in a separate verifier container built from `tests/Dockerfile` (`[verifier] environment_mode = "separate"`). The only thing it receives from the agent is `/app/answer.txt`, collected as an artifact after the agent's container has stopped. `test.sh` deletes any stale `reward.txt`/`reward.json` before grading. `judge.py` reads the answer without following symlinks and gives 0 to a symlink, a directory or another non-regular file, an unreadable file, or a file larger than 64 KiB.
- `--modes descriptive|reasoning` generates one question type only, so the two upstream metrics can be run and reported separately.

## Generated Task Structure

```text
datasets/charxiv/
├── charxiv-descriptive-0-0/
│   ├── task.toml
│   ├── instruction.md
│   ├── environment/
│   │   ├── Dockerfile          # agent image: python:3.11-slim + chart image
│   │   └── images/chart.jpg
│   ├── solution/
│   │   └── solve.sh            # writes ground truth to /app/answer.txt
│   └── tests/
│       ├── Dockerfile          # verifier image: python:3.11-slim + openai SDK + tests/
│       ├── test.sh             # clears stale rewards, runs judge.py
│       ├── judge.py            # upstream CharXiv grading (one question)
│       ├── charxiv_constants.py# vendored upstream constants.py
│       └── config.json         # mode, template/answer type, ground truth
├── ...
└── charxiv-reasoning-999/
```

## Run Evaluation / Harness

Once the dataset is published to the registry:

```bash
harbor run -d princeton-nlp/charxiv -a oracle
harbor run -d princeton-nlp/charxiv -a claude-code -m anthropic/claude-haiku-4-5-20251001
```

Before publication, generate the tasks locally (next section) and run from the `harbor-framework/adapters` repository root:

```bash
# Oracle (default agent in the config; no API key needed)
harbor run -c src/charxiv/run_charxiv.yaml

# Any local path
harbor run -p datasets/charxiv -a oracle
harbor trial start -p datasets/charxiv/charxiv-reasoning-0 -a oracle

# Real agents: the judge needs OpenAI credentials in the host environment
export OPENAI_API_KEY=...            # optional: OPENAI_BASE_URL, CHARXIV_JUDGE_MODEL
harbor run -p datasets/charxiv -a codex -m openai/<model>
```

Agents must be able to view image files. Claude Code (Read tool), Codex (`view_image`) and Gemini CLI (`read_file`) can. Terminal-only agents such as Terminus or mini-swe-agent cannot see the chart.

## Usage: Create Task Directories

```bash
cd src/charxiv
uv sync
uv run charxiv --output-dir ../../datasets/charxiv                 # all 5,000 tasks
uv run charxiv --output-dir ../../datasets/charxiv --limit 5
uv run charxiv --output-dir ../../datasets/charxiv --modes reasoning
uv run charxiv --output-dir ../../datasets/charxiv_parity --split parity     # 500-task parity subset
uv run charxiv --output-dir ../../datasets/charxiv --task-ids charxiv-reasoning-0 charxiv-descriptive-0-1
uv run charxiv --output-dir ../../datasets/charxiv --overwrite
```

By default the pinned QA JSON (GitHub) and `images.zip` (Hugging Face) are downloaded to `~/.cache/harbor-charxiv` (`--cache-dir`). `--source-dir` accepts a local CharXiv checkout that contains `data/` and an unzipped `images/`.

Unit tests (set `CHARXIV_UPSTREAM_DIR` to a CharXiv checkout to also run the upstream-equivalence tests):

```bash
CHARXIV_UPSTREAM_DIR=/path/to/CharXiv uv run pytest
```

## Comparison with Original Benchmark (Parity)

Parity has not been run yet. The plan (pending team approval) is Scenario 2. The original benchmark calls MLLM APIs directly (`src/generate_lib/*`), so the plan is to fork CharXiv and add a `generate_lib` backend that runs the same CLI agent (planned: Claude Code with `claude-haiku-4-5-20251001`, following the HLE adapter) on each chart/question. That backend uses the same instruction wrapper as this adapter (image path line plus `/app/answer.txt` line) and grades with upstream `src/evaluate.py` and `src/get_stats.py`. The fork makes two documented changes to grading: descriptive questions are graded with `nq_per_query=1`, and the same exact-match short-circuit is applied (see Notes & Caveats). Prompts and rubrics are otherwise untouched.

Proposed parity subset (`--split parity`, to be confirmed with the team): 100 of the 1,000 validation charts (10%) sampled uniformly with `random.Random(42)`, keeping all 5 questions per chart, i.e. 400 descriptive + 100 reasoning = 500 tasks. The 100 reasoning questions split by answer type as 46 text-in-chart, 5 text-in-general, 32 number-in-chart and 17 number-in-general (full validation split: 440 / 99 / 232 / 229).

Reproduction (Harbor side; original-side commands to be added with the fork):

```bash
cd src/charxiv && uv run charxiv --split parity --output-dir ../../datasets/charxiv_parity && cd ../..
export OPENAI_API_KEY=...   # judge
harbor run -p datasets/charxiv_parity -a claude-code -m anthropic/claude-haiku-4-5-20251001
```

### Oracle Verification

The full validation split was run with the oracle agent on Harbor 0.23.0 (Docker, local orchestrator, separate verifier): **5,000 / 5,000 tasks scored 1.0**, with no errors. The oracle answer is the ground truth, so it is graded by the exact-match short-circuit and does not call the LLM judge. The judge path was checked separately in Harbor with `CHARXIV_EXACT_MATCH_SHORTCUT=0` and the default judge: oracle answers for three tasks (two reasoning, one descriptive) were scored 1 by the judge, and a deliberately wrong answer was scored 0.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| TBD | TBD | reasoning accuracy | TBD | TBD | TBD | TBD |
| TBD | TBD | descriptive accuracy | TBD | TBD | TBD | TBD |

Links: original benchmark https://github.com/princeton-nlp/CharXiv · parity fork TBD · adapter PR https://github.com/harbor-framework/adapters/pull/85 · dataset PR TBD · parity upload TBD.

## Notes & Caveats

- **Split.** Only the validation split is adapted. Upstream deliberately sets the test-split answers to `null`, so the test split cannot be graded locally.
- **Instruction wrapper (prompt modification).** The upstream question text (with its bullet-point answer instructions and original indentation) is unchanged. The adapter adds one leading line naming the image path and one trailing line asking for the final answer in `/app/answer.txt`. The parity fork must add the same two lines.
- **Descriptive judge batching (deviation).** Upstream groups descriptive responses by template and grades 5 per judge call (`nq_per_query=5`). Each Harbor task is verified on its own, so the verifier grades with a batch of 1. This is the same prompt template with `NUM_TRIPLETS=1`; upstream also sends batches smaller than 5 for the remainder. Use `nq_per_query=1` on the original side for parity.
- **Exact-match short-circuit.** If `answer.txt` equals the ground truth after stripping surrounding whitespace, the reward is 1 and the judge is not called. Every upstream rubric awards 1 when the extracted answer and the ground truth refer to the same term or value, so a verbatim match is always a 1 under the rubric. The short-circuit only removes judge stochasticity and cost. It makes the oracle deterministic and API-free. Disable it with `CHARXIV_EXACT_MATCH_SHORTCUT=0`. Apply the same setting on both sides during parity.
- **Empty or invalid answer.** A missing or empty `/app/answer.txt` gets reward 0 without a judge call. The upstream judge prompt says to give 0 when there is no response. An answer path that is a symlink, a directory or another non-regular file, is unreadable, or is larger than 64 KiB also gets 0 (`method: agent_fault`).
- **Judge failures.** If the judge replied but never produced valid output within 10 attempts, the score is -1, which counts as reward 0 (upstream `get_stats.py`). If the judge never replied at all (missing key, network or auth error), or the verifier itself fails, `judge.py` exits non-zero and writes no reward file. `test.sh` has already removed any earlier `reward.txt`/`reward.json`, so Harbor raises `RewardFileNotFoundError` and the trial counts as a verifier error, not a 0. `/logs/verifier/judgment.json` records the method, the extracted answer and the judge errors for every trial.
- **Verifier isolation.** The verifier runs in its own container (`environment_mode = "separate"`) built from `tests/Dockerfile`, with the grading code baked in. The agent's container is stopped before verification, and only `/app/answer.txt` is copied across. Processes the agent started, or files it changed in its own container (site-packages, the interpreter, `/logs/verifier`), therefore cannot affect grading. As a second line of defence, `test.sh` uses `#!/bin/bash`, a fixed `PATH`, and `/usr/local/bin/python3 -I -B`, and removes any file under `/tests` that the adapter does not ship. `judge.py` loads `charxiv_constants.py` by explicit file path. If these tasks are run in shared-verifier mode instead (for example on a Harbor version without separate verifiers), the agent runs as root in the same container, so it could still patch site-packages or leave a background process that rewrites the reward after grading.
- **Prompt injection.** As upstream, the agent's answer text is inserted verbatim into the judge prompt, so an answer can try to instruct the judge. The exact-match short-circuit does not change this for non-matching answers.
- **Web lookup.** Questions are verbatim upstream text, and the CharXiv validation answers are public (GitHub and the Hugging Face dataset viewer). An agent with internet access could search for a question and find its answer. No benchmark name, figure id or source link appears in the instruction or the agent's image, but the question text itself cannot be changed without breaking parity. Like other QA adapters with public answers (e.g. HLE), the tasks keep Harbor's default agent network access, because CLI agents are installed at run time and parity runs reach the model through an API proxy. For runs where lookup matters, restrict agent-phase network access to the model API host (`[agent] network_mode = "allowlist"` with `allowed_hosts`, as `src/programbench` does, or `--allow-agent-host`). Parity uses the same network policy on both sides.
- **Upstream quirk kept.** The reasoning judge prefix asks for keys `[extract_answer, score]`, but upstream code reads `extracted_answer` (the in-context examples also use `extracted_answer`). This behaviour is kept as is.
- **Judge model (deviation).** Upstream grades with `gpt-4o-2024-05-13`, which OpenAI has retired (the API returns 404 `model_not_found`). The default judge is the closest pinned GPT-4o snapshot, `gpt-4o-2024-08-06`, which accepts the same call parameters (`temperature`, `top_p`, `seed`, `max_tokens`, `json_object`); GPT-5-family models do not. Parity uses the same judge on both sides, as the HLE adapter did when it swapped judges symmetrically.
- **Known data error.** The [erratum on the CharXiv dataset card](https://huggingface.co/datasets/princeton-nlp/CharXiv#erratum) notes that the reasoning answer for chart `0` is wrong. It is kept unchanged for fidelity. The oracle is unaffected.
- **Aggregation.** Harbor's job mean mixes 4,000 descriptive and 1,000 reasoning tasks. Report the two upstream metrics separately, by generating with `--modes` or by grouping on the task-name prefix.
- **Image licensing.** CharXiv's QA data is CC BY-SA 4.0 and its code is Apache-2.0. Per upstream, the copyright of the charts belongs to the original arXiv authors (sources are listed in `image_metadata_val.json`). The charts are redistributed here exactly as CharXiv distributes them on Hugging Face.

## Installation / Prerequisites

- Docker, and the Harbor CLI (`uv tool install harbor`; tested with harbor 0.23.0).
- Python ≥ 3.11 and `uv` for the adapter. The adapter has no runtime dependencies beyond the standard library.
- Network access when generating tasks: GitHub raw files plus a 141 MB `images.zip` from Hugging Face. Pass `--source-dir` to work offline.
- For non-oracle runs: an OpenAI-compatible API key for the GPT-4o judge.

## Troubleshooting

- **`images.zip sha256 mismatch`:** the cached download is incomplete or corrupt. Delete `~/.cache/harbor-charxiv/<revision>/images.zip` and retry.
- **Verifier error "OPENAI_API_KEY is not set":** the agent's answer was not an exact match, so the judge is required. Export `OPENAI_API_KEY` (and `OPENAI_BASE_URL` for a proxy) before `harbor run`.
- **Agent scores near random:** check that the agent can actually view images. Terminal-only agents cannot.
- **`FileExistsError` when generating:** pass `--overwrite`.

## Citation

```bibtex
@inproceedings{wang2024charxiv,
  title={CharXiv: Charting Gaps in Realistic Chart Understanding in Multimodal LLMs},
  author={Wang, Zirui and Xia, Mengzhou and He, Luxi and Chen, Howard and Liu, Yitao and Zhu, Richard and Liang, Kaiqu and Wu, Xindi and Liu, Haotian and Malladi, Sadhika and Chevalier, Alexis and Arora, Sanjeev and Chen, Danqi},
  booktitle={Advances in Neural Information Processing Systems (Datasets and Benchmarks Track)},
  year={2024}
}
```

## Authors & Contributions

This adapter is developed and maintained by Junnan Li (junnanl@cs.wisc.edu). The original benchmark is by the CharXiv authors (Princeton Language and Intelligence).

**Issues and Contributions:**

- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines
