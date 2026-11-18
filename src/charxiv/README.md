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
- **Parity agent.** `charxiv-direct` (`src/charxiv/parity_agent.py`, `charxiv-direct@1.0.0`) reproduces upstream's single API call per question for matched-generation parity (see Parity). Install it with the `parity` extra.
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
harbor run -p datasets/charxiv -a claude-code -m anthropic/claude-haiku-4-5-20251001
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


**Approach: matched generation.** Upstream CharXiv does not run an agent: `src/generate.py` makes one API call per question with the chart and the question text and stores the reply, which `src/evaluate.py` grades. The adapter therefore ships a parity agent, `charxiv-direct` (`src/charxiv/parity_agent.py`), that makes the same call inside Harbor, as `kumo-vanilla` and `contractbench-parity-agent` do for their benchmarks:

- query = the upstream question text (the task instruction without the adapter's image-path and answer-file lines); image = the task's chart;
- OpenAI models: the request body of `generate_lib/gpt.py` (text then image, `max_tokens=1000`, `temperature=0`, `top_p=1`, `seed=42`); Anthropic models: that of `generate_lib/claude.py` (image then text, `max_tokens=1024`, `temperature=0`, `top_p=1`);
- the retry loop of `generate_lib/utils.py` (10 attempts, sleep 1 s × 1.6 per failure, `"Error in generating response."` if all fail);
- the reply is written verbatim to `/app/answer.txt` and graded by the Harbor verifier.

Both sides thus run the same generation, and only the harness differs (task packaging and the verifier). The original side runs upstream `src/generate.py`, `src/evaluate.py` and `src/get_stats.py` with three small changes, needed because upstream hard-codes them: the judge model (`gpt-4o-2024-05-13` is retired; both sides use `gpt-4o-2024-08-06`), descriptive grading with `nq_per_query=1` (one question per judge call, as in each Harbor task), and the OpenAI base URL for an API proxy. Parity runs disable the exact-match short-circuit (`CHARXIV_EXACT_MATCH_SHORTCUT=0`), so every answer goes through the judge on both sides. Parity uses `gpt-4o-mini-2024-07-18`, which upstream supports natively. A standard CLI agent run (Codex) on the Harbor side, reported below, shows that the tasks work with standard agents; that run is not part of parity.

**Result.** `charxiv-direct@1.0.0` with `gpt-4o-mini-2024-07-18`, 3 runs per side on the parity subset (`--split parity`: 100 of the 1,000 validation charts sampled with `random.Random(42)`, all 5 questions per chart, i.e. 400 descriptive + 100 reasoning = 500 tasks, 10%). Judge `gpt-4o-2024-08-06` on both sides, exact-match short-circuit off. Accuracy in %, mean ± sample SEM:

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| charxiv-direct@1.0.0 | gpt-4o-mini-2024-07-18 | reasoning accuracy | 3 | 100 (10% of 1,000) | 34.33 ± 0.8819 | 32.00 ± 0.5774 |
| charxiv-direct@1.0.0 | gpt-4o-mini-2024-07-18 | descriptive accuracy | 3 | 400 (10% of 4,000) | 74.33 ± 0.4410 | 74.17 ± 0.1667 |

Per-run scores: reasoning original 33.0 / 36.0 / 34.0, Harbor 33.0 / 31.0 / 32.0; descriptive original 74.5 / 73.5 / 75.0, Harbor 74.0 / 74.5 / 74.0. The run-score ranges overlap for both metrics. Neither side had a generation failure (`"Error in generating response."`) or a judge failure (score -1). Even at temperature 0 the OpenAI API is not deterministic: 83% of Harbor descriptive replies and 68% of Harbor reasoning replies are byte-identical to one of the three original replies for the same question. The 2.3-point reasoning gap comes from 11 of the 100 questions whose solve count differs between the sides (8 favour the original side, 3 the Harbor side). By majority vote over the three runs, 3 questions are solved only on the original side and 2 only on the Harbor side, which fits sampling noise on 100 questions. The Harbor side ran on harbor 0.23.0 (PyPI) with Docker and the separate verifier. Its runs are the three attempts of one job (`n_attempts: 3`); run *k* is the *k*-th attempt of each task by start time. Order: the 50-question sanity check below on both sides, then the three runs per side (the original side's three runs ran in parallel).

Reproduction, original side: the [parity fork](https://github.com/lijrjyan/CharXiv/tree/93e54a2583dedc74fc51687b979c55072343c669) is upstream `7ebe88f` with the three changes above, plus `harbor_parity/` (the 100 parity chart ids, a script that builds the subset, and a run script). Per run, from the fork's root (`harbor_parity/run_parity.sh parity_run1` does the same):

```bash
python harbor_parity/make_subset.py --out parity_run1 && cd parity_run1   # data/, images/ and src/ for the 100 parity charts
M=gpt-4o-mini-2024-07-18
for mode in descriptive reasoning; do
  python src/generate.py --model_name $M --model_path $M --model_api "$OPENAI_API_KEY" --mode $mode --data_dir ./data --image_dir ./images --output_dir ./results
  python src/evaluate.py --model_name $M --split val --mode $mode --api_key "$OPENAI_API_KEY"
done
python src/get_stats.py --model_name $M --split val
```

Reproduction, Harbor side:

```bash
cd src/charxiv && uv run charxiv --split parity --output-dir ../../datasets/charxiv_parity && cd ../..
uv pip install -e "src/charxiv[parity]"        # into the environment that runs Harbor
export OPENAI_API_KEY=...                       # agent and judge; OPENAI_BASE_URL for a proxy
export CHARXIV_EXACT_MATCH_SHORTCUT=0
harbor run -c src/charxiv/run_charxiv_parity.yaml
```

A 50-question pilot run before parity (10 parity charts, one run per side) gave identical replies for 40 of 50 questions and the same score for 49 of 50.

**Standard CLI agent (Harbor side only, not part of parity).** To check the path a real agent takes (read the instruction, open `/app/images/chart.jpg` in the container, write `/app/answer.txt`), Codex was run once on the same 500-task parity subset with the default task settings (exact-match short-circuit on, judge `gpt-4o-2024-08-06`):

| Agent | Model | Runs | Dataset Size | Descriptive accuracy | Reasoning accuracy |
|-------|-------|------|--------------|----------------------|--------------------|
| codex@0.169.1 | gpt-4o-mini-2024-07-18 | 1 | 500 (400 + 100) | 67.50 | 28.00 |

All 500 trials finished without exceptions, and in every trial Codex opened the chart with its `view_image` tool before writing the answer. Grading: 271 answers matched the ground truth exactly, 228 went to the judge and 1 answer file was empty. Codex scores below `charxiv-direct` with the same model (74.17 / 32.00), as expected for an agent loop with a coding-agent system prompt instead of upstream's single direct query. To avoid installing Node.js and Codex in every container during agent setup, the run used task images built `FROM` a local base image that is `python:3.11-slim` plus the same Codex install that Harbor's `codex` agent performs (nvm, Node 22, `@openai/codex@0.169.1`); Harbor then skips the install step. The tasks are otherwise unchanged. Config: `run_charxiv.yaml` (commented `codex` entry).

### Oracle Verification

The full validation split was run with the oracle agent on Harbor 0.23.0 (Docker, local orchestrator, separate verifier): **5,000 / 5,000 tasks scored 1.0**, with no errors. The oracle answer is the ground truth, so it is graded by the exact-match short-circuit and does not call the LLM judge. The judge path was checked separately in Harbor with `CHARXIV_EXACT_MATCH_SHORTCUT=0` and the default judge: oracle answers for three tasks (two reasoning, one descriptive) were scored 1 by the judge, and a deliberately wrong answer was scored 0.


Links: original benchmark https://github.com/princeton-nlp/CharXiv · parity fork https://github.com/lijrjyan/CharXiv/tree/93e54a2583dedc74fc51687b979c55072343c669 · adapter PR https://github.com/harbor-framework/adapters/pull/85 · dataset PR https://github.com/harbor-framework/harbor-datasets/pull/284 · parity upload https://huggingface.co/datasets/harborframework/parity-experiments/discussions/286. The shared parity repository is over the Hub file limit and refuses uploads for now, so the raw results are pinned at https://huggingface.co/datasets/jrjyan/charxiv-parity-experiments/tree/ada4d8eb995fff518f2be2ed7763cbe5f78ba1d6/adapters/charxiv until they can be pushed to discussion #286.

## Notes & Caveats

- **Split.** Only the validation split is adapted. Upstream deliberately sets the test-split answers to `null`, so the test split cannot be graded locally.
- **Instruction wrapper (prompt modification).** The upstream question text (with its bullet-point answer instructions and original indentation) is unchanged. The adapter adds one leading line naming the image path and one trailing line asking for the final answer in `/app/answer.txt`. The `charxiv-direct` parity agent removes these two lines again, so it sends exactly the upstream query.
- **Descriptive judge batching (deviation).** Upstream groups descriptive responses by template and grades 5 per judge call (`nq_per_query=5`). Each Harbor task is verified on its own, so the verifier grades with a batch of 1. This is the same prompt template with `NUM_TRIPLETS=1`; upstream also sends batches smaller than 5 for the remainder. Use `nq_per_query=1` on the original side for parity.
- **Exact-match short-circuit.** If `answer.txt` equals the ground truth after stripping surrounding whitespace, the reward is 1 and the judge is not called. Every upstream rubric awards 1 when the extracted answer and the ground truth refer to the same term or value, so a verbatim match is always a 1 under the rubric. The short-circuit only removes judge stochasticity and cost. It makes the oracle deterministic and API-free. Disable it with `CHARXIV_EXACT_MATCH_SHORTCUT=0`. Apply the same setting on both sides during parity. The parity runs used it off; the Codex run above used the default (on).
- **Empty or invalid answer.** A missing or empty `/app/answer.txt` gets reward 0 without a judge call. The upstream judge prompt says to give 0 when there is no response. An answer path that is a symlink, a directory or another non-regular file, is unreadable, or is larger than 64 KiB also gets 0 (`method: agent_fault`).
- **Judge failures.** If the judge replied but never produced valid output within 10 attempts, the score is -1, which counts as reward 0 (upstream `get_stats.py`). If the judge never replied at all (missing key, network or auth error), or the verifier itself fails, `judge.py` exits non-zero and writes no reward file. `test.sh` has already removed any earlier `reward.txt`/`reward.json`, so Harbor raises `RewardFileNotFoundError` and the trial counts as a verifier error, not a 0. `/logs/verifier/judgment.json` records the method, the extracted answer and the judge errors for every trial.
- **Verifier isolation.** The verifier runs in its own container (`environment_mode = "separate"`) built from `tests/Dockerfile`, with the grading code baked in. The agent's container is stopped before verification, and only `/app/answer.txt` is copied across. Processes the agent started, or files it changed in its own container (site-packages, the interpreter, `/logs/verifier`), therefore cannot affect grading. As a second line of defence, `test.sh` uses `#!/bin/bash`, a fixed `PATH`, and `/usr/local/bin/python3 -I -B`, and removes any file under `/tests` that the adapter does not ship. `judge.py` loads `charxiv_constants.py` by explicit file path. If these tasks are run in shared-verifier mode instead (for example on a Harbor version without separate verifiers), the agent runs as root in the same container, so it could still patch site-packages or leave a background process that rewrites the reward after grading.
- **Prompt injection.** As upstream, the agent's answer text is inserted verbatim into the judge prompt, so an answer can try to instruct the judge. The exact-match short-circuit does not change this for non-matching answers.
- **Web lookup.** Questions are verbatim upstream text, and the CharXiv validation answers are public (GitHub and the Hugging Face dataset viewer). An agent with internet access could search for a question and find its answer, and the question text cannot be changed without breaking parity. Upstream queries each model once with no tools and no internet, while CLI agents keep Harbor's default network access here, as in other QA adapters with public answers (e.g. HLE). Scores of web-enabled agents may therefore be optimistic. To match upstream more closely, add `network_mode = "no-network"` under `[agent]` in `task.toml`, allow only the model API host at run time (`--allow-agent-host api.anthropic.com`), and disable hosted web tools (`--ak disallowed_tools=WebSearch,WebFetch`; Claude Code's `WebSearch` runs on Anthropic's side, so the network policy alone does not stop it). This was tested on Harbor 0.23.0 with Docker: in the agent phase, `example.com`, `huggingface.co` and the model API were unreachable by default, and only the allowed host was reachable with `--allow-agent-host`. The parity agent (`charxiv-direct`) makes a single model call and never browses. No benchmark name, figure id or source link appears in the instruction or the agent's image.
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
