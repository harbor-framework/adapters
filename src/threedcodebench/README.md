## 3DCodeBench → Harbor Adapter

## Overview

3DCodeBench evaluates whether vision-language-model agents can act as procedural 3D modelers: given a reference description of an object, the model writes **Blender 5.0 Python** that builds the object as a mesh. The benchmark covers **212 object categories** drawn from the Infinigen procedural generators (furniture, tableware, plants, corals, creatures, …), one canonical instance per category (`<Category>_seed0`), each with a human-reviewed caption and a ground-truth Blender factory script.

This adapter targets the benchmark's **coding-agent, text-to-3D setting** (`tasks/coding_agent/` upstream, paper §4.3 / Table 2): the agent works in a sandbox with Blender available, writes `<Category>_seed0.py`, may execute and fix it, and is scored by re-executing its script independently.

- **Tasks:** 212 (all 3DCodeBench text-to-3D instances; 1 task per upstream instance, no exclusions).
- **Provenance:** paper [arXiv:2606.01057](https://arxiv.org/abs/2606.01057); code [gaoypeng/3dcodebench](https://github.com/gaoypeng/3dcodebench) pinned at `42c7780`; data [YipengGao/3DCode](https://huggingface.co/datasets/YipengGao/3DCode) folder `3DCodeBench/` pinned at revision `b9ebb35`. License: MIT.
- **Main adaptation choices:** the prompt is the upstream coding-agent prompt with only the working directory and Blender path substituted. Scoring calls the upstream render, export, Chamfer, SigLIP-2 and Uni3D scorers verbatim, so every metric in the paper's coding-agent table (Table 2) is reported; SigLIP-2 and Uni3D run on CPU. One upstream reference script with a crash bug (`FanCoral_seed0`) is patched (see Notes & Caveats). The image-to-3D track and the single-shot / multi-turn LLM tracks are not part of this adapter.

## What is 3DCodeBench?

3DCodeBench ([project page](https://3dcodebench.com), [paper](https://arxiv.org/abs/2606.01057)) benchmarks VLMs as procedural 3D modelers that translate text or image references into code for 3D modeling software. Procedural code yields deterministic, editable, engine-ready assets, but writing it requires fluency with Blender's Python API and code-level geometric reasoning. The paper evaluates 12 VLMs in single-shot, multi-turn (traceback feedback), and coding-agent settings (Claude Code, Codex CLI, Gemini CLI, Antigravity), and complements automatic metrics with a human-preference arena (3DCodeArena).

Upstream metrics: **executability** (script runs in Blender 5.0 without an exception, leaves at least one mesh, and the 4 reference views render), image-grounded similarity (**SigLIP-2**, DINOv3), 3D-shape metrics (**Chamfer distance** on exported GLBs, **Uni3D**), LLM-as-judge, and arena Elo. The coding-agent table (Table 2) reports the four in bold: executability, SigLIP-2 text-image similarity, Uni3D 3D-3D similarity, and Chamfer distance, the last three as conditional means over each run's successful tasks.

## Adapter Features

- **Pinned, automatic data management:** `main.py` downloads the pinned HF revision of `3DCodeBench/` and shallow-fetches the pinned upstream commit (or uses local copies via `--benchmark-dir` / `--upstream-dir`).
- **Stable task ids:** `ArmChair_seed0` → `armchair-seed0`; registry names `3dcodebench/<task-id>`.
- **Agent environment (`environment/Dockerfile`):** Ubuntu 24.04 + official Blender 5.0.0 Linux build (`blender` on `PATH`, `blender-python` for its bundled Python), plus `scipy`, `shapely`, `trimesh`, `scikit-image` in Blender's Python (scipy is allowed by the prompt; the reference factories import the others). CPU only; no GPU needed.
- **Upstream-faithful prompt:** `instruction.md` is the upstream `run_codex_agent.sh` prompt (agent-neutral wording) with `$WORK_DIR` → `/workspace`, `$BLENDER` → `blender`, and the 600 s time budget.
- **Isolated grading (`tests/Dockerfile`):** `[verifier] environment_mode = "separate"` with its own grading image: the same Blender layers as the agent image plus CPU PyTorch, `transformers`, `timm`, `open_clip_torch`, the Uni3D point encoder (pinned commit) and the SigLIP-2 / Uni3D weights (pinned Hugging Face commits, loaded offline). The agent's sandbox never contains these models. Only the agent's `/workspace/<Instance>.py` (and the optional `.agent_done` sentinel) are carried over as artifacts, so changes the agent made to its own sandbox cannot affect scoring. The instance name reaches `test.sh` through `[verifier] env` in `task.toml`; under `tests/`, only `reference/<Instance>.py` and `reference/<Instance>.txt` differ between tasks (see Notes & Caveats). A grader-internal error (including a crash of the model step) writes no reward, so it shows up as a failed trial rather than a score of 0.
- **Upstream-faithful scoring:** `tests/evaluate.py` copies the agent's script and runs the upstream code from `tests/upstream/` unmodified:
  1. `core/render.py` (CYCLES, 64 spp, 512 px, 600 s cap) → **executability** = `render_log.json` status `OK`; this is the reward (`reward.txt`, 0/1).
  2. `core/export_glb.py` (600 s cap) for the agent's script and for the hidden reference script.
  3. `metrics/shape_chamfer.py` functions (8192 points, unit-sphere normalisation, min over 4 yaws) → `cd`, `cd_yawmin`.
  4. `tests/neural_metrics.py`, which calls the functions of `metrics/text_image_similarity.py` (SigLIP-2 so400m-patch16-naflex; cosine between the caption and each of the 4 renders, averaged) → `siglip2_text_image`, and of `metrics/shape_uni3d.py` (Uni3D-Giant on 8192 points; cosine between generated and reference embeddings) → `uni3d_3d_3d`.

  All values go to `/logs/verifier/metrics.json`. Agent-produced GLBs or renders are never used, matching upstream's "bake the produced `.py` independently".
- **Oracle:** the ground-truth factory script for the instance.
- **Aggregation:** `aggregate_metrics.py` computes the Table 2 metrics for one or more job directories: executability, plus conditional and penalized means of Chamfer distance, SigLIP-2 and Uni3D, and mean ± sample SEM across runs.

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
│       ├── Dockerfile                  # grading image: Blender + CPU SigLIP-2 / Uni3D
│       ├── test.sh                     # runs evaluate.py with Blender's Python
│       ├── evaluate.py                 # render → export → Chamfer → neural metrics; writes reward.txt + metrics.json
│       ├── neural_metrics.py           # SigLIP-2 text-image and Uni3D 3D-3D similarity
│       ├── reference/
│       │   ├── ArmChair_seed0.py       # hidden reference (Chamfer / Uni3D target)
│       │   └── ArmChair_seed0.txt      # caption (text side of SigLIP-2)
│       └── upstream/                   # render.py, export_glb.py, shape_chamfer.py,
│                                       # text_image_similarity.py, shape_uni3d.py (verbatim)
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
        └── tests/{Dockerfile,test.sh,evaluate.py,neural_metrics.py}
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

The YAML defaults to the oracle agent; commented blocks show `claude-code` and `codex`. The job summary shows the mean reward (executability); all Table 2 metrics for a finished job:

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
- `--split` — `full` (default, all 212 tasks) or `parity` (the 50-task parity subset, see Parity)
- `--limit` — generate only the first N tasks (sorted by upstream instance name)
- `--overwrite` — overwrite existing task directories
- `--task-ids` — only these tasks; accepts Harbor ids (`armchair-seed0`) or upstream ids (`ArmChair_seed0`)
- `--benchmark-dir` — use a local copy of the HF `3DCodeBench/` folder instead of downloading
- `--upstream-dir` — use a local checkout of `gaoypeng/3dcodebench` instead of fetching the pinned commit

## Comparison with Original Benchmark (Parity)

**Status: oracle verified, scorers checked against the paper, parity run on a 50-task subset (3 runs per side).**

**Oracle.** Harbor `0.27.0`, local Docker, separate verifier container, 8 concurrent trials: 212/212 tasks pass (executability 1.000) with no trial errors. Against the reference, the oracle gets:

- Chamfer distance (yaw-min, conditional) 0.0007 over the 211 tasks with a valid reference mesh.
- Uni3D 3D–3D 0.987 over the same 211 tasks. It is not exactly 1 because the two GLBs are point-sampled independently.
- SigLIP-2 0.153 over all 212 tasks.

**Scorer check against Table 2.** Upstream publishes the scripts its coding agents wrote (HF `YipengGao/3DCode`, `3DCodeBench_ModelLogs/data/text_to_3D_agent.parquet`). The 212 GPT-5.4 mini + Codex CLI scripts were placed as the task solutions and run through the full Harbor pipeline: separate verifier, CPU models, `aggregate_metrics.py`. No model calls are involved, so this checks scoring only.

| Metric | Paper, Table 2 (GPT-5.4 mini, Codex CLI) | Harbor re-score of the same scripts |
|--------|------------------------------------------|-------------------------------------|
| Executability | 1.000 | 1.000 (212/212) |
| SigLIP-2 text-image (conditional) | 0.154 | 0.155 (n = 212) |
| Uni3D 3D–3D (conditional) | 0.450 | 0.444 (n = 211) |
| Chamfer distance (conditional) | 0.072 | 0.072 (`cd_yawmin`, n = 211) |

The remaining differences come from CPU instead of GPU inference, per-task sampling seeds and re-baked reference GLBs (see Notes & Caveats).

**Parity.** Both sides ran Codex CLI `0.171.0` with `gpt-5.4-mini` (model-default reasoning) through the same OpenAI-compatible endpoint, with the upstream prompt and a 600 s agent budget, 4 tasks at a time, with both sides running at the same time.
- **Original side:** upstream's `tasks/coding_agent/run_codex_agent.sh`, unchanged except that the Blender path is read from `$BLENDER`. It runs in a container on the same Ubuntu 24.04 / Blender 5.0.0 base as the Harbor task image. Scoring uses upstream's `core/render.py`, `core/export_glb.py` and `metrics/*.py`, with the same CPU models and 600 s caps as the Harbor verifier.
- **Harbor side:** Harbor's built-in `codex` agent.

All four Table 2 metrics are reported as mean ± sample SEM over 3 runs. Executability alone is close to saturated for coding agents in the paper (0.986–1.000), so the three similarity metrics carry most of the signal.

**Subset.** Parity ran on 50 of the 212 tasks (23.6%), drawn at random from the task ids sorted by name:
- the first 20 with `random.Random(0).sample(ids, 20)`, the initial sample;
- 30 more with `random.Random(1).sample(rest, 30)` from the remaining 192, which extended it to 50.

`uv run threedcodebench --split parity` generates exactly these tasks; the list is in `src/threedcodebench/parity.py`.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| codex@0.171.0 | gpt-5.4-mini | executability | 3 | 50 (23.6%) | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 |
| codex@0.171.0 | gpt-5.4-mini | SigLIP-2 text-image (conditional) | 3 | 50 (23.6%) | 0.1412 ± 0.0003 | 0.1456 ± 0.0011 |
| codex@0.171.0 | gpt-5.4-mini | Uni3D 3D–3D (conditional) | 3 | 50 (23.6%) | 0.4000 ± 0.0033 | 0.3901 ± 0.0022 |
| codex@0.171.0 | gpt-5.4-mini | Chamfer distance, `cd_yawmin` (conditional, lower is better) | 3 | 50 (23.6%) | 0.0762 ± 0.0038 | 0.0716 ± 0.0016 |

Per-run scores and the matching criterion (the run-score ranges of the two sides overlap):

| Metric | Original runs | Harbor runs | Ranges overlap |
|--------|---------------|-------------|----------------|
| Executability | 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000 | yes |
| SigLIP-2 | 0.1406, 0.1411, 0.1418 | 0.1455, 0.1476, 0.1438 | **no** |
| Uni3D | 0.4055, 0.4004, 0.3940 | 0.3880, 0.3877, 0.3945 | yes |
| CD (`cd_yawmin`) | 0.0772, 0.0691, 0.0822 | 0.0712, 0.0692, 0.0745 | yes |

All 300 agent runs finished within the 600 s budget and wrote `.agent_done`, and every script was executable.

One Harbor trial failed before its agent ran: `leafheart-seed0`, run 2, with `AgentSetupTimeoutError`. Codex installation took over 360 s while 16 trials were starting at once. That trial was re-run with `harbor jobs resume -f AgentSetupTimeoutError`.

Each run was executed as two jobs (20 tasks, then the other 30) because the subset was extended from 20 to 50 tasks.

Model calls cost $7.4: $3.75 on the Harbor side and $3.62 on the original side.

**SigLIP-2 investigation.** SigLIP-2 is the only metric whose ranges do not overlap. The gap was traced as follows; it points to sampling noise in the agents' outputs, not to a difference in the adapter.

- **Scoring is equivalent.** Both sides score the same text: the 150 scored prompts are byte-identical after stripping whitespace. They use the same upstream encoding functions and pinned weights. Every script from both sides was also re-scored by the other side's scorer:

  | Scripts | Harbor verifier | Upstream scorer |
  |---|---|---|
  | Harbor agents' 149 | 0.1456 | 0.1456 |
  | Original agents' 150 | 0.1411 | 0.1412 |

  The mean difference between scorers is below 1e-4, and 263 of 299 scores are identical. The rest differ because some agent scripts use unseeded randomness and build slightly different meshes on each execution. One further Harbor script hit the 600 s render cap in the upstream re-score, under heavy load. So the gap lies in the scripts, not in scoring.
- **Same agent configuration.** Capturing the API requests Codex sends under each side's invocation shows identical model parameters, tool definitions and system prompt. Only the working-directory path differs: in the environment context, the skills root, and the prompt's "Working directory" line.
- **The working directory changes exploration.** Upstream runs the agent inside the repository's results tree, next to the other tasks' outputs, while Harbor uses an empty `/workspace`. Original-side agents looked at parent directories in 57% of runs, against 9% on Harbor. Four of the 150 original runs saw another task's files, which accounts for about 0.0008 of the gap.
- **The outputs differ slightly in colour.** Harbor's renders have more coloured pixels (share 0.150 vs 0.123). Within a task, colour explains about a quarter of the SigLIP-2 gap. Neither this nor any other output feature differs significantly per task (paired tests, p ≥ 0.07).
- **The gap is within sampling noise.** Per task, Harbor minus original is +0.0045 with SE 0.0041 (paired, p = 0.27). Run-to-run variation within tasks implies an SD of about 0.0046 for a run's 50-task mean. The original side's three run means, however, fell within 0.0012 (SD 0.0006), which happens in about 2% of random run assignments, and that is why the ranges do not overlap. Uni3D and Chamfer, which depend only on geometry, do overlap.

Links:
- Original benchmark: [gaoypeng/3dcodebench](https://github.com/gaoypeng/3dcodebench) at `42c7780`.
- Parity fork (original side): [ZhenbangDu/3dcodebench, branch `harbor-parity`](https://github.com/ZhenbangDu/3dcodebench/tree/harbor-parity).
- Adapter PR: [harbor-framework/adapters#99](https://github.com/harbor-framework/adapters/pull/99).
- Dataset PR: [harbor-framework/harbor-datasets#297](https://github.com/harbor-framework/harbor-datasets/pull/297).
- Parity and oracle artifacts: [ZhenbangDu/threedcodebench-parity, pinned at `71bb391`](https://huggingface.co/datasets/ZhenbangDu/threedcodebench-parity/tree/71bb3917ccfb993c188dd75050c1d7274d0aa09f/adapters/threedcodebench). They include every attempt and the aggregation scripts. This is a personal dataset because the shared `harborframework/parity-experiments` repository is over Hugging Face's file limit ([adapters#129](https://github.com/harbor-framework/adapters/issues/129)). `SHA256SUMS` there lists all 11,798 files; its own SHA-256 is `12d7cef3f411205913c272b2777e3e14e579a656813bb4272f7102717351f51e`. To recompute the parity table from the uploaded files, run `python scripts/aggregate_parity_upload.py .` in that folder.

Reproduction:
- **Original side:** the parity fork [ZhenbangDu/3dcodebench, branch `harbor-parity`](https://github.com/ZhenbangDu/3dcodebench/tree/harbor-parity) (commit `c77ca22`, on upstream `42c7780`), directory `harbor_parity/`, with the 50 upstream instance names in `harbor_parity/parity_instances.txt`:
  ```bash
  docker build -f harbor_parity/Dockerfile.agent -t 3dcb-parity-agent:codex-0.171.0 harbor_parity
  docker build -f harbor_parity/Dockerfile.score -t 3dcb-parity-score:1 harbor_parity
  harbor_parity/prepare_data.sh /path/to/3DCodeBench harbor_parity/parity_instances.txt
  export OPENAI_API_KEY=... OPENAI_BASE_URL=...
  harbor_parity/run_agents.sh gpt-5.4-mini harbor_parity/parity_instances.txt runs/r1 4
  harbor_parity/score.sh gpt-5.4-mini harbor_parity/parity_instances.txt runs/r1
  # repeat for runs/r2 and runs/r3, then:
  python3 harbor_parity/summarize.py gpt-5.4-mini runs/r1 runs/r2 runs/r3
  ```
- **Harbor side:**
  ```bash
  (cd src/threedcodebench && uv run threedcodebench --split parity --output-dir ../../datasets/threedcodebench-parity)
  export OPENAI_API_KEY=... OPENAI_BASE_URL=...
  harbor run -p datasets/threedcodebench-parity -a codex -m openai/gpt-5.4-mini --ak version=0.171.0 -n 4 --job-name parity-r1
  # repeat as parity-r2 and parity-r3, then:
  python src/threedcodebench/aggregate_metrics.py jobs/parity-r1 jobs/parity-r2 jobs/parity-r3 --expected-tasks 50
  ```
- **Metric definitions:**
  - **Executability:** 0/1 per task, averaged over all tasks.
  - **`cd_yawmin`:** the symmetric squared Chamfer distance between unit-sphere-normalised point clouds, minimised over 4 yaw rotations (lower is better). It is averaged over tasks whose GLB was produced.
  - **SigLIP-2 and Uni3D:** cosine similarities (higher is better), averaged as described in Notes & Caveats.

## Notes & Caveats

- **Patched reference script (`FanCoral_seed0`).** The published factory computes `n_ep` from a geometry-dependent candidate count but hardcodes five endpoint indices; when the count is not 5 (as in a clean Blender 5.0.0 run), `csr_matrix` receives index and data arrays of different lengths and raises `ValueError`. The adapter adds `n_ep = len(endpoints)` after the hardcoded indices, in both the oracle and the hidden reference. The other 211 reference scripts are used unmodified. This will be reported upstream.
- **Prompt variant.** Upstream ships near-identical prompts per CLI; the Claude Code variant names its tools ("Use the Write tool …"). The adapter uses the agent-neutral Codex-CLI wording for all agents; parity runs use the same wording on both sides.
- **Paths.** `$WORK_DIR` becomes `/workspace` and the hardcoded Blender path becomes `blender` on `PATH`. Upstream's `$WORK_DIR` is `tasks/results/text_to_3D_agent/<model>/<Instance>/` inside the repository, next to other tasks' outputs. Harbor's `/workspace` is empty, so agents explore less and cannot see other tasks (see the SigLIP-2 investigation under Parity).
- **Scoring timeouts raised from 240 s / 180 s to 600 s.** Upstream caps the render and GLB-export Blender calls at 240 s and 180 s, tuned for GPU rendering. On the CPU-only image several valid reference scripts exceed them (`BasketBase`, `PalmTree` render; `Bed` export) when trials run concurrently, so both caps are 600 s (the dataset card targets scripts that finish in under 5 minutes on one CPU core). The original side of the parity experiments must use the same caps. If the render call times out, the export call is skipped, since it would re-run the same script under the same cap.
- **`ElkhornCoral_seed0` reference is an empty mesh.** Its published factory script runs and leaves one mesh object (so it counts as executable), but in Blender 5.0.0 the surface-construction step leaves 0 faces (6 vertices, 4 edges before solidify/remesh), so the exported GLB has no geometry. Chamfer distance is therefore undefined for this task (`chamfer_status = BAD_REF_MESH`) on both sides and it drops out of the conditional mean; executability is unaffected. This will be reported upstream.
- **Some reference scripts are not bit-for-bit deterministic.** A few coral/plant factories (`TableCoral`, `DiffGrowthBaseCoral`, `LeatherCoral`, `Seaweed`) produce slightly different meshes on repeated runs even with a fixed `PYTHONHASHSEED`. Upstream bakes the reference GLB once; the Harbor verifier re-bakes it in every trial (shipping baked GLBs would add ~2.7 GB to the dataset). Measured oracle self-distance over two full oracle runs: median ≈ 3e-4 per task; `TableCoral` reached 0.027 and 0.070 (comparable to the ≈ 0.07 agent average in the paper), while all other tasks stayed ≤ 0.014. The effect on the 211-task conditional mean is below 0.001, but per-task Chamfer for these instances is noisy.
- **Chamfer sampling seed.** Upstream draws all per-instance sampling seeds from one RNG shared across a whole results directory; the Harbor verifier scores each task alone with a fresh RNG seeded 0. This only changes which surface points are sampled (oracle self-distance ≈ 1e-3 versus typical agent CD ≈ 0.07).
- **Penalized Chamfer.** Upstream's penalized mean uses 1.5 × the worst valid CD of the run, which is not a per-task quantity, so it is computed by `aggregate_metrics.py` at the job level rather than in the reward.
- **Which Chamfer is "CD" in Table 2.** Upstream reports both the plain CD (`cd`) and the minimum over 4 yaw rotations (`cd_yawmin`). Replaying the published GPT-5.4 mini runs (see Parity) gives a conditional `cd_yawmin` of 0.072, equal to Table 2's CD column, while plain `cd` is 0.093, so `cd_yawmin` is the Table 2 metric. Both are recorded.
- **SigLIP-2 and Uni3D run on CPU.** Upstream runs both on GPU. The grader calls the upstream functions with `device="cpu"`, float32 (also upstream's Uni3D precision), the pinned weights, and 4 torch threads (`NEURAL_THREADS`, so results do not depend on the host's core count). The SigLIP-2 text is the instance's upstream `prompt_description.txt` (copied to `tests/reference/<Instance>.txt`), which is what upstream's `prompt.txt` holds for text-to-3D. Uni3D's farthest-point sampling picks a random start point and upstream does not seed it; the grader seeds torch with 0 so repeated scoring gives the same value. As with Chamfer, each task's point sampling uses a fresh RNG seeded 0 (upstream uses one RNG across a whole results directory). `siglip2_text_image` is the mean over the 4 renders (`siglip2_text_image_max` and per-view values are also recorded). `aggregate_metrics.py` reports conditional means (SigLIP-2 over tasks with all 4 renders; Uni3D over tasks with both GLBs) and penalized means (failures count as 0). The parity scripts were re-scored by both scorers (about 300 scripts). SigLIP-2 matches (mean difference below 1e-4). The Harbor verifier's Uni3D averages about 0.002 lower than upstream's; individual scripts differ by up to 0.13 because the two point-sample differently.
- **Per-task files in `tests/` live only at instance-named paths.** `tests/` is the Docker build context of the grading image. Docker's incremental context transfer can keep a file from an earlier build when its path, size and modification time all match. Files written in the same kernel clock tick share an mtime, so in one oracle run two tasks whose `test.sh` differed only in a same-length instance name (`Pillar_seed0` / `Pillow_seed0`, `TriangleShelf_seed0` / `TruncatedTree_seed0`) were graded with the neighbouring task's `test.sh`. Since then `test.sh` and every other shared path are identical across tasks. The instance comes from `[verifier] env` and the caption sits at `reference/<Instance>.txt`. `evaluate.py` also refuses to score (no reward) if the reference files for the instance are missing.
- **Not adapted:** the image-to-3D track (upstream also publishes image-to-3D coding-agent runs, with the four reference views under `3DCodeBench_ModelLogs/inputs/`, but the paper's coding-agent results, Table 2, are text-to-3D only); the single-shot and multi-turn LLM tracks; DINOv3 image-image similarity (a reference-view metric that is not in Table 2); and the LLM judge.
- **The upstream `.agent_done` sentinel** is kept in the prompt and recorded in `metrics.json` but, as upstream, does not affect the score.
- **Generated code runs inside the grader.** As upstream, scoring executes the agent's script (as root, inside the separate verifier container) in the same Blender process that writes the render log. A deliberately adversarial script could tamper with that container's scoring files; trajectories and the archived script (`artifacts/workspace/<Instance>.py`) allow such cases to be audited.
- **Resource use.** The agent image is about 1.8 GB; the grading image about 9.7 GB (6.6 GB of it model weights), built once and shared by all tasks through Docker layer caching. Verification re-runs the agent's script up to twice plus the reference once, then loads the two models one after the other (peak memory about 6.3 GB, so the grader requests 16 GB). With 4 threads the model step takes about 10 s (SigLIP-2) plus about 30 s (Uni3D) per task. The whole verifier takes about 1 minute per task (median, 8 concurrent trials).

## Installation / Prerequisites

- Docker (Linux containers) and Harbor (`uv tool install harbor`).
- Python ≥ 3.12 and `uv` for the adapter package:
  ```bash
  cd src/threedcodebench
  uv sync
  ```
- Network access to huggingface.co (dataset and, at image build, the SigLIP-2 / Uni3D weights), github.com (upstream helpers, Uni3D encoder) and download.blender.org (image build). Grading itself runs offline.
- About 12 GB of free disk for the two images.
- API keys for the agent/model you evaluate (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).

## Troubleshooting

- **Image build is slow or times out:** the Blender 5.0.0 archive is ~390 MB and the grading image also downloads ~6.6 GB of weights; build once with Docker layer caching (all tasks share the same layers, only the final `COPY` of `tests/` differs) or raise `--environment-build-timeout-multiplier`.
- **Model step fails (`neural_metrics.py`):** see `verifier/eval/neural_metrics.log`; the trial records a grader error and no reward. Out-of-memory is the usual cause when the runtime enforces a smaller memory limit than the 16 GB requested.
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
