# 4DCodeBench → Harbor Adapter

## Overview

This adapter converts [4DCodeBench](https://github.com/4DCodeBench/4DCodeBench) into Harbor tasks.

- **Task type:** inverse graphics of dynamic scenes. The agent watches a video and writes graphics code whose Blender render, camera, per-frame geometry and material trajectories reproduce the 4D scene.
- **Splits:** 100 synthetic cases, which have published reference 4D worlds, and 100 real-world cases, which have none. Each case becomes one Harbor task, 200 in all.
- **Upstream pin:** commit `6c466be34107d7f388f30f97bf059b68ba1a21b0`. Each generated task records the commit of the checkout it was generated from.
- **Scoring:** the original scorer (`python -m scorer`), unmodified, in a separate GPU verifier container. Its per-metric readings become Harbor rewards; nothing is re-implemented and no combined score is formed.
- **Status:** work in progress.
  - Implemented for both splits: task generation, the separate verifier, and the reward conversion.
  - Validated on a GPU, synthetic split only: the synthetic oracle on all 100 cases. The original scorer and the Harbor verifier produced identical readings on every case. That is scorer consistency, not a 100% oracle reward (see [Comparison with Original Benchmark](#comparison-with-original-benchmark-parity)).
  - Known oracle failures: on 8 of the 100 synthetic cases, some metrics fail identically on both sides. 6 liquid-only reference worlds fail upstream's own world gate, and 2 cases hit the upstream 32 GiB scorer memory limit. Only B_01 and B_04 score 1.0 on every applicable metric (see [Notes & Caveats](#notes--caveats)).
  - Real-world split: implemented but not validated. Its task generation is tested only with stand-in fixture files. No released real-world case has been generated, or scored on a GPU. Its oracle is unresolved, because no reference worlds exist.
  - Not done: parity. A plan is proposed in the parity section.

## What is 4DCodeBench?

4DCodeBench (Shen et al., 2026) benchmarks coding agents on reconstructing a dynamic scene from a single video as an explicit, reproducible 4D program.

- **What the agent delivers:**
  - `world/`: `camera.json`, `render.mp4`, `meshes/` and `dynamics/`, plus `solver/` for liquids.
  - `solution/`: an executable `build.sh` that rebuilds `world/` from nothing.
- **What is compared:**
  - the render against the reference video, on every case;
  - the geometry and dynamics against the reference world, on synthetic cases;
  - against estimates from off-the-shelf models, on real cases.
- **Metric families** (`docs/spec.md`):

  | Family | Metrics |
  |---|---|
  | Perceptual | DINOv3 similarity |
  | 2D dynamics | Dynamic IoU, Flow, Track2D |
  | 2.5D geometry | Depth error |
  | 3D geometry | Scene 3D |
  | 3D dynamics | Trajectory DTW, EMD step |

- Additional metrics (TIPS, GeoPhys, Uni3D, Occupancy DTW) and geometry-quality metrics are reported separately.

## Adapter Features

- **One task per case.** Task names are `4dcodebench/<kind>-<case>`, lowercased, for example `4dcodebench/synthetic-b-01`. `--split synthetic|real|all` selects cases.
- **The original instruction.**
  - `instruction.md` is the upstream `harness/agent_context/TASK.md`, rendered with the harness's own container paths.
  - The agent also gets the original `/task/` directory (`TASK.md`, `world-format.md`, `render-settings.md`) and `/input/reference.mp4`, exactly what `harness/runtime/infer.py` mounts.
- **The original agent image.**
  - `environment/Dockerfile` builds `FROM` the upstream agent image (CUDA 13, Blender 5.2, bpy, PyTorch, Taichi, Warp, FFmpeg and the public checker) and adds only the task context and the video.
  - GPU: `gpus = 1` in `task.toml`, plus `environment/docker-compose.yaml` with an NVIDIA reservation.
- **A separate verifier.**
  - `[verifier] environment_mode = "separate"`. `tests/Dockerfile` builds `FROM` the upstream scorer image with its checkpoints, and adds the case's private reference data under `/bench`.
  - Only `/workspace/world` and `/workspace/solution` cross from the agent (task `artifacts`), the two directories the upstream harness collects.
  - The verifier runs with `no-network`, as upstream does.
- **The original scorer, unchanged.**
  - `tests/run_verifier.py` writes the same manifest entry `harness/runtime/score.py` writes for a delivered run.
  - It runs `python -m scorer` with the upstream timeouts (1800 s per metric, 600 s per preparation) and thread settings.
  - The scorer's `results/` stays under `/logs/verifier/4dcodebench/` for inspection.
- **Harbor rewards** (`rewards.py`): `/logs/verifier/reward.json` holds finite numbers only, mapped as the benchmark's specification aggregates them:

  | Original reading | Harbor reward |
  |---|---|
  | number | unchanged |
  | `error` | the metric's worst value: 0, or 2 for `depth_error` (lower is better) |
  | `error` from a closed gate, on `mesh_*` / `interpenetration` | left out: geometry quality is averaged over runs that pass the world gate |
  | `not_applicable`, `excluded`, `uncomputable` | left out |

  - `executable` is 1 when both validation gates pass.
  - `4dcodebench_readings.json` records every original reading and its cause next to the Harbor value.
- **Dataset metric** (`metric.py`, written to the dataset root):
  - It averages each key over the trials that report it.
  - Harbor's default `mean` would instead count a metric that does not apply to a case (for example `depth_error` on synthetic cases) as 0.
- **Synthetic oracle.**
  - `solution/solve.sh` copies the published reference world into `/workspace/world`.
  - It installs `solution/build.sh`, a clearly labelled placeholder that exits 1. It exists because the scorer's world gate requires `solution/build.sh`, and the generating simulation programs are not released.
- **Real-world oracle.** Marked unresolved: `solve.sh` writes nothing and exits 1.
- **No custom agents.** Harbor's standard installed agents run against these tasks.

## Generated Task Structure

```
datasets/4dcodebench/
├── metric.py                         # dataset metric (Harbor uv-script)
└── synthetic-b-01/
    ├── task.toml                     # name, authors, GPU, separate verifier, artifacts
    ├── instruction.md                # rendered upstream TASK.md
    ├── environment/                  # agent image: FROM the upstream agent image
    │   ├── Dockerfile
    │   ├── docker-compose.yaml       # NVIDIA reservation
    │   ├── task/                     # TASK.md, world-format.md, render-settings.md
    │   └── input/reference.mp4
    ├── tests/                        # verifier image: FROM the upstream scorer image + checkpoints
    │   ├── Dockerfile
    │   ├── docker-compose.yaml
    │   ├── test.sh
    │   ├── run_verifier.py           # manifest, `python -m scorer`, reward conversion
    │   ├── rewards.py
    │   ├── case.json
    │   └── bench/                    # private: cases/<kind>/<case>/reference.mp4,
    │                                 #          data/<kind>/<case>/{world|annotation, estimates}
    └── solution/
        ├── solve.sh                  # synthetic: submit the reference world; real: UNRESOLVED
        ├── build.sh                  # synthetic only: oracle placeholder
        └── world/                    # synthetic only: the published reference world
```

The adapter package lives at `src/4dcodebench/src/harbor_4dcodebench/`: `adapter.py`, `main.py`, `rewards.py`, `metric.py`, `compare.py` and `task-template/`. The Python module is `harbor_4dcodebench` because a module name cannot start with a digit.

## Run Evaluation / Harness

Once the dataset is registered:

```bash
harbor run -d 4dcodebench/4dcodebench -a <agent> -m <model>
```

Before registration, from the adapters repository root, after generating tasks:

```bash
# oracle over both splits (real cases are unresolved and exit 1)
harbor run -c src/4dcodebench/run_4dcodebench.yaml

# synthetic oracle only
harbor run -c src/4dcodebench/run_4dcodebench_synthetic_oracle.yaml

# one task with an agent
harbor trial start -p datasets/4dcodebench/synthetic-b-01 -a claude-code -m anthropic/claude-opus-5-5
```

Pass `metrics: [{type: uv-script, kwargs: {script_path: datasets/4dcodebench/metric.py}}]`, as the configs do, so that aggregation skips the keys a case does not report. Harbor (0.27.0) does not pick up a local dataset's `metric.py` by itself. A plain `harbor run -p datasets/4dcodebench` therefore falls back to the default mean, which counts every key a trial does not report as 0. Use the configs above for local runs. A registered dataset uses `metric.py` only if its `dataset.toml` lists it under `[[files]]` (`harbor init --with-metric`).

We recommend reporting the synthetic and real-world splits separately, pending confirmation with the Harbor team. The two splits score different sets of metrics. A job over both splits averages each shared key (for example `semantic_dinov3`) over synthetic and real cases together, while the upstream README lists metrics per dataset. `metric.py` itself does not separate the splits. Run each split as its own job, with `--split` at generation or `task_names` in the config.

Each trial needs the locally built `4dcb/*` images ([Installation / Prerequisites](#installation--prerequisites)), including after registration. They are not pulled from a registry.

## Usage: Create Task Directories

```bash
cd src/4dcodebench
uv sync

# all 200 cases from a 4DCodeBench checkout whose cases/ and data/ were filled by
# its own scripts/download_data.py --estimates
uv run 4dcodebench --repo /path/to/4DCodeBench --output-dir ../../datasets/4dcodebench

# one case, data kept outside the checkout
uv run 4dcodebench --repo /path/to/4DCodeBench \
    --cases-root /data/4dcb/cases --data-root /data/4dcb/data \
    --task-ids synthetic/B_01 --output-dir ../../datasets/4dcodebench --overwrite
```

| Flag | Meaning |
|---|---|
| `--repo` | a 4DCodeBench checkout (read only): agent context and commit |
| `--cases-root`, `--data-root` | default `<repo>/cases`, `<repo>/data` (the upstream download layout) |
| `--split` | `all` (default), `synthetic`, `real` |
| `--task-ids` | task names (`synthetic-b-01`), `<kind>/<case>` or bare case names |
| `--limit`, `--overwrite` | standard adapter flags |
| `--agent-image` | default `4dcb/agent:dev` |
| `--scorer-image` | default `4dcb/scorer-checkpoints:dev` |
| `--agent-network`, `--agent-allowed-host` | `public` (default, as upstream) or `allowlist` |
| `--skip-incomplete` | skip cases with missing reference data instead of failing |

A case whose reference data is incomplete stops generation and lists the missing files.

## Comparison with Original Benchmark (Parity)

Parity has **not** been run. Agents, models, the subset and the number of runs are still to be agreed with the Harbor team.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Performance | Harbor Performance |
|-------|-------|--------|----------------|--------------|----------------------|--------------------|
| TBD | TBD | TBD | TBD | 200 (100%) | TBD | TBD |

**Proposed parity plan.** Nothing below has been run, and the plan is to be agreed with the Harbor team before any run.

- **Split and cases.**
  - Start with the synthetic split, where every metric family is scored against a reference world.
  - Use a subset of about 10 to 20 cases, fixed before any run, with at least one case from each scene family (B, CK, G, HM, LI, ML, PF, S, TM, Z).
  - Leave the 6 liquid-only and the 2 memory-limited cases out of the first subset. Their scores are set by a gate or a memory failure rather than by the agent. If they are kept in the dataset, report them separately.
  - The real-world split follows once its verifier has been checked on real cases (see the cross-scoring bullet below).
- **The same agent on both sides.** One agent CLI and model, at a pinned CLI version.
  - **Original side:** upstream `harness/runtime/infer.py` with the `4dcb/agent:dev` image and the upstream command line. For Claude Code that is `--model`, `--effort`, `--permission-mode dontAsk` and the upstream `--allowedTools` list, with a 6 h budget per run.
  - **Harbor side:** the same CLI through Harbor's installed agent, with the same model, effort, permission mode and allowed tools (agent kwargs), and the same 21,600 s timeout from `task.toml`.
  - **Shared settings:** the same image IDs, the same GPU type, upstream's scorer resources (8 CPUs, 32 GiB, 1 GPU) and the same agent network setting.
- **Runs.** At least 3 runs per side on the same cases. The parity contract requires at least 2.
- **Scoring and comparison.**
  - **Original side:** upstream `harness/runtime/score.py` on the delivered runs.
  - **Harbor side:** the verifier output in `verifier/4dcodebench/results/`.
  - **Same conversion:** apply `rewards.py` to the original scorer's output too, so that any difference comes from the agent runs, not from the reward mapping.
  - **Report**, per metric: the mean over cases for each run, then the mean ± SEM over runs on each side, with `executable` as the executability rate. Add a per-case, per-run ledger, and check that the run ranges overlap.
- **Cross-scoring check.**
  - Score each world delivered in an original run with the Harbor verifier, and each Harbor-delivered world with the original scorer, and compare them with `4dcodebench-compare --atol 0`.
  - This separates scorer differences (none are expected) from agent variance.
  - It also exercises the real-world verifier on real cases.
- **Artifacts to keep:**
  - provenance: adapter and upstream commits, image IDs, CLI versions, model IDs, the Harbor version;
  - original side: the run directories (`run.json`, transcripts, the delivered `world/` and `solution/`, `results/`);
  - Harbor side: the trial directories and job configs;
  - the ledger.

  No tokens and no gated weights.
- **Cost.**
  - **Original runs:** token usage and USD from upstream `harness/runtime/cost.py`, which uses LiteLLM's price table at a pinned revision.
  - **Harbor runs:** the token usage and cost Harbor records.
  - **Both sides:** GPU hours (wall clock times GPUs).
  - **Reporting:** these go into `parity_costs`.
  - **Budgeting:** the upper bound is cases × runs × 2 sides × 6 h of agent time.
- **Real-world dependency.** Real-world scoring needs no reference world: it uses the video and the published estimates. Harbor, however, asks for oracle validation before parity, so real-world parity waits for the maintainers' decision on the real-world oracle. In the meantime, the cross-scoring check gives scorer-consistency evidence on real cases.
- **After the initial PR**, in order:
  1. The plan is approved.
  2. Runs.
  3. Upload to `harborframework/parity-experiments` (`parity_pr`).
  4. `parity_experiment.json`, the table above, and `parity_costs`.
  5. Registration in `harbor-datasets`, with `metric.py` listed under `[[files]]` (`dataset_pr`).
  6. `adapter_pr`.

**Synthetic oracle check.** It compares the original scorer's `--sanity` readings (the reference world scored against itself) with the Harbor verifier's readings on the same world, case by case. Prepare the data, checkpoints and images first (see [Installation / Prerequisites](#installation--prerequisites)). Below, `/data/4dcb` holds `cases/` and `data/` as `scripts/fetch_case.py` writes them.

```bash
# 1. generate the task from the downloaded data, before any original-side run (from src/4dcodebench)
uv run 4dcodebench --repo /path/to/4DCodeBench --cases-root /data/4dcb/cases \
    --data-root /data/4dcb/data --task-ids synthetic/B_01 --output-dir ../../datasets/4dcodebench

# 2. original side, on an isolated copy of the case's data (from the adapters repository root)
mkdir -p /data/4dcb/orig-data/synthetic
cp -a /data/4dcb/data/synthetic/B_01 /data/4dcb/orig-data/synthetic/
bash src/4dcodebench/scripts/run_original_sanity.sh \
    /data/4dcb/cases /data/4dcb/orig-data /data/4dcb/checkpoints synthetic/B_01 sanity-1

# 3. Harbor side: the oracle on the generated task
harbor trial start -p datasets/4dcodebench/synthetic-b-01 -a oracle --trials-dir trials --trial-name b01-oracle-1

# 4. exact comparison: any difference in a state, a gate verdict or a number fails
(cd src/4dcodebench && uv run 4dcodebench-compare --atol 0 \
    --original /data/4dcb/orig-data/synthetic/B_01/sanity-1/results \
    --harbor ../../trials/b01-oracle-1/verifier/4dcodebench/results)
```

- **Use a copy for the original side.** `run_original_sanity.sh` mounts its data root read-write, as the upstream scorer expects, and writes into `<data root>/<kind>/<case>/`:
  - `solution/build.sh`, the placeholder the world gate requires beside the scored world, since the released data has none;
  - `<run name>/results/`.

  The upstream scorer can also write a liquid tracer cache into the world it scores, under `world/solver/` (`scorer/liquid.py`, `prepare`). On the original side, that world is the reference world in the data root. Run it on a copy, as above, so the downloaded reference data stays as published. Otherwise a later task generation would package the extra files with the reference world.
- **A new run name each time.** The scorer merges into an existing `reward.json`, so every original run needs a new run name: the fifth argument, default `sanity`, as upstream `--sanity`.
- **Why `--atol 0`.** With `--atol 0`, any numeric difference fails the comparison. Without `--atol`, numeric differences are printed but do not fail it.

This oracle comparison is not parity: it replays the same world through both scoring paths and involves no agent. Results:

| Cases | Original runs per case | Harbor oracle runs per case | Cases with any reading that differs | Harbor `executable` = 1 | Every applicable metric computed | Every applicable metric at 1.0 |
|-------|------------------------|-----------------------------|-------------------------------------|-------------------------|----------------------------------|--------------------------------|
| synthetic/B_01 (first check) | 2 | 2 | 0 | 1 of 1 | 1 of 1 | 1 of 1 |
| all 100 synthetic | 1 | 1 | 0 of 100 (all 18 readings, both gate verdicts; every numeric difference 0) | 94 of 100 | 92 of 100 | 2 of 100 (B_01, B_04) |

How the 100 cases split:

| Group | Cases | What happened, identically on both sides |
|-------|-------|-------------------------------------------|
| Gate open, every applicable metric computed | 92 | The oracle scores the reference world's own ceiling (see [Notes & Caveats](#notes--caveats)). |
| Gate open, some metrics `error` | 2: G_02 (11 world metrics), S_02 (`interpenetration`) | A scorer worker was killed under the 32 GiB memory limit that upstream's runtime template sets for the scorer and that this adapter keeps. |
| World gate closed (`no_world: Missing world/dynamics/`), `executable` 0 | 6: B_09, B_11, B_13, B_14, B_19, B_28 | Liquid-only reference worlds as published; upstream's gate rejects them. The three video-side metrics are still computed. |

Also checked on every case:
- The world Harbor collected from the agent container, which it hands to the verifier, was byte-identical to the published reference world.
- Harbor's `reward.json` is what `rewards.py` derives from the scorer's output.
- No Harbor trial raised an exception, and no case was retried.
- The two `reward.detail.json` files differ only in the reference world's mount path and in the timing field `dynamics_seconds`.

The 100-case run used the same host and images as B_01. Software: 4DCodeBench `6c466be` (unmodified), this adapter at `20c9878` plus the liquid-only generation change described in Notes & Caveats, and Harbor 0.27.0. Data: the Hugging Face revisions pinned in `scripts/fetch_case.py`, checked against SHA-256 before and after the run.

It ran three cases at a time. Each case ran the original scorer, then the Harbor oracle trial. The whole run took 9.9 h of wall clock. Under that contention, a Harbor trial (image build, oracle, verifier) took a median of 407 s and at most 2040 s. Peak GPU memory, summed over the concurrent containers, was 17.8 GiB.

Per-case results and the scripts that produced them are kept with the oracle evidence, outside this repository.

On the original side, the placeholder `build.sh` is needed because the scorer's world gate requires `solution/build.sh` beside the scored world. Without it, the original `--sanity` run marks every geometry metric `error`. The upstream repository is not touched.

## Notes & Caveats

- **Validation status.**
  - Verified on a GPU: the synthetic oracle on all 100 cases, one original and one Harbor run each, compared with exact equality. The results, and the 8 cases that do not reach their full ceiling, are in the parity section above.
  - First check, synthetic/B_01:
    - Setup: RTX A6000 48 GB, driver 580.119.02, Docker 29.10.0, Harbor 0.27.0, 4DCodeBench `6c466be`, adapter `20c9878`.
    - Runs: the original scorer twice (`run_original_sanity.sh`) and the Harbor oracle twice.
    - Agreement: all 18 readings and both gate verdicts are identical across the four runs. `4dcodebench-compare` was run four times (original 1 vs Harbor 1, original 2 vs Harbor 2, original 1 vs 2, Harbor 1 vs 2), and each numeric difference was 0 in every comparison.
    - Scores: the 14 applicable metrics are 1.0 and `executable` is 1.0. Flow, Track2D, Depth and Uni3D MoGe are `not_applicable` on synthetic cases.
    - Cost: each Harbor oracle trial took 130–140 s once the images were built. The scorer's peak GPU memory was 3.6 GiB.
  - `tests/test_recorded_outputs.py` pins the reward conversion and the comparison to recorded scorer outputs: B_01 (gate open), B_09 (world gate closed) and S_02 (one metric `error`).
  - Real-world split: implemented, not validated.
    - Unit tests generate real-world tasks from stand-in fixture files and run the generated verifier against a stand-in scorer.
    - No released real-world case has been generated, and none has been scored by the real scorer on a GPU.
    - The real-only metrics (`uni3d_moge_scene`, `flow_distribution`, `track2d_dtw`, `depth_error`) and the `annotation/` path have therefore never gone through a GPU run.
  - Not run: parity (see the proposed plan in the parity section).
- **What the oracle's reward means.**
  - The synthetic oracle's score is the case's per-metric ceiling: the reference world scored against itself, the quantity upstream `--sanity` reports.
  - That ceiling is 1.0 on every applicable metric only for B_01 and B_04.
    - The quality checks score the reference meshes themselves, and 83 of the 100 cases are below 1 on at least one of them. These checks are `interpenetration`, `mesh_watertight`, `mesh_manifold`, `mesh_clean_faces` and `mesh_no_self_intersection`, with lowest values between 0.56 and 0.62.
    - `scene_3d`, `uni3d_point_scene`, `trajectory_dtw`, `emd_step`, `occupancy_dtw` and `geophys_dinov3` fall below 1 by at most 6e-5.
    - `dynamic_iou`, `semantic_dinov3` and `semantic_tips` are exactly 1 wherever computed.
  - No metric is normalised or thresholded to make the oracle pass.
  - Validation means the Harbor readings match the original `--sanity` readings case by case.
  - Harbor's oracle rule asks for 100% reward on all tasks. With the released data and the upstream scorer configuration, that is not reachable:
    - the ceiling is below 1 on most reference worlds;
    - 6 published worlds fail upstream's own gate;
    - 2 cases exceed upstream's scorer memory limit;
    - the real split has no reference solution.
  - Exact agreement with the original scorer on 100 of 100 cases is scorer consistency, not a 100% oracle reward. How Harbor's rule should apply here needs confirmation from the Harbor team.
- **Upstream issue: liquid-only synthetic worlds without `dynamics/`.**
  - Some released synthetic worlds hold `world/solver/` (an identity-less liquid) and no `world/dynamics/`.
  - Upstream's world gate (`scorer/gate.py`, `WORLD_DIRECTORIES`) and checker (`checker/check.py`) both require `world/dynamics/`. So the original scorer closes the world gate (`no_world`) on these published reference worlds; the original `--sanity` run fails them too.
  - The likely cause: `unpack` in upstream `scripts/download_data.py` creates `dynamics/` only when it writes an archive into it.
  - The adapter does not add an empty `dynamics/` or change the gate, because either would change scores.
  - Task generation takes such a world as published: when `world/solver/` exists and `world/dynamics/` does not, `world/dynamics` is dropped from the case's required data (`required_data` in `adapter.py`, also written to `tests/case.json`). Everything else is still required, and a synthetic world with neither directory is still reported as incomplete.
  - The generated task's oracle therefore delivers the world without `dynamics/`, and the scorer closes the world gate exactly as the original `--sanity` run does.
  - Affected cases at the pinned data revision: B_09, B_11, B_13, B_14, B_19 and B_28.
    - On all six, the original and Harbor readings are identical: `no_world: Missing world/dynamics/`, `executable` 0.
    - All 11 world metrics are `error`. In Harbor's reward, the 6 scene and dynamics metrics become 0, and the 5 geometry-quality keys are omitted.
    - `semantic_dinov3`, `semantic_tips` and `geophys_dinov3` are still computed.
  - A separate diagnostic, not applied to any task: on an isolated copy of B_09 with an empty `world/dynamics/` added, both sides passed the gate and agreed exactly, with the world metrics at their ceiling. That points to the missing directory, not the world's content, as the cause.
  - Upstream status: open. It has not yet been reported to the 4DCodeBench repository.
  - Whether to keep these six tasks, exclude them, or wait for an upstream fix is to be agreed with the Harbor team. The adapter guide asks for cases with an oracle that cannot be fixed to be documented and excluded.
- **Scorer memory limit.**
  - The verifier keeps upstream's `[scorer.environment]`: 8 CPUs and 32 GiB (`memory_mb = 32768`).
  - On G_02 and S_02, a metric worker was killed under that limit, in the original container and in the Harbor verifier alike.
    - The validation host's kernel log confirms it: four memory-cgroup OOM kills of a scorer `python` process, one inside each of the four runs (G_02 and S_02, original and Harbor).
    - Both sides report the same `error` readings: 11 world metrics on G_02, and `interpenetration` on S_02.
  - Raising the limit would depart from upstream's resources, so it was not changed. Whether to keep the upstream limit is to be agreed with the Harbor team.
- **The oracle's `build.sh` is a placeholder.**
  - It exists only because the world gate checks that the file is there.
  - It states that it is not the program that produced the reference world, and it exits 1.
  - The authors' simulation programs are not released.
- **Real-world oracle: unresolved.** The real split has no reference 4D world. Its `solve.sh` exits 1, and no reconstruction is fabricated. Accepting it needs a separate decision with the Harbor team.
- **Primary reward: unresolved.**
  - The scorer writes per-metric readings only. The paper's Overall score (the average of the five families) is not implemented upstream, so the adapter forms no combined score.
  - It also adds no pass/fail threshold.
  - Which key, if any, Harbor Index should treat as primary is open.
- **Reward scales are the original ones.**
  - Every key is in [0, 1] with higher better, except `depth_error`, which is in [0, 2] with lower better, as upstream defines it.
  - The adapter does not rescale or invert it. Consumers that assume "higher is better in [0, 1]" must handle this key.
- **Mapping non-numeric readings.**
  - `error` becomes the worst value, following `docs/spec.md` ("When computing aggregates, `error` is assigned the metric's worst possible value").
  - The upstream viewer instead averages metrics over executable runs only. The raw readings in `4dcodebench_readings.json` support either aggregation.
- **`executable` differs slightly from upstream.**
  - Harbor's `executable` is the gate verdict.
  - The upstream viewer's executability also requires the agent CLI's exit status to be 0. Harbor records agent failures separately.
- **`metric.py` aggregates over trials, not per case.** It equals the original per-case-then-mean whenever every case contributes the same number of trials.
- **Agent network.**
  - Upstream gives the agent the default (public) network, which this adapter keeps.
  - The synthetic reference worlds are public on Hugging Face, so an agent with internet access could fetch its case's answer, upstream and here alike.
  - `--agent-network allowlist` restricts the agent to its inference host. That would be a deviation that parity must apply on both sides.
- **No leakage through packaging.**
  - The agent image is built from `environment/` only: the task context and the video.
  - Reference worlds, annotations, estimates and checkpoints are only in the verifier image (`tests/`) and in `solution/`, which Harbor uploads only for the oracle agent.
- **Licensing and redistribution.**
  - 23 of the 100 real videos are not redistributed by the authors. They are rebuilt locally by the dataset's `prepare_videos.py`, and generated tasks contain them.
  - The Hugging Face datasets declare no licence.
  - Both must be settled before publishing the dataset to the registry.
- **Dataset size.**
  - Synthetic reference worlds occupy about 65 GB once unpacked (upstream README); B_01 alone is about 11 MB.
  - Generation hard-links them into `tests/bench/` and `solution/world/` when the filesystem allows.
  - Every generated task carries its case's private reference data, so the generated dataset is roughly as large as the downloaded data. Where a registered dataset of this size should live (harbor-datasets or a Hugging Face mirror) is to be agreed with the Harbor team.
- **Images.**
  - On the validation host, the built images took about 35 minutes. Their disk usage was: `4dcb/sim-base:dev` 24.6 GB, `4dcb/agent:dev` 28.5 GB, `4dcb/scorer:dev` 35.1 GB and `4dcb/scorer-checkpoints:dev` 48.4 GB. These share layers, so the total is less than the sum.
  - `4dcb/scorer-checkpoints:dev` contains the gated DINOv3 weights. Keep it local, and do not push it to a public registry.
- **GPU reservations.** `task.toml` sets `gpus = 1` for both containers. The agent's `environment/docker-compose.yaml` reserves all GPUs, as upstream `infer.py` passes `--gpus all`, while the verifier reserves one. Only single-GPU hosts have been tested.
- **Unpinned agent CLIs.** The upstream agent image installs the Claude Code and Codex CLIs unpinned. Parity must pin the agent versions on both sides.

## Installation / Prerequisites

1. **Harbor and uv:** the Harbor CLI (`uv tool install harbor`) and `uv`.
2. **Upstream checkout and data.** A 4DCodeBench checkout, with its data downloaded by its own script, into the checkout or elsewhere:

   ```bash
   python scripts/download_data.py --estimates
   ```

   Synthetic reference worlds occupy about 65 GB once unpacked, and the estimates 53 GB. For a few cases only, `scripts/fetch_case.py` downloads the same files from the same datasets at pinned revisions, checks their SHA-256 against the Hub, and unpacks worlds with the upstream `unpack`:

   ```bash
   # from src/4dcodebench; about 13 MB for B_01
   uv run scripts/fetch_case.py --repo /path/to/4DCodeBench --root /data/4dcb synthetic/B_01
   ```
3. **Checkpoints** for the scorer, about 6.7 GB. They require approved access to the gated `facebook/dinov3-vitl16-pretrain-lvd1689m` on Hugging Face:

   ```bash
   # in the 4DCodeBench checkout
   scripts/download_checkpoints.sh /data/4dcb/checkpoints
   ```

4. **Images.** A Linux host with an NVIDIA GPU, a driver that supports CUDA 13, Docker and the NVIDIA Container Toolkit. Build the images once:

   ```bash
   # from the adapters repository root
   bash src/4dcodebench/scripts/build_images.sh /path/to/4DCodeBench /data/4dcb/checkpoints
   ```

   This builds `4dcb/sim-base:dev`, `4dcb/agent:dev` and `4dcb/scorer:dev` with the upstream Dockerfiles, then `4dcb/scorer-checkpoints:dev` from `docker/scorer-checkpoints.Dockerfile`. Without the checkpoint directory it builds the upstream three only.

   Host used for validation: x86_64 Linux, one RTX A6000 (48 GB), the R580 driver (CUDA 13.0), Docker with the NVIDIA Container Toolkit, and Harbor 0.27.0. Scoring B_01 peaked at 3.6 GiB of GPU memory, so smaller GPUs are likely to work, though none has been tested. Plan for at least 150 GB of Docker disk for the images, plus the generated tasks.

5. **Host check.** `scripts/vm_preflight.sh <4DCodeBench checkout> <data home> <checkpoint dir>` checks the tools, Docker and GPU access, the upstream commit, the data checksums, the checkpoints and the images, without changing anything. The full synthetic oracle check is under [Comparison with Original Benchmark](#comparison-with-original-benchmark-parity).

## Troubleshooting

- **`reference data missing`** during generation: download the data with `download_data.py --estimates`, or pass `--skip-incomplete`.
- **The verifier fails with `scorer checkpoints missing`:** the verifier was built `FROM` a scorer image without `/checkpoints`. Build `4dcb/scorer-checkpoints:dev`, or pass `--scorer-image`.
- **A verifier failure with no `reward.json`:** the scorer crashed or timed out. See `verifier/4dcodebench_verifier.log` and `4dcodebench_failure.txt` in the trial directory. This is reported as an infrastructure error, not as a score of 0.
- **Every geometry metric is `error`:** look at `world_gate` in `verifier/4dcodebench/results/reward.detail.json`. A missing `solution/build.sh` or a checker violation closes the world gate.
- **`reference data missing: ... world/dynamics` on a synthetic case:** a world with `solver/` and no `dynamics/` is accepted (see Notes & Caveats), so this means the world has neither: the download or unpack is incomplete. Rerun the upstream `scripts/download_data.py`, or skip the case with `--skip-incomplete`.
- **Some metrics are `error` with "worker exited without a result" or `BrokenProcessPool` in `verifier/4dcodebench_verifier.log`:** a scorer worker was probably killed under the verifier's 32 GiB memory limit. Check the host kernel log (`dmesg`) for a memory-cgroup OOM kill. Upstream's scorer hits the same limit on the same cases (G_02 and S_02 in the synthetic oracle run).
- **The downloaded case data has extra files (`solution/`, `sanity*/`, or a tracer file under `world/solver/`):** an original-side run was pointed at it. Re-fetch the case (`scripts/fetch_case.py` checks SHA-256 against the Hub), and run the original side on a copy of the case data.
- **A second original run reports old readings:** the scorer merges into an existing `reward.json`. Give every `run_original_sanity.sh` run a new run name.
- **`harbor lint --select ALL` stops with `Lint failed (ValueError)` on Windows:** this was seen with Harbor 0.27.0 on a Windows host. The default rules pass. Of the optional rules, `root-agent` reports that the agent runs as root, as upstream does, and `unpinned-image` reports that the `FROM` images are local builds with no registry digest.

## Citation

```bibtex
@article{shen20264dcodebench,
  title={{4DCodeBench}: Benchmarking Agents on Inverse Graphics of Dynamic Scenes},
  author={Shen, Ruihong and Kova{\v{c}}i{\v{c}}, {\v{Z}}iga and Kulits, Peter and Wang, Xingrui and Li, Zizhang and Tenenbaum, Joshua B. and Yuille, Alan and Chen, Jieneng and Wu, Jiajun},
  journal={arXiv preprint arXiv:2610.03715},
  year={2026}
}
```

## Authors & Contributions

- Adapter: Zeqian Long (zeqian@stanford.edu).
- Benchmark: the 4DCodeBench authors listed in the citation.
- Questions about the adapter go to the adapters repository; questions about the benchmark go upstream.
