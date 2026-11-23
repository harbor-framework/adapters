# GSM8K for Harbor

## Overview

Generate Harbor tasks from OpenAI's original GSM8K train and test splits with fixed source and image revisions.

## What is GSM8K?

GSM8K is a set of English grade-school math problems. The source contains 7,473 train and 1,319 test examples. [OpenAI dataset source](https://github.com/openai/grade-school-math/tree/3101c7d5072418e28b9008a6636bde82a006892c)

## Adapter Features

- Preserve the original question, source row, and gold answer.
- Run a non-root agent and a separate offline verifier.
- Build a dataset manifest with Harbor Registry names and content digests.

## Generated Task Structure

Each task includes `task.toml`, `instruction.md`, `environment/Dockerfile`, `solution/solve.sh`, and `tests/`. The dataset directory includes `dataset.toml` and a source manifest.

## Installation / Prerequisites

Install `uv`, Python 3.12, and a functioning Docker or Podman backend. The adapter pins Harbor 0.27.0.

## Usage

From this adapter directory, run:

```bash
uv run gsm8k --output-dir ../../datasets/gsm8k-test
uv run gsm8k --split train --output-dir ../../datasets/gsm8k-train
```

Use `--source` for a local copy of the pinned input. Use `--limit` or `--task-ids` for a deterministic subset. Use `--split parity --task-ids ...` to generate an explicitly selected test subset. Use `--overwrite` to replace an existing adapter output.

## Run Evaluation

The proposed Registry identifiers are `gsm8k/gsm8k-test` and `gsm8k/gsm8k-train`. Registry commands become available after the maintainers register the datasets.

From the repository root, run `uv run --project src/gsm8k --locked harbor run -c src/gsm8k/run_gsm8k.yaml` against the generated test tasks. For train, use `uv run --project src/gsm8k --locked harbor run --path datasets/gsm8k-train --agent oracle --env docker`.

## Comparison with Original Benchmark

The native control suite checked 17,590 submissions against the pinned OpenAI scorer. The matched-model experiment is proposed. Its agent, precise model revision and budget are subject to maintainer coordination.

Prepare the eight-task sanity cohort with the command below. These zero-based source rows are spaced from row 0 to row 1318 across the fixed test split. The proposed scored experiment uses the full 1,319-task test split.

```bash
uv run --project src/gsm8k --locked gsm8k --split parity \
  --task-ids "$(paste -sd, src/gsm8k/parity-smoke-ids.txt)" \
  --output-dir datasets/gsm8k-parity-smoke
```

The original repository supplies the task data, first-marker answer extractor, and an example checkpoint sampler with calculator support. The proposed paired runner uses the same model prompt, single-turn configuration, and tool policy on both sides. The original side scores each raw completion with the pinned `is_correct`. A Harbor-compatible agent makes a separate model request and transports the extracted answer to the native verifier. The proposed shared-agent comparison covers this file transport and grading path. A standard terminal agent would require its own matched system configuration and score table.

See the paired harness and reproduction commands in [the proposed parity protocol](PARITY.md).

## Notes & Caveats

The Harbor prompt asks for a single number in `/app/output/answer.txt`. The verifier uses exact matching after stripping surrounding whitespace and valid thousands separators. The original completion extractor accepts answers embedded in additional text.

## Troubleshooting

For a missing reward, inspect `verifier/test-stdout.txt`, `verifier/test-stderr.txt`, and the Harbor trial result. The shell entry invokes `grade.py`, which writes `/logs/verifier/reward.txt`. The agent environment must allow UID 1001 to create `/app/output/answer.txt`.

## Citation

Karl Cobbe et al., *Training Verifiers to Solve Math Word Problems*, 2021. [Paper](https://arxiv.org/abs/2110.14168)

```bibtex
@misc{cobbe2021training,
  title = {Training Verifiers to Solve Math Word Problems},
  author = {Cobbe, Karl and Kosaraju, Vineet and Bavarian, Mohammad and others},
  year = {2021},
  eprint = {2110.14168},
  archivePrefix = {arXiv}
}
```

## Authors & Contributions

Original benchmark by Karl Cobbe and co-authors. Harbor adaptation by stein-wang0226. [OpenAI license](src/gsm8k/LICENSE.openai)
