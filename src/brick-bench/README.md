# BrickBench Adapter

## Overview

This adapter integrates **[BrickBench](https://brickben.ch/)** ([kulits/BrickAgent](https://github.com/kulits/BrickAgent), arXiv [2610.12452](https://arxiv.org/abs/2610.12452), MIT license) into Harbor. It converts all **300** text-conditioned LEGO design tasks across the benchmark's three constraint settings (`model`, `set`, `alt-build`) while preserving the upstream agent prompt template (`scripts/prompt.md`), BrickAgent Docker environment (`python:3.14.7-slim-trixie`, BrickNet colliders, LDraw snapshot, Mesa/Node viewer), physical validation (`scripts/verify.py`), Blender Cycles 8-view rendering (`bricknet-render`), and dependency-gated VQA evaluation (`google/gemma-4-31B-it`, revision `842da3794eaa0b77d5f08bae87a17459d91ff475`).

Pinned upstream revisions:

- **Benchmark & environment (`kulits/BrickAgent`):** `b3df55e36c669b22ef089b13db1ee841907d09b3`
- **LDraw parts snapshot (`kulits/ldraw-parts`):** `b61b905f1173f120f528be9521bb870619c36785`
- **Renderer (`kulits/BrickNet-Render` / PyPI `bricknet-render==0.1.0`):** `b49e8733782a5fa7040cc776b5fba8c55b0b894e`
- **VQA Judge (`google/gemma-4-31B-it`):** `842da3794eaa0b77d5f08bae87a17459d91ff475`
- **Oracle reference builds (`kulits/BrickBench-Runs`, MIT, `astra` valid builds):** `feecb33e7f2aa9d35e6e894c7333d44602c12ca0`

## What is BrickBench?

BrickBench evaluates coding agents on programmatic 3D LEGO set design from natural-language prompts using the **BrickAgent** environment (built on [BrickNet](https://github.com/kulits/BrickNet)'s connector graph and PyBullet rigid-body physics). An agent writes `build.py` (defining `build()`, which returns an `Assembly`) and exports `model.mpd`.

The benchmark spans **300 prompts** (10 prompts in each of 10 BrickLink Designer Program categories per setting) and **5,270 DSG VQA questions**:

| Setting | Tasks | VQA Questions | Constraint |
|---------|-------|---------------|------------|
| `model` | 100 (`model-001`..`model-100`) | 1,719 | 1–400 parts |
| `set` | 100 (`set-001`..`set-100`) | 2,369 | 400–4,000 parts |
| `alt-build` | 100 (`alt-001`..`alt-100`) | 1,182 | Restricted to the 783 parts of retail set 10698 (`inventory.json`) |

Upstream evaluates each submission on:
1. **Valid** (`scripts/verify.py`): rebuilds `build()`, verifies part limits / `BRICKAGENT_SET` inventory, exact authored joins, collision-free geometry (`TAU=1.0` LDU), and PyBullet rigid-body stability. Invalid submissions receive score `0`.
2. **VQA** (`scripts/vqa.py`): flattens the assembly (`scripts/flatten.py`), renders 8 views at `1024x1024` / 64 samples via `bricknet-render`, and evaluates each task's DSG question graph with `google/gemma-4-31B-it` (greedy, `enable_thinking=False`). A question counts only if it and every ancestor dependency are answered `yes` (`vqa_gated`).
3. **ELO** (`scripts/judge.py` + `scripts/elo.py`): multi-system pairwise Bradley–Terry ratings (`Align ELO`, `Design ELO`, combined `ELO`) computed across cohorts of systems.

## Adapter Features

- **Full 300-task coverage:** generates all 100 `model`, 100 `set`, and 100 `alt-build` tasks with stable registry names `brickbench/<task-id>` and BrickLink category metadata.
- **Byte-for-byte upstream prompts:** renders `instruction.md` from pinned `kulits/BrickAgent/scripts/prompt.md` with Jinja2 `StrictUndefined` and `keep_trailing_newline=True`.
- **Separate GPU verifier (`environment_mode = "separate"`):**
  - Agent container matches upstream `kulits/BrickAgent/Dockerfile` (`python:3.14.7-slim-trixie`, CPU-only, Mesa software EGL viewer, `WORKDIR /work`, read-only `BRICKAGENT_SET` for `alt-build`).
  - Verifier container (`tests/Dockerfile`, `python:3.13-slim-trixie` + `gpus = 1`) receives only `/work` via `artifacts = ["/work"]`, executes untrusted `build.py` verification as an unprivileged `builder` user against an isolated copy of `inventory.json`, flattens the rebuilt assembly, renders 8 views into `/logs/verifier/renders/`, and runs Gemma 4 31B VQA.
- **Multi-metric Harbor rewards:** writes `/logs/verifier/reward.json` with `reward` (`vqa_gated` when `valid == 1.0`, else `0.0`), `valid`, `vqa_gated`, and `vqa_flat`. Retained 8-view renders under `/logs/verifier/renders/` remain compatible with upstream pairwise `scripts/judge.py` and `scripts/elo.py`.
- **Read-only Hugging Face cache support:** when `google/gemma-4-31B-it@842da3794eaa0b77d5f08bae87a17459d91ff475` is pre-downloaded on the host and bind-mounted read-only at `/opt/hf-cache`, the verifier loads directly from disk with zero per-trial downloads and zero agent write access.
- **Stratified subsets:** `--split parity` selects 30 tasks (1 per category x 10 categories x 3 settings); `--split oracle-smoke` selects 9 tasks (3 per setting).

## Generated Task Structure

```
datasets/brick-bench/
└── <task-id>/                      # e.g., model-001, set-001, alt-001
    ├── task.toml                   # [task].name = "brickbench/<task-id>", separate GPU verifier
    ├── instruction.md              # Exact upstream scripts/prompt.md rendering
    ├── environment/
    │   ├── Dockerfile              # Upstream BrickAgent Python 3.14.7 CPU agent container
    │   └── inventory.json          # Present on alt-build tasks only
    ├── solution/
    │   ├── solve.sh                # Copies build.py to /work and exports /work/model.mpd
    │   └── build.py                # Pinned MIT reference build (kulits/BrickBench-Runs, astra)
    └── tests/
        ├── Dockerfile              # Separate Python 3.13 GPU verifier (bpy + bricknet-render + Gemma 4 31B)
        ├── test.sh                 # Verifier entrypoint checking /logs/verifier/reward.json
        ├── grade.py                # Upstream verify.py + flatten.py + bricknet-render + vqa.py
        ├── task.json               # Task prompt, split, category, and DSG question graph
        └── inventory.json          # Authoritative set 10698 inventory (alt-build tasks only)
```

## Run Evaluation / Harness

### Option 1: Registry (once published)

```bash
harbor run -d brickbench/brick-bench -a codex -m openai/gpt-5.4
```

### Option 2: Local reference config

```bash
cd src/brick-bench
uv sync
uv run brick-bench --output-dir datasets/brick-bench
harbor run -c run_brick-bench.yaml
```

### Option 3: Single task or subset

```bash
harbor trial start -p datasets/brick-bench/model-001 -a oracle
harbor run -p datasets/brick-bench -a oracle -n 1
```

## Usage: Create Task Directories

```bash
cd src/brick-bench
uv sync

# Generate all 300 tasks
uv run brick-bench --output-dir ../../datasets/brick-bench

# Generate the stratified 30-task parity subset (10 per setting, 1 per category)
uv run brick-bench --split parity --output-dir ../../datasets/brick-bench-parity

# Generate the 9-task E2E oracle smoke subset (3 per setting)
uv run brick-bench --split oracle-smoke --output-dir ../../datasets/brick-bench-smoke

# Generate specific tasks or limit count
uv run brick-bench --task-ids model-001 set-001 alt-001 --overwrite --output-dir /tmp/bb-sample
uv run brick-bench --split alt-build --limit 5 --output-dir /tmp/bb-alt5
```

## Comparison with Original Benchmark (Parity)

Parity is pending maintainer approval of the plan below (no agent parity runs have been executed yet).

| | |
|---|---|
| Agent / model | Pinned `codex` (exact npm version recorded at approval) + `gpt-5.6-luna` or agreed model, identical settings on both sides (`web_search=disabled`) |
| Original side | Upstream `kulits/BrickAgent@b3df55e36c669b22ef089b13db1ee841907d09b3` Docker image + `scripts/prompt.py` + `scripts/verify.py` + `scripts/flatten.py` + `bricknet-render` + `scripts/vqa.py` |
| Harbor side | This adapter via `run_brick-bench.yaml` (`--split parity`) using identical agent container, prompt, and separate GPU verifier |
| Judge | `google/gemma-4-31B-it` @ `842da3794eaa0b77d5f08bae87a17459d91ff475` (`do_sample=False`, `enable_thinking=False`) + `bricknet-render==0.1.0` (`--views 8 --resolution 1024x1024 --samples 64`) on both sides |
| Hardware / controls | 1x >=80 GB GPU (A100 80GB or RTX PRO 6000 96GB) for rendering + Gemma 4 31B VQA; read-only pre-cached HF snapshot; identical prompts, timeouts, and `BRICKAGENT_SET` inventory |
| Tasks | 30 stratified tasks (`--split parity`: 10% of 300 — 1 per BrickLink category across all 10 categories in each of `model`, `set`, `alt-build`, frozen at approval) |
| Runs | 6-task sanity check (2 per setting, both sides) -> 1 full 30-task run per side for cost/score check -> 3 full runs per side total |
| Metric | Primary: mean Valid-gated VQA (`vqa_gated`, 0 for invalid builds) and Valid rate, reported as `mean ± sample SEM` with range overlap; secondary: `vqa_flat` (and optional post-run pairwise `Align ELO` / `Design ELO` on retained renders) |
| Est. cost | TBD (~$135 API cost at ~$0.75/build for `gpt-5.6-luna` across 180 runs = 30 tasks x 3 runs x 2 sides, plus ~6–10 GPU-hours for Blender Cycles rendering + Gemma 4 31B VQA; exact cost reported after run 1) |

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Performance | Harbor Performance |
|-------|-------|--------|----------------|--------------|----------------------|--------------------|
| codex (planned) | TBD | Valid-gated VQA (`vqa_gated`) | 3 per side (planned) | 30 (`--split parity`, 10% of 300) | TBD | TBD |

### Planned Reproduction Commands

```bash
# 1. Generate the 30-task stratified parity cohort
cd src/brick-bench
uv run brick-bench --split parity --output-dir ../../datasets/brick-bench-parity

# 2. Harbor side (after maintainer approval & agent/model pinning)
harbor run -p ../../datasets/brick-bench-parity -a codex -m <pinned-model> -n 1

# 3. Original side (on the same 30 task IDs from kulits/BrickAgent@b3df55e3)
# Render prompt via scripts/prompt.py, run Codex in the upstream brickagent image,
# then verify with scripts/verify.py, render with bricknet-render, and score with scripts/vqa.py.
```

## Notes & Caveats

- **Oracle reference builds:** Upstream BrickBench is an open-ended creative 3D design benchmark and does not ship handcrafted ground-truth builds. The adapter's oracle solutions use the authors' MIT-licensed `astra` (GPT-6 Astra) builds from [kulits/BrickBench-Runs](https://huggingface.co/datasets/kulits/BrickBench-Runs) (`feecb33e7f2aa9d35e6e894c7333d44602c12ca0`), which pass physical validation on 300/300 tasks and average `0.954` VQA upstream. Because `astra` is a real model rather than an idealized VQA oracle, individual oracle tasks can score slightly below `1.0` on Gemma 4 31B VQA even when `valid == 1.0`.
- **Single-trial reward vs. pairwise ELO:** Harbor scores one trial in isolation, so `reward` is Valid-gated VQA (`vqa_gated` when `verify.py` passes, `0.0` otherwise), with `valid`, `vqa_gated`, and `vqa_flat` recorded in `/logs/verifier/reward.json`. Pairwise `Align ELO` and `Design ELO` require comparing multiple systems against each other and can be computed post-hoc over the saved `/logs/verifier/renders/` PNGs with upstream `scripts/judge.py` and `scripts/elo.py`.
- **Rebuilt MPD rendered for grading integrity:** Following upstream `scripts/verify.py` ("`build()` is rebuilt from the source and judged; whether the rebuild reproduces `model.mpd` is recorded, not judged"), `grade.py` flattens and renders the MPD exported from rebuilding `build.py` (while still requiring `/work/model.mpd` to exist and recording reproduction checks).
- **Separate verifier isolation:** Upstream's `verify.py` imports untrusted `build.py` in-process. The Harbor verifier runs in a separate container (`environment_mode = "separate"`) and executes `verify` in an unprivileged `builder` subprocess so agent code cannot modify `/tests/inventory.json`, `/tests/task.json`, or `/logs/verifier/reward.json`.
- **Hardware requirements:** Agent execution is CPU-only (`python:3.14.7-slim-trixie`). Verification requires an NVIDIA GPU with >=64 GB VRAM (80 GB+ recommended, e.g., A100 80GB or RTX PRO 6000 96GB) to load `google/gemma-4-31B-it` (~62 GB) in `bf16` and run Blender Cycles (`bpy>=5.1`).
- **Scope of WIP validation:** All 300 tasks are statically validated; full 300-task GPU oracle verification is deferred pending maintainer approval. E2E Harbor oracle and negative-control validation is recorded on 9 representative tasks (3 per setting).

## Installation / Prerequisites

- Python 3.11+ and `uv`
- Harbor CLI (`harbor>=0.27.0` recommended for `verifier.environment_mode = "separate"` with dedicated `[verifier.environment]`)
- Docker Engine with NVIDIA Container Toolkit (for GPU verification)
- >=80 GB GPU VRAM and ~150 GB free disk space on the verification host (for Docker images, BrickNet colliders/GLBs, and the ~62 GB `google/gemma-4-31B-it` checkpoint)

## Troubleshooting

- **Slow per-trial Hugging Face downloads:** Pre-download `google/gemma-4-31B-it` at revision `842da3794eaa0b77d5f08bae87a17459d91ff475` once on the host (`hf download google/gemma-4-31B-it --revision 842da3794eaa0b77d5f08bae87a17459d91ff475 --cache-dir /var/cache/brickbench-hf`) and mount `/var/cache/brickbench-hf` read-only at `/opt/hf-cache` via `environment.mounts` in `run_brick-bench.yaml`.
- **CUDA/OptiX unavailable for Blender Cycles:** Ensure the NVIDIA Container Toolkit exposes CUDA/EGL devices to Docker containers (`docker run --rm --gpus all ... nvidia-smi`), or set `BRICKBENCH_RENDER_DEVICE=CPU` for diagnostic software rendering.
- **Verifier OOM on <80 GB GPUs:** `google/gemma-4-31B-it` requires ~62 GB VRAM in native `dtype="auto"` (`bf16`). Run with `n_concurrent_trials: 1` on a single 80 GB+ GPU; `bricknet-render` runs in a separate subprocess before PyTorch loads Gemma 4 so GPU memory is fully released between stages.

## Citation

```bibtex
@misc{kulits2026brickbenchevaluatingagenticbrick,
      title={BrickBench: Evaluating Agentic Brick Design},
      author={Peter Kulits and Yiqing Xu and R. Kenny Jones and Cordelia Schmid and Jiajun Wu},
      year={2026},
      eprint={2610.12452},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2610.12452},
}
```

## Authors & Contributions

- **Original Benchmark:** Peter Kulits, Yiqing Xu, R. Kenny Jones, Cordelia Schmid, and Jiajun Wu ([kulits/BrickAgent](https://github.com/kulits/BrickAgent), [brickben.ch](https://brickben.ch/)).
- **Harbor Adapter:** Contributed by [Harbor adapter author](https://github.com/vyomakesh0728).
