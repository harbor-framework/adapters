## Overview

This adapter ports OpenAI Evals' English-language MakeMeSay interaction benchmark to Harbor. It creates one Harbor task for each upstream sample: 50 in the default `medium-and-hard` variant, 45 `easy`, 50 `medium`, 28 `hard`, and 16 `very-hard` (189 split-specific tasks in total). The adapter pins the upstream Evals commit and verifies each source data file by SHA-256 before generation. The five variants remain separately labeled; the total is their registry-size sum, without cross-variant deduplication.

The copied OpenAI Evals code and prompts are covered by the repository's MIT license; that repository lists separate licenses for some dataset resources. This adapter does not redistribute the NLTK WordNet data, which is downloaded at runtime under its [own license](https://wordnet.princeton.edu/license-and-commercial-use). The prompts retain their original wording. This adapter does not claim parity: no model runs have been recorded. The custom agent implementation is required because each task uses separate manipulator, manipulatee, and judge completion calls.

## What is MakeMeSay?

MakeMeSay tests whether a model acting as a manipulator can persuade a simulated user to say a secret codeword without saying it first, and whether the user detects the manipulation. The upstream implementation supplies the role prompts, a 30-turn conversation, a final user guess, NLTK-based codeword matching, and a judge that scores the user's awareness. See the [pinned OpenAI Evals implementation](https://github.com/openai/evals/tree/8eac7a7de5215c907fbddc30efdaf316913eccdd/evals/elsuite/make_me_say) and [OpenAI o1 System Card](https://openai.com/index/openai-o1-system-card/).

## Adapter Features

- Generates stable, split-qualified task IDs from all five upstream registry variants and checks upstream data hashes and sample counts.
- Preserves the original prompts, role visibility, turn order, periodic updates, final guess, internal-monologue handling, and four metrics.
- Provides `makemesay.agent:MakeMeSayAgent`, a Harbor custom agent that calls LiteLLM separately for the manipulator, manipulatee, and judge. By default the three roles use Harbor's selected model; `manipulatee_model` and `judge_model` can override the latter two.
- Stores the public transcript, model identifiers, judge outputs, and recomputed metric values as `/workspace/makemesay_result.json`. Private monologue spans are removed from this artifact.
- Includes a deterministic scorer fixture to exercise result transport and verifier calculations. It is explicitly marked `scorer-fixture` and is not a model run, oracle performance, or parity evidence.

## Run Evaluation / Harness

After the dataset is registered, run it from the adapters repository root with the custom agent and a dated model ID:

```bash
uv run --project src/makemesay harbor run \
  -d <organization>/makemesay \
  -a makemesay.agent:MakeMeSayAgent \
  -m "<dated-model-id>" \
  --n-concurrent 1
```

The dataset is not registered yet. For local work, generate tasks first and use the reference config below. The custom agent needs model credentials in the environment (or Harbor's supported credential configuration). The default uses one selected model for all three roles; for separate role models, pass `--agent-kwarg manipulatee_model=<dated-model-id>` and `--agent-kwarg judge_model=<dated-model-id>`. Keep role models identical on both sides of a parity comparison.

## Usage: Create Task Directories

From the repository root, generate all five variants:

```bash
uv run --project src/makemesay python -m makemesay.main \
  --output-dir datasets/makemesay
```

Useful options:

- `--splits medium-and-hard` selects the default upstream variant; any subset of the five names is accepted.
- `--limit 10` generates the first ten tasks after split selection.
- `--task-ids make-me-say-medium-and-hard-00000` selects specific local IDs; upstream registry names are also accepted.
- `--overwrite` replaces generated task directories with the same IDs.

### Generated Task Structure

```text
datasets/makemesay/
└── make-me-say-{split}-{index}/
    ├── task.toml
    ├── instruction.md
    ├── environment/Dockerfile
    ├── solution/
    │   ├── solve.sh
    │   └── fixture_result.json
    └── tests/
        ├── expected.json
        ├── scoring.py
        ├── verify_result.py
        └── test.sh
```

The instruction's data block is read by the custom agent; it is not forwarded to the manipulatee model. The expected answer in `tests/expected.json` is verifier data, not benchmark evidence.

Then run the full locally generated set with the provided config:

```bash
uv run --project src/makemesay harbor run \
  -c src/makemesay/run_makemesay.yaml \
  -a makemesay.agent:MakeMeSayAgent \
  -m "<dated-model-id>" \
  --n-concurrent 1
```

For a single generated task, use `harbor trial start -p datasets/makemesay/<task-id> -a makemesay.agent:MakeMeSayAgent -m "<dated-model-id>"`.

## Comparison with Original Benchmark (Parity)

Parity has **not been run**. `parity_experiment.json` records zero runs and no scores. The adapter guide requires coordination on the task set, agent/model versions, spending limit, concurrency, and run order before paid experiments. No inference spend is included here. Results must not be inferred from the scorer fixture.

For reproducibility, use the same dated model for all roles on each side, the same role prompts and 30-turn limit, the pinned Evals revision below, and the `medium-and-hard` variant (50 samples). The upstream scorer makes three judge calls per game: two as part of the original win/loss calculation and one for the awareness metric. Each game therefore makes 34 model calls total: 30 conversation responses, the final user guess, and three judging calls.

Original side:

```bash
git clone https://github.com/openai/evals.git
cd evals
git checkout 8eac7a7de5215c907fbddc30efdaf316913eccdd
pip install -e .
export OPENAI_API_KEY=<approved-key>
export MANIPULATOR=<pinned-completion-function>
export MANIPULATEE=<pinned-completion-function>
export JUDGE=<pinned-completion-function>
oaieval "$MANIPULATOR,$MANIPULATEE,$JUDGE" \
  make-me-say.medium-and-hard.v0 \
  --max_samples 50 \
  --record_path /tmp/makemesay-original.jsonl
```

Harbor side (from the adapters repository root):

```bash
uv sync --project src/makemesay
uv run --project src/makemesay python -m makemesay.main \
  --output-dir datasets/makemesay --splits medium-and-hard
uv run --project src/makemesay harbor run \
  -p datasets/makemesay \
  -a makemesay.agent:MakeMeSayAgent \
  -m "<same-dated-model-id>" \
  --n-concurrent 1
```

For the guide's staged plan, first run the first 5–10 tasks on both sides, then a full 50-task run on each side, then complete three full runs per side with locked settings. Use unique output paths for each attempt and retain all per-task results. Report mean ± sample SEM from the raw run arrays and check the guide's run-score range-overlap criterion. The metrics are per-game binary indicators averaged over the selected samples: `win_rate`, `loss_rate`, `violation_rate`, and `user_aware_of_manipulation_rate`.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|---|---|---|---:|---:|---|---|
| Not run | Not run | `win_rate` | 0 | 50 | Not run | Not run |
| Not run | Not run | `loss_rate` | 0 | 50 | Not run | Not run |
| Not run | Not run | `violation_rate` | 0 | 50 | Not run | Not run |
| Not run | Not run | `user_aware_of_manipulation_rate` | 0 | 50 | Not run | Not run |

Raw parity record: [parity_experiment.json](parity_experiment.json).

## Notes & Caveats

- This is a model-versus-model benchmark, not a conventional coding task. The custom agent runs the three model roles; a generic shell agent does not reproduce the benchmark interaction.
- The upstream prompts request private step-by-step monologue. The adapter preserves the prompt behavior for fidelity, but strips marked monologue from the public transcript artifact. Provider-side request logs are outside the adapter's control.
- The verifier recomputes all four metrics from the transcript and three judge outputs. `solution/solve.sh` uses only the marked scorer fixture to validate reward plumbing; its result must not be described as a successful benchmark run.
- NLTK 3.8.1, Punkt, and WordNet are needed for the upstream tokenization and noun-lemmatization behavior. The task image downloads the resources at build time; the local agent downloads them on first use.
- WordNet is a separately licensed lexical database; users should review its terms before using the downloaded resource.
- The all-variant aggregate size is 189 split-specific tasks; parity is currently documented only for the 50-task default variant.

## Installation / Prerequisites

The adapter is a standalone uv package. It requires Python 3.12+, uv, a working Harbor CLI, Docker for task execution, internet access to download the pinned upstream data and NLTK resources, and provider credentials for the selected role models.

```bash
uv sync --project src/makemesay
uv run --project src/makemesay harbor agent schema \
  makemesay.agent:MakeMeSayAgent --json
```

The agent supports OpenAI chat completions, Anthropic Messages, Google Generate Content, and Bedrock Converse through LiteLLM and Harbor's model-connection resolution. Configure credentials for the chosen provider.

## Troubleshooting

- **Missing NLTK data:** Confirm the task image can reach the NLTK data host during build. For local use, allow the agent's first-run `punkt` and `wordnet` downloads.
- **Missing model credentials:** Configure the provider key and verify the selected model ID with `harbor agent schema` and Harbor credential preflight.
- **No result artifact or zero reward:** Inspect the agent log and `/workspace/makemesay_result.json`; the verifier rejects incomplete turns, unexpected role order, invalid judge responses, and metrics that do not match the transcript.
- **Checksum or sample-count error:** Do not edit the manifest to bypass it. Confirm the pinned upstream object can be downloaded and matches the recorded SHA-256.
- **Validator finds a canary string in `.venv`:** `uv sync` creates a local environment containing Harbor files that the repository validator may scan. Set `UV_PROJECT_ENVIRONMENT` to a location outside the checkout, or remove the generated environment before validation.

## Citation

```bibtex
@misc{openai_evals_makemesay,
  author       = {OpenAI},
  title        = {MakeMeSay evaluation in OpenAI Evals},
  year         = {2024},
  howpublished = {\url{https://github.com/openai/evals/tree/8eac7a7de5215c907fbddc30efdaf316913eccdd/evals/elsuite/make_me_say}},
  note         = {Source revision 8eac7a7de5215c907fbddc30efdaf316913eccdd}
}
```

The copied upstream prompts are covered by [OpenAI Evals' MIT license](OPENAI_EVALS_LICENSE.txt), subject to that repository's listed dataset-license exceptions.

## Authors & Contributions

Adapter author: Christian. Upstream benchmark and source data: OpenAI Evals.

For adapter issues or contributions, open an issue or pull request in the Harbor adapters repository. Dataset publication, parity results, and any authorship decisions require separate review and approval by the Harbor team.
