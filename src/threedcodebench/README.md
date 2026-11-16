## 3DCodeBench → Harbor Adapter

## Overview

3DCodeBench evaluates whether vision-language-model agents can act as procedural 3D modelers: given a reference description of an object, the model writes **Blender 5.0 Python** that builds the object as a mesh. The benchmark covers **212 object categories** drawn from the Infinigen procedural generators (furniture, tableware, plants, corals, creatures, …), one canonical instance per category (`<Category>_seed0`), each with a human-reviewed caption and a ground-truth Blender factory script.

This adapter targets the benchmark's **coding-agent, text-to-3D setting** (`tasks/coding_agent/` upstream, paper §4.3 / Table 2): the agent works in a sandbox with Blender available, writes `<Category>_seed0.py`, may execute and fix it, and is scored by re-executing its script independently.

- **Tasks:** 212 (all 3DCodeBench text-to-3D instances; 1 task per upstream instance, no exclusions).
- **Provenance:** paper [arXiv:2606.01057](https://arxiv.org/abs/2606.01057); code [gaoypeng/3dcodebench](https://github.com/gaoypeng/3dcodebench) pinned at `42c7780`; data [YipengGao/3DCode](https://huggingface.co/datasets/YipengGao/3DCode) folder `3DCodeBench/` pinned at revision `b9ebb35`. License: MIT.
- **Main adaptation choices:** the prompt is the upstream coding-agent prompt with only the working directory and Blender path substituted; scoring calls the upstream render / export / Chamfer helpers verbatim; one upstream reference script with a crash bug (`FanCoral_seed0`) is patched (see Notes & Caveats). The image-to-3D track and the single-shot / multi-turn LLM tracks are not part of this adapter.

## What is 3DCodeBench?

3DCodeBench ([project page](https://3dcodebench.com), [paper](https://arxiv.org/abs/2606.01057)) benchmarks VLMs as procedural 3D modelers that translate text or image references into code for 3D modeling software. Procedural code yields deterministic, editable, engine-ready assets, but writing it requires fluency with Blender's Python API and code-level geometric reasoning. The paper evaluates 12 VLMs in single-shot, multi-turn (traceback feedback), and coding-agent settings (Claude Code, Codex CLI, Gemini CLI, Antigravity), and complements automatic metrics with a human-preference arena (3DCodeArena).

Upstream metrics: **executability** (script runs in Blender 5.0 without an exception, leaves at least one mesh, and the 4 reference views render), image-grounded similarity (SigLIP-2 / DINOv3, GPU), 3D-shape metrics (**Chamfer distance** on exported GLBs; Uni3D, GPU), LLM-as-judge, and arena Elo.

## Adapter Features

- **Pinned, automatic data management:** `main.py` downloads the pinned HF revision of `3DCodeBench/` and shallow-fetches the pinned upstream commit (or uses local copies via `--benchmark-dir` / `--upstream-dir`).
- **Stable task ids:** `ArmChair_seed0` → `armchair-seed0`; registry names `3dcodebench/<task-id>`.
- **Docker environment:** Ubuntu 24.04 + official Blender 5.0.0 Linux build (`blender` on `PATH`, `blender-python` for its bundled Python), plus `scipy`, `shapely`, `trimesh`, `scikit-image` in Blender's Python (scipy is allowed by the prompt; the reference factories import the others). CPU only; no GPU needed.
- **Upstream-faithful prompt:** `instruction.md` is the upstream `run_codex_agent.sh` prompt (agent-neutral wording) with `$WORK_DIR` → `/workspace`, `$BLENDER` → `blender`, and the 600 s time budget.
- **Isolated grading:** `[verifier] environment_mode = "separate"`. The verifier runs in a fresh container built from the same image; only the agent's `/workspace/<Instance>.py` (and the optional `.agent_done` sentinel) are carried over as artifacts, so changes the agent made to its own sandbox (Blender, Python packages, files) cannot affect scoring. A verifier-internal error writes no reward, so it shows up as a failed trial rather than a score of 0.
- **Upstream-faithful scoring:** `tests/evaluate.py` copies the agent's script and runs the upstream helpers from `tests/upstream/` unmodified:
  1. `core/render.py` (CYCLES, 64 spp, 512 px, 600 s cap) → **executability** = `render_log.json` status `OK`; this is the Harbor reward (`reward.txt`, 0/1).
  2. `core/export_glb.py` (600 s cap) for the agent's script and for the hidden reference script.
  3. `metrics/shape_chamfer.py` functions (8192 points, unit-sphere normalisation, min over 4 yaws) → `cd`, `cd_yawmin` in `/logs/verifier/metrics.json`.
  Agent-produced GLBs or renders are never used, matching upstream's "bake the produced `.py` independently".
- **Oracle:** the ground-truth factory script for the instance.
- **Aggregation:** `aggregate_metrics.py` computes executability plus conditional / penalized mean Chamfer distance for one or more Harbor job directories, and mean ± sample SEM across runs.

## Generated Task Structure

```
datasets/threedcodebench/
├── armchair-seed0/
│   ├── task.toml                       # name = "3dcodebench/armchair-seed0"
│   ├── instruction.md                  # upstream coding-agent prompt for ArmChair_seed0
│   ├── environment/
│   │   └── Dockerfile                  # Ubuntu 24.04 + Blender 5.0.0
│   ├── solution/
│   │   ├── solve.sh                    # copies the reference script into /workspace
│   │   └── ArmChair_seed0.py           # ground-truth factory script
│   └── tests/
│       ├── test.sh                     # runs evaluate.py with Blender's Python
│       ├── evaluate.py                 # render → export → Chamfer; writes reward.txt + metrics.json
│       ├── reference/ArmChair_seed0.py # hidden reference (for the Chamfer target)
│       └── upstream/                   # render.py, export_glb.py, shape_chamfer.py (verbatim)
└── ...                                 # 212 task directories
```

Adapter code layout:

```
src/threedcodebench/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── aggregate_metrics.py
├── pyproject.toml
├── run_threedcodebench.yaml
└── src/threedcodebench/
    ├── __init__.py
    ├── adapter.py                      # ThreeDCodeBenchAdapter
    ├── main.py
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/Dockerfile
        ├── solution/solve.sh
        └── tests/{test.sh,evaluate.py}
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the dataset is published:

```bash
# Oracle (reference solutions)
harbor run -d 3dcodebench/3dcodebench

# A coding agent
harbor run -d 3dcodebench/3dcodebench -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

```bash
# From the adapters repository root, after generating datasets/threedcodebench
harbor run -c src/threedcodebench/run_threedcodebench.yaml

# Or with a locally prepared dataset path
harbor run -p datasets/threedcodebench -a <agent_name> -m "<model_name>"

# Resume a previously started job
harbor job resume -p /path/to/jobs/<job_name>
```

The YAML defaults to the oracle agent; commented blocks show `claude-code` and `codex`. Shape metrics for a finished job:

```bash
python src/threedcodebench/aggregate_metrics.py jobs/<job_name> --expected-tasks 212
```

### Running Individual Trial

```bash
harbor trial start -p datasets/threedcodebench/armchair-seed0
harbor trial start -p datasets/threedcodebench/armchair-seed0 -a <agent_name> -m "<model_name>"
```

## Usage: Create Task Directories

```bash
cd src/threedcodebench
uv sync
uv run threedcodebench --output-dir ../../datasets/threedcodebench
```

Available flags:
- `--output-dir` — where tasks are written (default: `datasets/threedcodebench` at the repo root)
- `--limit` — generate only the first N tasks (sorted by upstream instance name)
- `--overwrite` — overwrite existing task directories
- `--task-ids` — only these tasks; accepts Harbor ids (`armchair-seed0`) or upstream ids (`ArmChair_seed0`)
- `--benchmark-dir` — use a local copy of the HF `3DCodeBench/` folder instead of downloading
- `--upstream-dir` — use a local checkout of `gaoypeng/3dcodebench` instead of fetching the pinned commit

## Comparison with Original Benchmark (Parity)

**Status: oracle verified, parity pending.** The oracle passes 212/212 tasks (executability 1.000) with near-zero Chamfer distance to the reference (conditional mean 0.0009 over the 211 tasks with a valid reference mesh), using Harbor `0.26.0`, local Docker and the separate verifier container. Parity experiments have not been run yet; the plan (to be confirmed with the Harbor team) is a coding agent from the upstream harness (Claude Code or Codex CLI) with the same pinned agent version, model, prompt and 600 s budget on both sides, reporting executability and conditional Chamfer distance as mean ± sample SEM over at least 3 runs on all 212 tasks. Executability alone is close to saturated for coding agents in the paper (0.986–1.000), so Chamfer distance is reported alongside it.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| TBD | TBD | executability | TBD | 212 (100%) | TBD | TBD |
| TBD | TBD | Chamfer distance (conditional) | TBD | 212 (100%) | TBD | TBD |

Reproduction (to be finalised with the parity fork):
- Original side: the upstream coding-agent scripts (`tasks/coding_agent/run_*_agent.sh`) at `42c7780`, scored with `core/render.py`, `core/export_glb.py` and `metrics/shape_chamfer.py`; the fork will fix the hardcoded Blender path and data directory.
- Harbor side:
  ```bash
  harbor run -c src/threedcodebench/run_threedcodebench.yaml -a <agent> -m "<model>"
  python src/threedcodebench/aggregate_metrics.py jobs/<job_name> --expected-tasks 212
  ```
- Executability is a 0/1 per task averaged over the 212 tasks; `cd` is the symmetric squared Chamfer distance between unit-sphere-normalised point clouds (lower is better), averaged over tasks whose GLB was produced.

## Notes & Caveats

- **Patched reference script (`FanCoral_seed0`).** The published factory computes `n_ep` from a geometry-dependent candidate count but hardcodes five endpoint indices; when the count is not 5 (as in a clean Blender 5.0.0 run), `csr_matrix` receives index and data arrays of different lengths and raises `ValueError`. The adapter adds `n_ep = len(endpoints)` after the hardcoded indices, in both the oracle and the hidden reference. The other 211 reference scripts are used unmodified. This will be reported upstream.
- **Prompt variant.** Upstream ships near-identical prompts per CLI; the Claude Code variant names its tools ("Use the Write tool …"). The adapter uses the agent-neutral Codex-CLI wording for all agents; parity runs use the same wording on both sides.
- **Paths.** `$WORK_DIR` becomes `/workspace` and the hardcoded Blender path becomes `blender` on `PATH`.
- **Scoring timeouts raised from 240 s / 180 s to 600 s.** Upstream caps the render and GLB-export Blender calls at 240 s and 180 s, tuned for GPU rendering. On the CPU-only image several valid reference scripts exceed them (`BasketBase`, `PalmTree` render; `Bed` export) when trials run concurrently, so both caps are 600 s (the dataset card targets scripts that finish in under 5 minutes on one CPU core). The original side of the parity experiments must use the same caps. If the render call times out, the export call is skipped, since it would re-run the same script under the same cap.
- **`ElkhornCoral_seed0` reference is an empty mesh.** Its published factory script runs and leaves one mesh object (so it counts as executable), but in Blender 5.0.0 the surface-construction step leaves 0 faces (6 vertices, 4 edges before solidify/remesh), so the exported GLB has no geometry. Chamfer distance is therefore undefined for this task (`chamfer_status = BAD_REF_MESH`) on both sides and it drops out of the conditional mean; executability is unaffected. This will be reported upstream.
- **Some reference scripts are not bit-for-bit deterministic.** A few coral/plant factories (`TableCoral`, `DiffGrowthBaseCoral`, `LeatherCoral`, `Seaweed`) produce slightly different meshes on repeated runs even with a fixed `PYTHONHASHSEED`. Upstream bakes the reference GLB once; the Harbor verifier re-bakes it in every trial (shipping baked GLBs would add ~2.7 GB to the dataset). Measured oracle self-distance over two full oracle runs: median ≈ 3e-4 per task; `TableCoral` reached 0.027 and 0.070 (comparable to the ≈ 0.07 agent average in the paper), while all other tasks stayed ≤ 0.014. The effect on the 211-task conditional mean is below 0.001, but per-task Chamfer for these instances is noisy.
- **Chamfer sampling seed.** Upstream draws all per-instance sampling seeds from one RNG shared across a whole results directory; the Harbor verifier scores each task alone with a fresh RNG seeded 0. This only changes which surface points are sampled (oracle self-distance ≈ 1e-3 versus typical agent CD ≈ 0.07).
- **Penalized Chamfer.** Upstream's penalized mean uses 1.5 × the worst valid CD of the run, which is not a per-task quantity, so it is computed by `aggregate_metrics.py` at the job level rather than in the reward.
- **Not adapted:** image-to-3D (the evaluation set ships no reference images; upstream renders them from the factories), single-shot and multi-turn LLM tracks, and GPU-based metrics (SigLIP-2, DINOv3, Uni3D) and the LLM judge.
- **The upstream `.agent_done` sentinel** is kept in the prompt and recorded in `metrics.json` but, as upstream, does not affect the score.
- **Generated code runs inside the grader.** As upstream, scoring executes the agent's script (as root, inside the separate verifier container) in the same Blender process that writes the render log. A deliberately adversarial script could tamper with that container's scoring files; trajectories and the archived script (`artifacts/workspace/<Instance>.py`) allow such cases to be audited.
- **Resource use.** The image is about 1.8 GB. Verification re-runs the agent's script up to twice plus the reference once; the median oracle verification takes about 40 s and the slowest (`BasketBase_seed0`, `PalmTree_seed0`, `Mushroom_seed0`) several minutes when many trials share a host.

## Installation / Prerequisites

- Docker (Linux containers) and Harbor (`uv tool install harbor`).
- Python ≥ 3.12 and `uv` for the adapter package:
  ```bash
  cd src/threedcodebench
  uv sync
  ```
- Network access to huggingface.co (dataset), github.com (upstream helpers) and download.blender.org (image build).
- API keys for the agent/model you evaluate (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).

## Troubleshooting

- **Image build is slow or times out:** the Blender 5.0.0 archive is ~390 MB; build once with Docker layer caching (all tasks share the same Dockerfile) or raise `--environment-build-timeout-multiplier`.
- **`ERR_TIMEOUT` on heavy scripts under high concurrency:** Cycles uses every visible core; reduce `-n` when running many trials on one host.
- **Inspecting a failure:** `verifier/metrics.json` has the stage statuses and tracebacks; `verifier/eval/generated/` holds the copied script, renders, GLB and Blender logs.

## Citation

```bibtex
@article{gao2026threedcodebench,
  title={3DCodeBench: Benchmarking Agentic Procedural 3D Modeling Via Code},
  author={Gao, Yipeng and Shu, Lei and Ye, Genzhi and Xiong, Xi and Makadia, Ameesh and Guo, Meiqi and Itti, Laurent and Chen, Jindong},
  journal={arXiv preprint arXiv:2606.01057},
  year={2026},
  url={https://arxiv.org/abs/2606.01057}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Zhenbang Du](mailto:zdu89@gatech.edu) ([@ZhenbangDu](https://github.com/ZhenbangDu)).

**Issues and Contributions:**
- Submit issues and pull requests to [harbor-framework/adapters](https://github.com/harbor-framework/adapters).

## Acknowledgement

> API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
