# ASI-Bench Harbor Adapter

Converts the public ASI-Bench seed31415 material into Harbor task directories. The adapter supports 46 of the 60 formal tasks; 14 tasks are excluded because they require network access or unsupported multimodal/LLM-judge scoring. Results are local and non-official.

## Generate tasks

```bash
cd src/asi-bench
uv sync
uv run asi-bench --output-dir /tmp/asi-bench --task-ids robotics.particle_filter --levels B1
```

The converter pins ASI revision `a88dd2bc174b8fbd604d5a23456d4af7fd354423` and HF seed31415 revision `0fa14219cafdbab634d8b3cfbce238a8735a214f`. It downloads public source material when `--source-dir` is not supplied.

Generated tasks use Harbor's `task.toml`, `instruction.md`, `environment/`, `solution/`, and `tests/` layout. Run them with the external Harbor CLI.

## Overview

This adapter converts public ASI-Bench seed31415 instances into Harbor tasks.

## What is ASI-Bench?

ASI-Bench is a scientific-agent benchmark with deterministic task scorers.

## Adapter Features

The adapter pins source revisions, preserves declared outputs, and runs the scorer in the Harbor verifier.

## Generated Task Structure

Generated tasks contain `task.toml`, `instruction.md`, `environment/`, `solution/`, and `tests/`.

## Run Evaluation

Use the external Harbor CLI against the generated dataset.

## Usage

Run `uv run asi-bench --output-dir /tmp/asi-bench --task-ids robotics.particle_filter --levels B1` from this adapter directory.

## Parity

Parity evidence is currently incomplete; results are local and non-official.

## Notes & Caveats

Seed42, network-required tasks, multimodal scorers, and LLM-judge tasks are excluded.

## Installation / Prerequisites

Install Python 3.11+, `uv`, Docker, and access to the pinned public ASI-Bench/Hugging Face sources.

## Citation

See the ASI-Bench repository for benchmark citation and attribution.

## Authors & Contributions

Contributions are reviewed through the Harbor adapters repository.

## Troubleshooting

Set `ASI_BENCH_SOURCE` to a complete ASI-Bench checkout when GitHub or Hugging Face downloads are unavailable.
