# Video2World → Harbor

## Overview

Adapts all **222 configurations, 189 distinct videos and 39 task families** from [Video2World](https://github.com/AetherLabsAI/Video2World), with no exclusions. Code is pinned to `df0e00b7893b24968e87c5a51a67d824482e431b`; [data](https://huggingface.co/datasets/AetherLabs-AI/Video2World/tree/9cac08429be06ad190b22d6e172af2f815024e3f) to `9cac08429be06ad190b22d6e172af2f815024e3f`. Generation, simulator evaluation and scoring use the upstream implementation.

## What is Video2World?

An agent reconstructs an embodied video as an executable scene and robot-action package. Upstream evaluators initialize the scene, execute submitted actions, apply track-specific integrity checks and compare geometry, dynamics and functionality with withheld annotations.

| Runtime | Configurations | Task families / embodiments |
|---|---:|---|
| ManiSkill 3.0.1 / SAPIEN 3.0.3 | 151 | FurnitureBench assembly, DROID pick/place, Push-T, HOT3D/HOI4D/DexYCB/OakInk arm and bimanual reconstruction; Panda, Panda/Robotiq, xArm7 pusher, Wuji hands |
| MuJoCo 3.11.0 | 9 | Rope routing (5), toy packing (2), DROID cloth folding (2) |
| Isaac Sim 5.1 + Isaac Lab | 62 | Native RoboDojo X5/xArm7 (25); AgiBot G1/OmniPicker in-house camera, point, reviewed, wallet and fryer configurations (37) |

The [upstream protocol](https://github.com/AetherLabsAI/Video2World/blob/df0e00b7893b24968e87c5a51a67d824482e431b/docs/benchmark.md) and pinned manifest own task definitions, controls, applicability and evaluation boundaries.

## Adapter Features

- Calls upstream `v2w.agents.run --prepare` for the brief, video, public rules and robot kits. Only filesystem/interpreter paths are relocated.
- Uses upstream's **custom-agent interface**: Harbor agents receive the prepared brief, write `/workspace/pkg` and can call `v2w check --task /workspace/task /workspace/pkg`. This does not implement the bundled driver's automatic two-round resume loop.
- Builds the main image from upstream's staged public library/inputs. The evaluator alone mounts the complete checkout and data read-only; sample metadata, hidden annotations, GT packages, sources and HAR records are absent from the main image.
- Public profile checks transfer regular package files to the checker over HTTP and return upstream validation errors. The checker exposes no final-grading endpoint. Links, special files, escaping archive paths and packages over 2 GiB are rejected.
- Harbor collects `/workspace/pkg` after the agent finishes and restores it in a **separate verifier environment** defined by `tests/`. The checker has no final-grading credentials. The verifier executes `benchmark.EVALUATORS`, `Experiment.metrics` and upstream scoring/report serialization, retaining the submitted package, raw evaluator artifacts, logs, command, identity and available metrics under `/logs/verifier`.

V2WScore is `100 × macro_family_mean(mean_configuration(build × (F+G+D)/3))`, with `F = 0.5 × success + 0.5 × progress`. G/D use upstream's applicable error metrics, tolerances and formula-version guards; no proxy metric is substituted. A ready per-task report becomes `reward.txt = v2w_score / 100`. Defined build failures remain scored zeros. Missing records, explicitly reported evaluator failures and invalid applicable measurements block scoring and produce no numeric reward. The furniture evaluator's internal-failure limitation is described below. **Use `video2world-score` for the cohort aggregate**; Harbor's ordinary per-task mean does not reproduce family weighting.

## Generated Task Structure

```text
<task-id>/
  task.toml                 aetherlabsai/video2world-<family>-<sample>
  instruction.md            upstream prepared brief
  environment/
    Dockerfile              public runtime and inputs
    docker-compose.yaml     main + evaluator
    evaluator.json          fixed configuration, requirements and source hashes
    client.py  evaluator_service.py
    public/{task,pkg,lib}/
  solution/solve.sh          explains unavailable general candidate oracle
  tests/
    Dockerfile  docker-compose.yaml   separate trusted evaluator runtime
    test.sh  verifier.py  evaluator.json
selection.json              output-directory cohort and provenance
```

Names and task inputs are stable. Host mounts are absolute: regenerate tasks after moving the checkout/data. Generated datasets and run evidence are not adapter source files.

## Run Evaluation / Harness

This adapter is not registered; use local paths. The proposed parity configuration is Codex CLI 0.164.0 with `gpt-6.1-sol` and low reasoning effort on the fixed 22-task cohort generated with `--split parity`. Model-parity runs require team approval and a measured matched pilot first.

After approval, run the first of three independent Harbor repetitions from the adapters repository root:

```bash
harbor run -p "$COHORT" -a codex -m openai/gpt-6.1-sol \
  --agent-kwarg version=0.164.0 --agent-kwarg reasoning_effort=low \
  -n 1 --n-concurrent 1 --max-retries 0 \
  --jobs-dir "$HARBOR_JOBS" --job-name harbor-r1
```

Repeat with job names `harbor-r2` and `harbor-r3`, keeping one attempt per configuration in each job. Match the original-side configuration and score each repetition separately as described in the parity plan.

The reference YAML defaults to `oracle` as required by the adapter guide, but no universal candidate-format reconstruction oracle is shipped; `solution/solve.sh` explicitly errors. To use the YAML entry point after approval, replace its `agents` list with the commented Codex configuration and set its dataset path to the generated parity cohort:

```bash
harbor run -c src/video2world/run_video2world.yaml \
  --jobs-dir "$HARBOR_JOBS" --job-name harbor-r1
```

Re-score the shipped HAR metric records with the pinned upstream code (no agent or simulator execution):

```bash
V2W_DATA="$DATA" PYTHONPATH="$UPSTREAM" uv run python -m v2w har --out "$HAR_REPORT"
```

From `src/video2world`, aggregate exactly one Harbor run:

```bash
uv run --extra harbor video2world-score --upstream-root "$UPSTREAM" --data-root "$DATA" \
  --selection "$COHORT/selection.json" --results "$HARBOR_JOBS/ONE_RUN" --out "$REPORT"
```

The collector reads every Harbor trial result, including exceptions, absent rewards and unfinished trials, using Harbor's own reward-validity policy. `attempts.json` records task identity, status, timestamps, agent/model metadata, exception, reward validity and artifact paths; its counts include attempted, scored, failed and incomplete trials, with unattempted configurations listed separately. Duplicate/unexpected attempts, malformed results and mixed revisions fail after writing the ledger. Missing slots retain the selected denominator and block the report. Use a fresh `--out` directory. Inspect `report/{summary.json,samples.json,samples.csv}`, `metrics.json` and `upstream/experiment/` in verifier logs before interpreting a score. Aggregate reports are written directly under `--out`.

## Usage: Create Task Directories

```bash
cd src/video2world
uv sync --extra harbor
uv run video2world --upstream-root "$UPSTREAM" --data-root "$DATA" \
  --runtime-config "$RUNTIMES" --output-dir ../../datasets/video2world
# Exact upstream family/sample IDs:
uv run video2world --upstream-root "$UPSTREAM" --data-root "$DATA" \
  --runtime-config "$RUNTIMES" --output-dir /tmp/video2world-one \
  --task-ids bulb-insert/fbraw_2023-01-22-22_45_54_lamp_bulb
# Proposed fixed parity cohort, chosen before outcomes:
uv run video2world --upstream-root "$UPSTREAM" --data-root "$DATA" \
  --runtime-config "$RUNTIMES" --output-dir "$COHORT" --split parity
```

Supports positive `--limit` and explicit `--overwrite`. Runtime entries are validated once for the selected upstream configurations before output creation. A complete cohort and its selection document are staged before publication; preparation failures leave the previous cohort intact. `--overwrite` replaces the whole generated cohort, removing tasks outside the new selection. Publication failure restores the previous cohort; if restoration itself fails, the error identifies its retained backup. Unknown IDs, nonempty destinations without overwrite, changed source/manifest and missing configuration/files error. The upstream checkout must be clean at its pin. Generation needs selected videos, preparation metadata and public robot kits; evaluation needs the complete data snapshot. The adapter checks the manifest SHA256 and evaluator source hashes; dataset-file authenticity beyond the manifest is the operator's responsibility.

## Comparison with Original Benchmark (Parity)

**No model parity has run, and none is authorized.** The proposed fixed subset is **22/222 configurations (9.9%)**, covering all 11 profiles and 12 evaluator types: 13 sim / 3 twin / 6 Isaac, across 22 families. IDs are fixed in `adapter.py` before model outcomes; repeated sample names select exactly this cohort through upstream's CLI.

Propose Codex CLI 0.164.0 with `gpt-6.1-sol`, reasoning effort low, subject to team confirmation of availability, required video/file tools and price. Use the cheapest suitable approved configuration, then freeze the same coding-agent version, immutable model snapshot, prepared prompts, custom-agent protocol, tools, budgets, permissions and 10,800-second agent limit on both sides. Pin identical runtime image digests, GPU/driver and Isaac Lab revision. Published benchmark scores and HAR references are reference-only. No agent runtime or campaign cost has been measured; no numeric campaign estimate is claimed.

After explicit approval, a matched pilot must measure agent wall-time, evaluator time, provisioning/image setup, model tokens and actual GPU/API/storage/network charges. The measurements below cover one MuJoCo cloth reference, one SAPIEN Push-T reference and one native Isaac reference. They cannot establish model runtime, untested profiles or API cost. Budget the campaign from that pilot, separately for each simulator/profile, before committing to three matched runs per side. Preserve every failed/incomplete attempt; diagnostic regrading of saved submissions must be reported separately and must not replace scored failures.

Upstream `v2w run --agent-cmd "$MATCHED_AGENT_CMD"` accepts repeated `--sample` options. The 20 distinct sample names in the fixed selection select exactly its 22 configurations at this pin. Since restricted upstream runs do not automatically score that subset, use:

```bash
# Original-side experiment, selected with the same sample IDs and agent settings:
uv run --extra harbor video2world-score --upstream-root "$UPSTREAM" --data-root "$DATA" \
  --selection "$COHORT/selection.json" --experiment "$RUNS/original-r1" --out "$REPORTS/original-r1"
# Harbor-side aggregate:
uv run --extra harbor video2world-score --upstream-root "$UPSTREAM" --data-root "$DATA" \
  --selection "$COHORT/selection.json" --results "$HARBOR_JOBS/harbor-r1" --out "$REPORTS/harbor-r1"
```

Report three raw V2WScore values per side, mean ± sample SEM, configuration statuses and family scores. Apply the guide's run-score-range overlap criterion; do not average only completed attempts. No experiment/result placeholder is included before parity is recorded.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|---|---|---|---|---|---|---|
| Pending | Pending | V2WScore | 0 | Proposed 22/222 | Not measured | Not measured |

## Notes & Caveats

- Generation/audit originally covered all 222 configurations and 11 profiles. The current fixed 22-task cohort passes Harbor configuration parsing, separate-verifier resolution, artifact-path and private-mount checks, and covers all 11 profiles / 12 evaluator types. Public inputs and instructions for its 11 overlapping saved baseline tasks are byte-identical. These checks do not validate simulator installations.
- All 25 direct CPU tests pass, including upstream HAR scoring, valid/invalid cloth contracts, final endpoint removal, artifact collection failures, blocked/non-finite results, failure-artifact retention, complete attempt accounting, missing furniture prerequisites and cohort publication rollback.
- Reported scores and rewards are rounded to two decimal places here; comparisons use the full-precision records.
- An earlier Harbor 0.25.0 task replayed all 222 shipped HAR metric records at V2WScore **73.78**; this executes no simulators. Fresh checks below use separate verifier containers and validation-only trusted reference runners; no GT is handed to the agent. Each checks one configuration, not candidate/model parity.
- **MuJoCo:** the cloth reference reproduced shipped HAR **94.45** exactly, including F/G/D; reward **0.94**. Saved artifacts include `executed.npz` and the upstream `reference_actions` execution mode. The current-entry-point evaluator took **13.71 s**. Its malformed-submission control scored **0.00** without an exception.
- **ManiSkill/SAPIEN:** Push-T completed **116 frames with CPU PhysX and GPU rendering**, using the upstream evaluator's optional `--video-dir` in the trusted validation harness. The default evaluation command is unchanged. V2WScore was **99.12**, versus shipped HAR **99.01** (+0.11 points); reward **0.99**. Evaluator time was **29.92 s**. The retained H.264 video independently decodes to 116 distinct 240×240 frames at 5 fps. Inspection of first/middle/last frames shows pusher and T-block movement. SAPIEN selected `sapien_cuda` on RTX 5060 Ti, and two NVIDIA graphics-context samples match the actual rollout PID. The earlier no-render physics reference scored **99.12**; its malformed control scored **0.00**. Neither reference exactly reproduces historical HAR.
- **Isaac:** native RoboDojo X5 `robodojo_general_pickup_7_x5__r002` completed **246 frames at 25 Hz**, with upstream audit `pass`, verified render/GT alignment and valid task success. V2WScore was **99.63**, versus shipped HAR **99.63** (a nonzero difference below 0.01 points); reward **1.00**. The evaluator took **559.62 s**. The separate-mode TrialResult has no exception and a valid reward. Full fresh native malformed-control verification remains unconfirmed.
- The fresh Isaac compact export retains raw audit/initialization records, evaluator logs, metrics, report, reward and TrialResult. Its video/trajectory size and SHA256 receipts were exported, but their binaries were not recovered before the connection failed; the bulk archive is partial. Earlier failed variants and the prior incomplete run remain separate from this successful reference.
- These checks validate one reference configuration per simulator. Full 222-configuration execution, in-house Isaac profiles and matched model parity remain unverified.
- The intended 45-minute rental was confirmed absent **61.79 minutes** after creation. The desktop watchdog missed its deadline; no claim is made that the cap was met. Subsequent reference work uses provider-scheduled deletion and a local backup. No benchmark model/API calls were made. These single-reference timings do not support a model-campaign cost estimate.
- HAR records and track-specific reference artifacts are evaluator-only. `gt_pkg` is not uniformly a candidate submission; cloth explicitly selects its reference branch only at the original GT path. Do not copy GT into an agent package or treat HAR as a 100%-reward oracle.
- Reference reproduction is track-specific: the pinned FurnitureBench HAR metadata identifies a feedback controller that is not shipped, and some in-house HAR records describe historical traces rather than a fresh executable package. Replaying `gt_pkg` does not universally reproduce HAR.
- The upstream furniture evaluator can return a ready zero after an internal rollout/file failure. The adapter now preflights its unconditional rig/library reads and recorded GT mesh paths, so these known environment errors fail before submission scoring. Other internally swallowed errors remain an upstream grading limitation; no replacement scoring or dummy library is supplied.
- Video2World evaluator, controller and scoring source is unchanged. Integration disables automatic infrastructure retries and blocks nonzero evaluator exits even when output exists, retaining that output separately.
- Harbor 0.25.0 automatically mounts its verifier-log directory in the agent environment, including in separate mode. It stops the agent environment and empties that directory before trusted grading; final evaluator artifacts are created afterward. The adapter does not override this framework behavior.
- Inherited limitations: publicly downloadable GT; leak audits recorded by the bundled driver but not consumed by scoring; rigid entity path checks that do not universally confine references to the package. A separate verifier and read-only mounts do not establish an adversarial parser sandbox. These are disclosed rather than silently repaired benchmark semantics.
- Docker Compose on Linux NVIDIA hosts only; Windows and cloud/Modal backends are unsupported. One concurrent trial is configured. Exact sim/twin wheel pins are checked; Isaac installation/version, GPU/Vulkan and fresh initialization need target-host verification. Runtime base images must contain no benchmark data or full Video2World installation.
- Existing adapter READMEs contained no matches for Video2World or its named source datasets. This is not registry-wide deduplication evidence; no scope reduction was made.

## Installation / Prerequisites

Generation requires Python 3.11+, `uv` and Git. Harbor execution and result ingestion use Python 3.12+ with the `harbor` extra (Harbor 0.25.0). Full generation used about 9.7 GiB of temporary output. Download the pinned source/data:

```bash
git clone https://github.com/AetherLabsAI/Video2World.git "$UPSTREAM"
git -C "$UPSTREAM" checkout df0e00b7893b24968e87c5a51a67d824482e431b
hf download AetherLabs-AI/Video2World --repo-type dataset \
  --revision 9cac08429be06ad190b22d6e172af2f815024e3f --local-dir "$DATA"
# From the adapters repository root:
docker build -f src/video2world/runtimes/Dockerfile.sim -t video2world-sim:df0e00b src/video2world/runtimes
docker build -f src/video2world/runtimes/Dockerfile.twin -t video2world-twin:df0e00b src/video2world/runtimes
```

Evaluation requires Docker Compose v2, NVIDIA Container Toolkit, working Vulkan/RTX and sufficient SSD for data/images/artifacts. For furniture/Push-T, install the released `assets/maniskill` rigs and supply read-only aliases for recorded GT mesh paths; `data/paths.json` maps those historical paths to release files. `sim.mounts` in the runtime JSON supplies these evaluator-only binds. The preflight error names the missing recorded path and its release mapping. The sim runtime pins NumPy 2.4.6 / SciPy 1.17.1 / trimesh 5.0.0 / pytorch-kinematics 0.7.6 / embreex 4.4.0 and downloads ManiSkill's official `xarm6`, `widowx250s` and `bridge_v2_real2sim` assets, including the custom Bridge catalog. ManiSkill verifies the Bridge archive SHA256 before extraction. The separate twin runtime pins NumPy 1.26.4 / SciPy 1.17.1 / trimesh 4.12.2. Runtime locks resolve upstream's otherwise floating dependencies.

For native RoboDojo, build the data-free Isaac runtime from its pinned Isaac Lab fork. `ROBODOJO` is an absolute host checkout path; the build context contains source and dependency constraints only.

```bash
git clone https://github.com/robodojo-benchmark/RoboDojo.git "$ROBODOJO"
git -C "$ROBODOJO" checkout 25691aa78fb34bbbe798aa3d880d57ef2788f696
git -C "$ROBODOJO" submodule update --init third_party/IsaacLab
ISAAC_CONTEXT="$(mktemp -d)"
git -C "$ROBODOJO/third_party/IsaacLab" archive --prefix=IsaacLab/ \
  afca7b09d60d8beb9c1cb28b43066499940b969b | tar -xf - -C "$ISAAC_CONTEXT"
cp src/video2world/runtimes/{Dockerfile.isaac,constraints-isaac.txt} "$ISAAC_CONTEXT/"
docker build -f "$ISAAC_CONTEXT/Dockerfile.isaac" -t video2world-isaac:5.1.0 "$ISAAC_CONTEXT"
mkdir -p "$ROBODOJO/Assets"
```

The recipe pins NVIDIA's Isaac Sim 5.1 image digest and installs RoboDojo's pinned Python dependencies. Kit activates its bundled Warp 1.8.2 during startup even though installed `warp-lang` metadata is 1.11.0; record effective imports as well as `pip freeze` and use the identical image on both parity sides. It installs a hashed, independent pip wheel before dependency changes, avoiding Isaac 5.1's [broken vendored-package links](https://github.com/isaac-sim/IsaacLab/issues/5351), and installs the fork with `./isaaclab.sh --install none`. The NGC-specific packaging adjustment names the `pip_prebundle/cv2` registration as `cv2` in Kit's `omni.pip.compute` extension, retaining the parent `pip_prebundle` registration. Its anonymous registration exposes OpenCV helpers as top-level `utils`, shadowing RoboDojo's namespace; removing the search root instead breaks OpenCV's binary bootstrap. Kit's importer and all evaluator/controller source remain unchanged. The unchanged joint-target recorder handles absent optional cuRobo itself. NVIDIA's base image has existing `pip check` warnings for missing `pyjwt` and its USD-to-URDF converter's `lxml` version; these are outside the selected X5 recorder path. Validation adds no new dependency conflicts.

`runtimes/example.json` supplies sim/twin entries. Add an `isaac` entry for your actual data-free Isaac Sim 5.1 image: `image`, executable base `python`, `isaac_python`, and RoboDojo `25691aa78fb34bbbe798aa3d880d57ef2788f696` via `robodojo_source` plus read-only `mounts`; include the normal clone's `.git` directory. Use that checkout's Isaac Lab fork/submodule at `afca7b09d60d8beb9c1cb28b43066499940b969b`. Bind the release's `assets/robodojo/Assets` at `<robodojo_source>/Assets`, as required by RoboDojo's own asset paths. Optional `graphics_libs` is passed through. Interpreter/source paths are inside the runtime; mount sources are host paths. Entry points honor the configured interpreter wrapper environment: Isaac's `python.sh` requires its canonical `PYTHONPATH` for bundled dependencies, so the adapter does not pass `-I`. Separate verifier containers and read-only mounts enforce the evaluator boundary. [Isaac 5.1 requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html) include RTX support (A100/H100 unsupported), at least 32 GiB RAM, 16 GiB VRAM and 50 GiB SSD for Isaac itself. Freeze image digests and driver versions before comparisons.

## Troubleshooting

- Configuration/source/input errors: correct the explicit path/version and regenerate; there is no fallback interpreter or missing-result zero.
- Self-check failure: inspect evaluator startup logs and package errors. Final verification is one-shot; no retry is automatic.
- Nonzero evaluator exit, timeout or blocked report: inspect preserved logs/artifacts and fix the underlying issue. A diagnostic rerun must not replace a scored method failure.
- Reproduce direct checks with `V2W_TEST_UPSTREAM="$UPSTREAM" V2W_TEST_DATA="$DATA" uv run --extra harbor python -m unittest discover -s tests -v`; upstream tests explicitly skip when those variables are absent.

## Citation

```bibtex
@article{tang2026video2world,
  title={Video2World: Benchmarking Coding Agents for Interactive World Modeling from Embodied Videos},
  author={Tang, Jinzhou and Zhang, Zijun and others},
  journal={arXiv preprint arXiv:2610.04432},
  year={2026}
}
```

## Authors & Contributions

Video2World: Jinzhou Tang, Zijun Zhang and collaborators at Aether AI and UC San Diego. Harbor integration: Vyomakesh; github: https://github.com/vyomakesh0728. Upstream's Apache-2.0 license and source dataset/simulator licenses apply.
