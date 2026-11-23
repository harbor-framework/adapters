# FinSearchComp → Harbor Adapter

## Overview

This adapter converts [FinSearchComp](https://github.com/randomtutu/FinSearchComp) into Harbor tasks.

- **Source** (upstream commit `55b6393fcf3c8f749ba5a69a70b20d4ef6f67caf`, sha256 checked by the adapter):
  - T2/T3: `data/finsearchcomp_data.json`
  - T1: `data/finsearchcomp_akshare_version.json`, the split upstream grades with the free AkShare API (the upstream quick start uses it too)
- **License**: CC-BY-4.0
- **Task type**: Open-domain financial search and reasoning; free-text answers graded by an LLM judge
- **Adapter size**: 593 tasks. T1 Time-Sensitive Data Fetching: 202 (Greater China 91, Global 111); T2 Simple Historical Lookup: 219; T3 Complex Historical Investigation: 172. About half are in Chinese.
- **Excluded**: the 41 T1 questions not in the AkShare split (they need paid data sources), and `(T1)Time_Sensitive_Data_Fetching_096` (Greater China, 台湾加权指数): upstream's own lookup raises `ValueError` on its tag/method pair, so it can never be graded.

## What is FinSearchComp?

FinSearchComp (ByteDance Seed and Columbia Business School, [arXiv:2509.13160](https://arxiv.org/abs/2509.13160)) is an expert-built benchmark of 635 financial questions covering global and Greater China markets. It tests whether search-enabled agents can find, reconcile and reason over financial data. Each question ships with a reference answer, an accepted error range and its own judge prompt; the judge scores each reply 1 (correct) or 0 (incorrect). The metric is accuracy.

## Adapter Features

- Loads the pinned upstream JSON files (download, or `--data-file` / `--akshare-data-file`) and verifies their sha256.
- One task per question; stable task names derived from upstream `prompt_id`. T1 names add the market (`-greater-china` / `-global`), because the two T1 sets reuse the same prompt ids.
- The agent receives the upstream question unchanged plus a short note on where to write the reply (`/app/answer.md`), and has web access.
- `tests/judge.py` reproduces upstream `eval.py`: same per-question judge system prompt and template, same message layout, `max_tokens=2048`, 3 attempts on API errors. The judge is called through LiteLLM, so `JUDGE_MODEL` takes any provider/model string (default `openai/gpt-5.4`, the parity judge). Writes the reply's score to `/logs/verifier/reward.txt` and the full judge output to `/logs/verifier/judge.json`.
- Oracle (`solution/solve.sh`) writes the upstream reference answer as the reply (T2/T3), or the snapshot quote (T1). The verifier recognises that text and scores it 1 without calling the judge (same approach as the deepresearch-bench adapter).
- **T1 ground truth: dated snapshot with live fallback.** Upstream builds the T1 ground truth at grading time from AkShare market tables and refreshes them when they are not from the current day. The adapter keeps that rule:
  - With `--t1-snapshot-dir`, each T1 task embeds the upstream ground truth from that snapshot. The date is labelled in `task.toml` (`[metadata] t1_snapshot_date`, `t1_snapshot_fetched_at`, UTC) and in `tests/task_data.json`.
  - At grading time the verifier uses the embedded value only if `t1_snapshot_date` is today (UTC). Otherwise it fetches the needed tables live with the same AkShare calls (`tests/t1_ground_truth.py`, upstream `market_data.py` vendored).
  - `judge.json` records `ground_truth_source` (`snapshot` / `live`), `ground_truth_date` and `ground_truth_fetched_at` for every T1 trial.
  - Without `--t1-snapshot-dir`, T1 tasks always fetch live, and their oracle has no answer.
- The verifier runs in a separate container (`environment_mode = "separate"`) built from `tests/Dockerfile`. Only `/app/answer.md` is passed to it as an artifact, so the agent cannot change the judge code or its dependencies. This passes `harbor lint` on Harbor 0.26.0.

## Generated Task Structure

```
finsearchcomp/
├── t2-simple-historical-lookup-001/
│   ├── task.toml                 # name: bytedance-seed/finsearchcomp__<id>; separate verifier
│   ├── instruction.md            # upstream question + output note
│   ├── environment/
│   │   └── Dockerfile            # agent image: python:3.12-slim
│   ├── solution/
│   │   └── solve.sh              # writes the reference answer
│   └── tests/
│       ├── Dockerfile            # verifier image: python:3.12-slim + litellm (T1: + akshare 1.20.43, pandas)
│       ├── test.sh               # runs judge.py
│       ├── judge.py              # LLM judge (upstream prompts)
│       ├── t1_ground_truth.py    # T1 only: snapshot / live ground truth
│       ├── market_data.py        # T1 only: upstream AkShare lookup (vendored)
│       └── task_data.json        # question, reference, judge prompts; T1: ticker, dated snapshot
└── ...
```

## Run Evaluation / Harness

Pending registry publication. Local runs:

```bash
export JUDGE_MODEL=openai/gpt-5.4          # any LiteLLM model string
export OPENAI_API_KEY=...                  # or ANTHROPIC_API_KEY for anthropic/... judges
harbor run -c src/finsearchcomp/run_finsearchcomp.yaml          # oracle
harbor run -p datasets/finsearchcomp -a <agent> -m <model>
```

## Usage: Create Task Directories

```bash
cd src/finsearchcomp
# T2 + T3 only (no extra dependencies)
uv run finsearchcomp --output-dir ../../datasets/finsearchcomp --tiers t2 t3

# All tiers, with a fresh dated T1 snapshot (~15 min of AkShare downloads).
# Run it on the day you grade, best on a weekend so prices do not move.
uv run --extra t1 finsearchcomp --output-dir ../../datasets/finsearchcomp \
  --t1-snapshot-dir ../../datasets/finsearchcomp-t1-snapshot --fetch-t1-snapshot

# Options: --limit N, --overwrite, --task-ids <id ...>, --tiers t1 t2 t3,
#          --data-file <finsearchcomp_data.json>, --akshare-data-file <finsearchcomp_akshare_version.json>,
#          --t1-snapshot-dir <dir of upstream-format snapshots>, --fetch-t1-snapshot
```

Keep the snapshot directory outside the dataset directory: Harbor treats every sub-directory of a dataset as a task.

## Comparison with Original Benchmark (Parity)

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| claude-code@2.1.329 | claude-haiku-5-5 | accuracy | 3 | 33 (5.6% of 593) | 0.495 ± 0.036 | 0.525 ± 0.020 |

Per-run accuracy: original 0.545, 0.515, 0.424; Harbor 0.545, 0.485, 0.545. The run ranges overlap.

Both sides run the same agent version, model, container limits and instruction, and use the same judge prompt with `gpt-5.4`. The original side is the upstream repository with the minimal grading fixes and a small agent runner (`parity/run_agent.py`), in [Salliberg/FinSearchComp](https://github.com/Salliberg/FinSearchComp).

Reproduce on the Harbor side:

```bash
harbor run -p datasets/finsearchcomp -a claude-code -m anthropic/claude-haiku-5-5 \
  $(grep -v '^t1-' src/finsearchcomp/parity_task_ids.txt | sed 's/^/-i /')
```

Reproduce on the original side: see `parity/README.md` in the fork.

**Scope: T2 and T3 only.** `parity_task_ids.txt` lists 50 tasks (T1 17, T2 19, T3 14). Parity uses the 33 T2/T3 tasks. The 17 T1 tasks are left out because no same-day AkShare snapshot could be fetched during the parity window. T1 tasks are still generated and graded the same way.

## Notes & Caveats

- **T1 is time-sensitive.** A T1 score is only meaningful together with its ground-truth date (`ground_truth_date` in `judge.json`). Agent and verifier should run on the same day, and best on a weekend or holiday so prices do not move between answering and grading. A registry copy of the dataset carries an old snapshot, so its T1 tasks always fetch live.
- **T1 live fetches are slow.** One full table takes 3-12 s (FX, indices) to over 8 minutes (US stocks), so the T1 verifier timeout is 1800 s. Many parallel live fetches may be throttled by the data source; a same-day snapshot avoids them.
- **T1 with no ground truth.** If the ticker is not found in the market table (3 of 202 in the upstream sample snapshot: `HSTECH.HI`, `HSI.HI`, `932000.CSI`), upstream asks the judge, which must answer `{"score": "null"}`, and leaves the item out of accuracy. The verifier writes no reward in that case, so the trial is void rather than scored 0.
- **T1 `fetch_time_utc`.** Upstream stamps each quote with the lookup time, not the market-data time. The embedded quote therefore shows the generation time; the real data date is `t1_snapshot_date`. The judge prompts tell the judge to ignore dates.
- **Upstream grading bugs** (fixed in this adapter):
  - `parse_judge_output` requires a ```` ```json ```` fence and reads `answer_score[0][0]`. The judge prompts ask for a flat `{"answer_score": 0}` (T2/T3) or `{"score": 0}` (T1) in a plain ```` ``` ```` fence, so every reply is scored as an error (the shipped example result shows `-100000`). This adapter accepts both keys, a flat or nested value, and a fence with or without the `json` tag.
  - The counter behind `accuracy` is never incremented, so upstream always reports 0; the overall average also skips every item scored 0.
  - `chat.py` contains unresolved merge-conflict markers and does not run.
  - `market_data.py` reads snapshot CSVs without a dtype, so `代码` becomes an integer and every code with a leading zero (for example `002230`, `00700`, `000300`) never matches: 41 of 202 T1 questions get no ground truth from upstream's own sample snapshot. The vendored copy reads `代码` as text (3 misses left).
  - `requirements.txt` allows any `akshare>=1.17.0`, but 1.20.44 renamed `forex_spot_em`, `stock_zh_index_spot_em` and `stock_hk_index_spot_em`. The verifier pins 1.20.43.
- **Empty replies** score 0. Upstream skips them instead.
- **T2/T3 answers can drift.** They are historical, but agencies revise published figures. For example, SAFE's revised BOP table (2026-09-29) gives China's 2024 current-account balance as ≈4623 ×10⁸ USD, while the reference (4220, ±1%) matches the earlier preliminary release. An agent that finds the revised figure is scored 0. This is upstream behaviour and is kept unchanged.
- **Judge model.** Upstream does not state the judge model. It is set with `JUDGE_MODEL`.
- **Original answer harness.** Upstream calls models through an internal gateway with a built-in search tool, which cannot be reproduced outside ByteDance.

## Installation / Prerequisites

- Harbor CLI (`uv tool install harbor`) and Docker.
- An API key for the judge model's provider (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).
- Network access for both the agent (web search) and the verifier (judge API).

## Troubleshooting

- `sha256 does not match`: pass `--data-file` / `--akshare-data-file` pointing at the files from the pinned commit.
- `T1 snapshots need akshare and pandas`: run the generator with `uv run --extra t1`.
- T1 trial has no reward and the log shows `T1 ground truth fetch failed`: the live AkShare download failed or was throttled; rerun later or regenerate with a same-day snapshot.
- Trial has no reward: the judge API failed after 3 attempts; check the key, base URL and model name.
- Reward 0 with `"parse_error": true` in `judge.json`: the judge did not output an `answer_score`; inspect `judge_output`.

## Citation

```bibtex
@misc{hu2025finsearchcomprealisticexpertlevelevaluation,
      title={FinSearchComp: Towards a Realistic, Expert-Level Evaluation of Financial Search and Reasoning},
      author={Liang Hu and Jianpeng Jiao and Jiashuo Liu and Yanle Ren and Zhoufutu Wen and Kaiyuan Zhang and Xuanliang Zhang and Xiang Gao and Tianci He and Fei Hu and Yali Liao and Zaiyuan Wang and Chenghao Yang and Qianyu Yang and Mingren Yin and Zhiyuan Zeng and Ge Zhang and Xinyi Zhang and Xiying Zhao and Zhenwei Zhu and Hongseok Namkoong and Wenhao Huang and Yuwen Tang},
      year={2025},
      eprint={2509.13160},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/2509.13160},
}
```

## Authors & Contributions

Adapter: Salliberg. Benchmark: the FinSearchComp authors (ByteDance Seed, Columbia Business School).
