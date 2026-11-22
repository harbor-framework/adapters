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

From the repository root, run `harbor run -c src/gsm8k/run_gsm8k.yaml` against the generated test tasks. For train, use `harbor run --path datasets/gsm8k-train --agent oracle --env docker`.

## Comparison with Original Benchmark

Matched model runs are pending coordination with the Harbor maintainers. The native control suite compares identical submitted bytes with the pinned OpenAI scorer.

## Notes & Caveats

The Harbor prompt asks for a single number in `/app/output/answer.txt`. The verifier uses exact matching after stripping surrounding whitespace and valid thousands separators. The original completion extractor accepts answers embedded in additional text.

## Citation

Karl Cobbe et al., *Training Verifiers to Solve Math Word Problems*, 2021. [Paper](https://arxiv.org/abs/2110.14168)

## Authors & Contributions

Original benchmark by Karl Cobbe and co-authors. Harbor adaptation by stein-wang0226. [OpenAI license](src/gsm8k/LICENSE.openai)
