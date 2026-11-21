## SecureReviewer → Harbor Adapter

## Overview

SecureReviewer evaluates **secure code review**: given a code change (a diff hunk from a real
open-source pull request), write a review comment that identifies the security issue it introduces.
Each review has four parts, R = (ST, D, I, A): **Security type** (one of 7 categories), **Description**,
**Impact** and **Advice**. Reviews are scored against an expert-refined reference with **SecureBLEU**,
the paper's metric that combines BLEU-4 per section with security-keyword overlap.

- **Source:** [SIMIAO515/SecureReviewer](https://github.com/SIMIAO515/SecureReviewer) (ICSE 2026);
  paper [arXiv:2510.26457](https://arxiv.org/abs/2510.26457).
- **License:** the upstream repository does not include a license file; the data is derived from the
  CodeReviewer dataset (Microsoft).
- **Size:** the test split (`dataset/test.jsonl`) has 300 items: 261 with a security issue and 39 labelled
  `No Issue`.
- **This adapter:** **261 Harbor tasks, one per test item with a security issue.** SecureBLEU's
  `process_jsonl` skips every item whose reference is `No Issue`, so those 39 items never contribute to
  the benchmark score and are left out. Task ids are the 0-based line number in `test.jsonl`, e.g.
  `test-000` (registry name `securereviewer/securereviewer__test-000`).
- **Main adaptation:** upstream, a model is prompted once per item and its output is parsed into the four
  sections. In Harbor, an agent receives the same prompt with the diff (also at `/workspace/patch.diff`)
  and writes the review to `/workspace/review.txt`. Grading runs the upstream `SecureBleu.py`
  unmodified.

## What is SecureReviewer?

SecureReviewer (Liu et al., ICSE 2026) builds a dataset of security-related code review comments mined
from CodeReviewer and refined into the (ST, D, I, A) format; the test split was manually refined by
security experts. The security types are Input Validation, Exception Handling, Type and Data Handling,
Concurrency, Access Control and Information Security, Error State Management and Resource Management.

**SecureBLEU** scores one item as `0.5 × weighted BLEU + 0.5 × 100 × keyword overlap`:
- weighted BLEU = 0.3 × (exact security-type match ? 100 : 0) + 0.3 × BLEU(description) +
  0.2 × BLEU(impact) + 0.2 × BLEU(advice);
- keyword overlap = how many of the security keywords (type-specific and common lists, matched with WordNet
  lemmas/synonyms) and `code` spans in each reference section also appear in the predicted section;
- a prediction of `No Issue` for an item with an issue scores 0.

The benchmark score is the mean over items (`Average BLEU score` printed by `evaluate/SecureBleu.py`).

## Adapter Features

- **Pinned data**: `dataset/test.jsonl` is downloaded from upstream commit `86df98bf` (or pass
  `--data-file`).
- **Separate verifier**: grading runs in its own container (`[verifier] environment_mode = "separate"`),
  built from `tests/Dockerfile`. The agent image holds only `patch.diff`; the only file passed from the
  agent to the verifier is the declared artifact `/workspace/review.txt`.
- **Upstream scorer, unmodified**: the verifier image fetches `evaluate/SecureBleu.py` from the same pinned
  commit. `tests/grade.py` parses the review with the upstream `parse_security_review` (copied verbatim
  from `infer/test.py`), writes a one-line `result.jsonl` and executes `SecureBleu.py` on it.
- **Reward**: `reward = SecureBLEU / 100` for the item, so **Harbor's mean reward × 100 is the upstream
  benchmark score** (every item is weighted equally upstream too). `/logs/verifier/details.json` also holds
  the parsed review, the type match and the scorer's log.
- **Hidden reference**: the reference review exists only in the verifier image (`tests/reference.json`),
  never in the agent's container.
- **Oracle**: writes the expert-refined reference comment (`solution/review.txt`).
- **Parity subset**: `--split parity` generates a fixed 25-task subset (about 10%), stratified by security
  type in proportion to its size, sampled with seed 42.
- **Parity agent** (`parity/securereviewer_parity_agent.py`, `securereviewer-single-call@1.0.0`): sends the
  task instruction to the model in one Anthropic Messages API call (temperature 0, matching upstream's
  greedy decoding; `max_tokens` 2000 for the reply, where upstream caps prompt plus reply at 2,000 tokens
  with `max_length`) and writes the reply
  verbatim to `/workspace/review.txt`. The API call lives in `parity/single_call.py`, which the
  original-side runner uses byte for byte. The endpoint and key come from `ANTHROPIC_BASE_URL` and
  `ANTHROPIC_API_KEY`.

## Generated Task Structure

```
securereviewer/
├── test-{index}/
│   ├── task.toml                 # name securereviewer/securereviewer__test-{index}; source index + type in [metadata]
│   ├── instruction.md            # upstream review prompt + the diff + output format
│   ├── environment/
│   │   ├── Dockerfile            # agent image: python:3.11 + the diff
│   │   └── patch.diff            # the code change
│   ├── solution/
│   │   ├── solve.sh              # copies review.txt to /workspace/review.txt
│   │   └── review.txt            # reference review comment
│   └── tests/
│       ├── Dockerfile            # verifier image: nltk 3.9.1 (+ WordNet, POS tagger) + pinned SecureBleu.py + tests
│       ├── test.sh               # runs grade.py, always rewrites reward.json
│       ├── grade.py              # parse review + run upstream SecureBleu.py on this item
│       └── reference.json        # reference fields for this item
```

Adapter code:

```
src/securereviewer/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_securereviewer.yaml
├── run_securereviewer_parity.yaml       # Harbor-side parity job config
├── parity/
│   ├── securereviewer_parity_agent.py   # Harbor-side single-call agent
│   └── single_call.py                   # API call shared with the original-side runner
└── src/securereviewer/
    ├── __init__.py
    ├── adapter.py        # download + task generation
    ├── main.py           # CLI
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/Dockerfile
        ├── solution/solve.sh
        └── tests/{Dockerfile, test.sh, grade.py}
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the dataset is published:

```bash
# Oracle agent (reference solutions)
harbor run -d securereviewer/securereviewer

# A specific agent and model
harbor run -d securereviewer/securereviewer -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

```bash
# From the adapters repository root, after generating tasks into datasets/securereviewer
harbor run -c src/securereviewer/run_securereviewer.yaml                     # oracle
harbor run -c src/securereviewer/run_securereviewer.yaml -a <agent> -m "<model>"
harbor run -p datasets/securereviewer -a <agent> -m "<model>"

# Resume a previously started job
harbor job resume -p jobs/<job-name>
```

### Running Individual Trial

```bash
harbor trial start -p datasets/securereviewer/test-000
harbor trial start -p datasets/securereviewer/test-000 -a <agent> -m "<model>"
```

## Usage: Create Task Directories

```bash
cd src/securereviewer
uv sync
uv run securereviewer --output-dir ../../datasets/securereviewer
```

Flags:
- `--output-dir` — where to write tasks (default `datasets/securereviewer` at the repo root)
- `--limit N` — only the first N tasks
- `--overwrite` — replace existing task directories
- `--task-ids ID [ID ...]` — only these task ids (e.g. `test-000`)
- `--data-file PATH` — use a local copy of `dataset/test.jsonl` instead of downloading the pinned one
- `--split {full,parity}` — `full` (default): all 261 tasks; `parity`: the 25-task parity subset

## Comparison with Original Benchmark (Parity)

Scores are SecureBLEU (0–100, mean over items), reported as mean ± sample SEM over 2 runs per side.
Both sides send the same prompt to the same model with the same settings in one API call per item.
The only difference is where the review is graded: upstream `evaluate/SecureBleu.py` on a
`result.jsonl`, versus the Harbor task's separate verifier.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| securereviewer-single-call@1.0.0 | claude-haiku-4-5 | SecureBLEU | 2 | 25 of 261 (9.6%) | 26.1055 ± 0.1446 | 26.3495 ± 0.1436 |

The runs are original 25.96 and 26.25, and Harbor 26.21 and 26.49 (0 exceptions), so the run ranges
overlap. The API cost for all four runs was about $0.30.

- Original benchmark: [SIMIAO515/SecureReviewer](https://github.com/SIMIAO515/SecureReviewer) (commit `86df98bf`)
- Parity fork with the API runner: [YiDanielLu/SecureReviewer@harbor-parity](https://github.com/YiDanielLu/SecureReviewer/tree/harbor-parity)
- Adapter PR: [harbor-framework/adapters#97](https://github.com/harbor-framework/adapters/pull/97)
- Dataset PR: [harbor-framework/harbor-datasets#285](https://github.com/harbor-framework/harbor-datasets/pull/285)
- Parity results (Hugging Face): [harborframework/parity-experiments#287](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/287). The PR has no files yet because that dataset is over the Hub's file limit, so the full bundle is mirrored at [Daniellu88/securereviewer-parity-experiments](https://huggingface.co/datasets/Daniellu88/securereviewer-parity-experiments/tree/ce88c43725ff2da24920be8dc281e8923c3e497f/adapters/securereviewer)

Reproduction. Put `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` and `DAYTONA_API_KEY` in a `.env` file.
The Harbor side ran on Harbor 0.26.0 with its Daytona extra. It used Daytona SDK 0.233.0, because SDK
2.x doesn't work with Harbor 0.26.0: `uv tool install 'harbor[daytona]==0.26.0' --with 'daytona<2'`.
`run_securereviewer_parity.yaml` has the same Harbor-side settings as a job config.

```bash
# Original side: the parity fork (upstream 86df98bf + infer/test_api.py)
git clone -b harbor-parity https://github.com/YiDanielLu/SecureReviewer && cd SecureReviewer
set -a; . /path/to/.env; set +a
pip install nltk==3.9.1 && python -m nltk.downloader wordnet omw-1.4 averaged_perceptron_tagger_eng
for r in 1 2; do
  python infer/test_api.py --model claude-haiku-4-5 --out runs/run$r --indices $(cat parity_indices.txt)
  (cd runs/run$r && python ../../evaluate/SecureBleu.py | tail -2)   # "Average BLEU score"
done

# Harbor side (from the adapters repo root)
cd src/securereviewer && uv run securereviewer --split parity --output-dir ../../datasets/securereviewer-parity && cd ../..
for r in 1 2; do
  PYTHONPATH=src/securereviewer/parity harbor run -p datasets/securereviewer-parity \
    --agent-import-path securereviewer_parity_agent:SecureReviewerSingleCallAgent \
    -m anthropic/claude-haiku-4-5 -e daytona --env-file .env -n 4 --job-name parity-harbor-run$r
done
# SecureBLEU = mean reward x 100
```

## Notes & Caveats

- **Oracle ceiling is below 100.** The reference review gets BLEU 100 on every section and the exact
  type, but the keyword-overlap half of SecureBLEU averages six ratios with fixed weights, and a ratio is
  0 (not skipped) when the reference section has no keywords or no `code` spans to match. So even the
  reference scores below 100 on most items: the oracle's mean SecureBLEU is **80.73** (5 of 261 items reach
  100; minimum 52.5). In the Harbor oracle run (261 trials, 0 exceptions, mean reward 0.807), every task's
  reward equals that item's maximum achievable score, computed by running `SecureBleu.py` on the reference
  review outside Harbor.
- **`No Issue` items are excluded** (39 of 300), because SecureBLEU never scores them.
- **Missing sections**: if a section header is missing, the section is scored as empty (upstream stores
  `None`, which crashes `SecureBleu.py`); a missing Security type counts as `No Issue` (score 0), as in
  `infer/test.py`. An empty or missing `review.txt` scores 0.
- `Error State Management` has no type-specific keyword list in `SecureBleu.py` (its list is named
  `State Management`), so only the common keywords count for those 46 items. This is upstream behaviour
  and is kept.
- **Parity runner (new code).** Upstream's `infer/test.py` only runs its fine-tuned local models, so the
  parity fork adds `infer/test_api.py`. It reuses upstream's review prompt text, `parse_security_review`
  and field mapping, and calls an API model instead of `model.generate`.
- **Parity prompt.** The parity prompt is the task instruction: upstream's review prompt, the raw
  unified diff in a fenced block (upstream feeds its models a `<add>/<del>/<keep>` encoding), and an
  output-format section listing the 7 types and the `Security type:/Description:/Impact:/Advice:`
  layout. The fine-tuned models learned that layout from training data, but a general chat model needs
  to be told it, or the parser finds no sections. Both parity sides use this exact prompt.
- **Parity model.** `claude-haiku-4-5` was used because `claude-haiku-5-5` rejects the `temperature`
  parameter. Even at temperature 0, API outputs vary slightly from run to run, which is the spread seen
  in the parity runs.
- **Model ID is an alias.** The guide asks for an exact dated model ID, but the 2077ai endpoint only
  serves the alias. It rejects `claude-haiku-4-5-20251001` with `model_not_found`, and every response
  in both parity runs reports `model: claude-haiku-4-5`. Both sides used the same alias.
- **Run order.** After a one-task sanity check on each side, both original-side runs were done before
  both Harbor-side runs, rather than alternating sides as the guide suggests. Each side's settings were
  fixed before any run, and nothing changed between runs.
- **Harbor version.** Parity and oracle runs used Harbor 0.26.0. Daytona SDK 0.233.0 was pinned
  because SDK 2.x isn't compatible with that Harbor version.
- **nltk version**: upstream does not pin nltk; the image uses nltk 3.9.1 with the `wordnet`, `omw-1.4` and
  `averaged_perceptron_tagger_eng` data.

## Installation / Prerequisites

- Docker installed and running
- Harbor CLI: `uv tool install harbor`
- Adapter environment:
  ```bash
  cd src/securereviewer
  uv sync
  ```
- API keys for the agent/model you run (exported as environment variables)

## Troubleshooting

- **`UnicodeEncodeError` from `harbor` on Windows consoles:** set `PYTHONUTF8=1`.
- **`Resource ... not found` from nltk in the verifier:** the nltk data is baked into the image under
  `/usr/share/nltk_data`; rebuild the image if it was built from an older Dockerfile.

## Citation

```bibtex
@misc{liu2025securereviewer,
      title={{SecureReviewer: Enhancing Large Language Models for Secure Code Review through Secure-aware Fine-tuning}},
      author={Fang Liu and Simiao Liu and Yinghao Zhu and Xiaoli Lian and Li Zhang},
      year={2025},
      eprint={2510.26457},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2510.26457},
}
```

## Authors & Contributions

This adapter is developed and maintained by [Yi Lu](mailto:81632945+YiDanielLu@users.noreply.github.com).

**Issues and Contributions:**
- Submit issues and pull requests to the adapters repository
- Follow the project's coding style and commit guidelines

## Acknowledgement

> API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
