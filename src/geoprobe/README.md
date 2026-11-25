# GeoProbe → Harbor Adapter

## Overview

This adapter converts all 168 GeoProbe queries from Embodied Agent Arena into Harbor tasks. Each task presents fixed RGB evidence and requests a structured geometric answer. Scoring is deterministic and offline; no robot simulator, GPU, or LLM judge is required by the task environment or verifier.

Status: work in progress, not ready for final acceptance. No model parity has been performed. See Notes & Caveats for the continuous-score acceptance and asset-licensing questions.

Source locks:

- Arena code: `ce298e7952b9138fd05796e33a2b8de63a0e404c`.
- [Task data](https://huggingface.co/datasets/uuu-Quant/Embodied-Agent-Arena/tree/5f729375eb35163a024625dd8ea72ac57a427a24/assets/w1_geoprobe): `5f729375eb35163a024625dd8ea72ac57a427a24`.
- Harbor runtime: `99218a4611e3bd76e49ce3b5f977e8c8134ad3ac`, the adapter contract v1 compatibility reference. The evaluation extra installs this source revision rather than the system Harbor checkout.
- Python image: `python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c`.

## What is GeoProbe?

[GeoProbe](https://embodied-agent-arena.github.io/embodied-agent-arena/geoprobe.html) measures visual estimation of object motion, size, camera intrinsics, relative pose, sparse depth, and controlled reference geometry. The release has 168 queries sharing 130 source images. Questions are retained in their original Chinese, including coordinate conventions and units.

| Native protocol | Tasks | Primary metric |
| --- | ---: | --- |
| vlm_motion_fixed | 12 | absolute_error_cm |
| vlm_motion_camera | 12 | absolute_error_cm |
| vlm_motion_camera_large | 12 | absolute_error_cm |
| vlm_motion_real | 4 | absolute_error_cm |
| vlm_size | 12 | mape_pct |
| vlm_intrinsics | 24 | focal_mape_pct |
| vlm_focal | 12 | focal_ape_pct |
| vlm_pose | 24 | rotation_error_deg |
| vlm_depth | 12 | abs_rel |
| vlm_reference | 44 | mape_pct or exact_match |

The source scorer calls these local diagnostics and leaves `official_score` unset. This adapter preserves that distinction.

## Adapter Features

- Stable task names derived from upstream sample IDs, with strict selection and collision checks.
- Pinned catalog, receipt, and individual image checksum validation before generation.
- Unchanged upstream parsing and scoring, with source hashes and MIT notices under `src/geoprobe/upstream/`.
- Independent verifier containers. Ground truth and oracle answers are absent from the agent build context.
- Original image order, roles, and dimensions; JPEG transport uses the upstream 1280-pixel limit, bilinear resizing, and quality 85.
- Per-protocol native metrics and explicit coverage. There is no cross-unit aggregate or invented pass threshold.

`geoprobe.agent:GeoProbeNativeAgent` runs the pinned upstream W1 persistent Python loop with its OpenAI-compatible completion transport. It preserves the upstream prompts, initial observe/yield requirement, bounded code execution, single submission, 12 code turns, 120,000-token episode budget, no automatic model retries, and native 900-second episode deadline (inside Harbor's 960-second agent limit).

The sole runtime hook defers `score_case` until Harbor verification. It runs only after the last submitted action; it does not change model inputs, actions, or feedback. The public catalog has no `gt` or provenance. The intermediate native report is a submission receipt, not a grading result. Private scoring then uses the unchanged source function in a fresh container.

The initial native agent supports the existing upstream OpenAI-compatible backend. Codex CLI login/install integration and standard-agent experiments have not been validated. An unrestricted Harbor Codex run is a different experimental condition and must not be labeled native parity.

## Generated Task Structure

```text
datasets/geoprobe/
├── metric.py
└── <sanitized-sample-id>/
    ├── task.toml
    ├── instruction.md
    ├── geoprobe-source.json
    ├── environment/
    │   ├── Dockerfile
    │   ├── public-task.json
    │   ├── run_public.py
    │   ├── data/                # public single-row catalog and source RGB only
    │   └── frames/              # native JPEG attachments
    ├── solution/
    │   ├── solve.sh
    │   └── answer.json
    └── tests/
        ├── Dockerfile
        ├── docker-compose.yaml  # verifier has no network
        ├── test.sh
        ├── case.json            # private reference annotation
        └── geoprobe/            # isolated native scorer
```

Only `/workspace/answer.json` is transferred from the agent into the verifier.

## Run Evaluation / Harness

The dataset is not registered yet. After publication, its intended registry name is `embodied-agent-arena/geoprobe`; registry commands must wait for the Harbor team's publication.

Before publication, use local tasks and the explicit custom metric:

```bash
uv sync --extra evaluation
uv run geoprobe --download --output-dir datasets/geoprobe
uv run --extra evaluation harbor run -c run_geoprobe.yaml
```

The config defaults to oracle annotation replay and performs no model calls. The native primary errors should be zero (rotation has floating-point tolerance `2e-6` degrees), and categorical exact matches should be one. This is not a binary success score for all 168 tasks.

Audit a full oracle job:

```bash
uv run python scripts/check_oracle.py \
  --job-dir jobs/JOB_NAME \
  --data-root .cache/geoprobe/5f729375 \
  --output oracle-validation.json
```

If an infrastructure failure required a separate recovery job, add `--recovery-job jobs/RECOVERY_JOB`. The audit retains the failed attempt, rejects duplicate scored attempts, and requires complete coverage across the original and recovery jobs. It does not replace genuine scored failures with later successes.

The pinned Harbor baseline requires the explicit `uv-script` metric in `run_geoprobe.yaml`. Running with only `-p` uses Harbor's default averages; those raw sufficient-statistic averages are not GeoProbe scores.

## Usage: Create Task Directories

From `src/geoprobe/` in the adapters repository:

```bash
uv run geoprobe --download --output-dir datasets/geoprobe
uv run geoprobe --data-root /path/to/frozen/data --output-dir datasets/geoprobe --limit 10
uv run geoprobe --data-root /path/to/frozen/data --output-dir datasets/geoprobe \
  --task-ids vlm_motion_fixed__pair0000
uv run geoprobe --data-root /path/to/frozen/data --output-dir datasets/geoprobe --overwrite
```

`--task-ids` accepts upstream sample IDs or sanitized directory names. Unknown IDs and corrupt assets fail before tasks are written. Existing directories are refused unless `--overwrite` is supplied and they contain this adapter's source marker. No task subset is designated as an approved parity split yet.

## Comparison with Original Benchmark (Parity)

Not run. `parity_experiment.json` is intentionally empty; the repository validator will report its unmet parity requirement. Oracle checks and fake-provider transport checks must not be reported as model parity.

Adapter tracking: [WIP PR #145](https://github.com/harbor-framework/adapters/pull/145). Dataset-registration and Hugging Face parity PRs have not been opened yet.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
| --- | --- | --- | --- | --- | --- | --- |

Before incurring model costs, agree the model's exact identifier, backend/version, temperature, per-response cap, reasoning configuration, episode limits, task selection, and repeat count with the Harbor team. Follow the contract's symmetric order: 5–10-task sanity on both sides, one full run on both sides, then at least two matched runs per side (three preferred). Report raw per-run arrays and mean ± sample SEM for each native metric.

The original-side command, from the pinned Arena checkout with the complete GeoProbe data:

```bash
python scripts/run_w1_native_case.py \
  --benchmark vlm_motion_fixed --sample-id vlm_motion_fixed__pair0000 \
  --data-root /path/to/frozen/data \
  --executor openai-compatible --model EXACT_NATIVE_MODEL_ID \
  --max-agent-iterations 12 --max-total-tokens 120000 \
  --max-agent-attempts 1 --llm-num-retries 0 \
  --output /path/to/original-result.json
```

Harbor side, using the same endpoint, native model ID, and upstream `LLM_*` settings through explicit agent environment forwarding:

```bash
uv run --extra evaluation harbor run -c run_geoprobe.yaml \
  -a geoprobe.agent:GeoProbeNativeAgent -m EXACT_NATIVE_MODEL_ID \
  --ae "LLM_API_KEY=$LLM_API_KEY" --ae "LLM_BASE_URL=$LLM_BASE_URL" \
  --ae "LLM_TEMPERATURE=$LLM_TEMPERATURE" --ae "LLM_MAX_TOKENS=$LLM_MAX_TOKENS"
```

Record the actual configuration and secret-free native traces. Original-side scores must use the same per-field valid denominators and coverage reporting as `metric.py`. These are reproduction entry points, not an approved parity plan or a claim that the API model has been tested.

## Notes & Caveats

- **Continuous-score contract:** 96 cases have no native binary pass gate. Error optimum is zero. This implementation emits native float metrics without a synthetic 0/1 score. Maintainers must confirm this oracle convention and the final reporting policy before acceptance; the guide's generic “100% reward” language does not define GeoProbe's error metrics.
- **Aggregation:** each metric is averaged only over valid results where that field exists, within its native protocol. Every output includes the field count and protocol valid fraction. Missing trials are counted separately. Invalid submissions do not become zero-error predictions, and selective validity must not be mistaken for complete benchmark performance. Centimeters, degrees, percentages, and ratios are never averaged together.
- **Failure classification:** native code-turn/token exhaustion and execution-stage failures produce an invalid/missing answer with zero submission coverage, without inventing a numeric error. Runtime setup and model-transport failures remain infrastructure exceptions. Their original reports are retained for any recovery; genuine scored failures must not be retried for a better answer.
- **Licensing:** code is MIT, with upstream notices retained. The pinned dataset card explicitly says the code license does not automatically license the project-authored GeoProbe assets. The adapter downloads assets on demand for local use; asset redistribution/public dataset upload remains pending explicit upstream terms.
- **Prompt treatments:** the standard file-output instruction wraps the original question. The custom native agent uses the original W1 question formatting, primitive cards, and author loop instead of the generic Harbor file-agent prompt. Any standard-agent comparison needs a symmetric original-side condition.
- **Environment:** no upstream scoring or task bug has been patched. The post-submission deferral is the only native-loop hook. The original `repl-sandbox=auto` policy is retained; Docker may prohibit bubblewrap, in which case upstream uses its existing Python audit boundary. Record this on both sides of parity.
- **Validation scope:** reference answers establish annotation-to-scorer consistency. Docker oracle checks establish task packaging, artifact transfer, and scoring. The offline fake provider checks two-turn image delivery. None establishes model-level parity or a published benchmark result.

### Local validation, 2026-11-23

The sanitized [oracle summary](validation/oracle-summary.json) and [169-attempt ledger](validation/oracle-attempts.json) record the 168 scored tasks and one retained infrastructure failure. The ledger includes hashes of original result/metric/reward files; complete job folders are retained locally pending artifact-upload coordination. These files contain neither source images nor reference answers. They are oracle evidence, not parity results.

A re-audit on 2026-11-24 is available as a [rendered CLI output image](validation/oracle-cli-output.png), with the [actual captured transcript](validation/oracle-cli-output.txt) and [command/hash provenance](validation/oracle-cli-output-provenance.json). This is a text rendering of a successful audit command, not a native terminal-window screenshot or a new Docker/model run. Maintainer acceptance of this alternative visual evidence is pending.

- All 168 distinct tasks completed Harbor/Docker oracle replay at their native primary-metric optimum; no missing cases or scoring failures. One Docker-daemon outage was recovered in a separate, identical oracle task, with the original failed attempt retained.
- Thirteen local tests passed, including all 168 reference answers, malformed submissions, sparse metric denominators, source-file checksums, isolation, deterministic generation, and native failure classification.
- The native agent completed a full Harbor trial against a local fake provider: observe/yield, exactly two image attachments with matching JPEG bytes/order, submit, artifact transfer, and independent grading. This used no paid model.
- The final grader, oracle, verifier configuration, and metric match the executed oracle cohort in 3,193 file comparisons. Native failure-classification changes were tested separately because the oracle agent does not run that loop.
- Wheel/source-distribution builds and `git diff --check` passed. The source-only structural validator has 30 passing checks; its remaining error and warning concern the intentionally absent real parity results.

## Installation / Prerequisites

- Python 3.12+, uv, and a running Docker daemon.
- Roughly 82 MiB for the downloaded GeoProbe closure and 166 MiB for generated tasks (before container images and run logs).
- Network during initial data download and Docker image build. The private verifier is offline.
- Native model experiments additionally need an explicitly configured OpenAI-compatible multimodal endpoint and model; oracle generation needs no credentials.

```bash
uv sync --extra evaluation --extra test
uv run --extra test python -m pytest tests --data-root /path/to/frozen/data -q
```

## Troubleshooting

- **Checksum failure:** restore the pinned receipt/catalog/image; do not change the expected hash to accept a different release.
- **Missing answer:** inspect the native report and episode logs. The verifier records an invalid submission rather than substituting a numeric zero error.
- **Wrong aggregate:** use `run_geoprobe.yaml` with its explicit custom metric; generic mean aggregation is not valid for sparse fields.
- **Docker address pool exhausted:** use a local validation network or free networks you own. Do not prune unrelated Docker state. The verifier already uses `network_mode: none`.
- **CLI parity differs:** compare the exact prompts, image bytes/order, model backend, limits, and Python sandbox backend first. Merely selecting a model named Codex on both sides is insufficient.

## Citation

Huang et al., *Are Frontier VLM Agents Ready to Be Robot Generalists? An Empirical Study with the Embodied Agent Arena*, 2026. [arXiv:2610.00854v3](https://arxiv.org/abs/2610.00854v3). The source citation metadata is in the pinned Arena repository's `CITATION.cff`.

```bibtex
@article{huang2026frontier,
  title={Are Frontier VLM Agents Ready to Be Robot Generalists? An Empirical Study with the Embodied Agent Arena},
  author={Huang, Haojian and Zhao, Pukun and Li, Zexi and Zhang, Yehang and Wei, Yangkai and Li, Wenqian and Yang, Han and Zhou, Kaiwen and Chen, Ying-Cong and Li, Yinchuan},
  journal={arXiv preprint arXiv:2610.00854},
  year={2026}
}
```

## Authors & Contributions

Benchmark authors: Haojian Huang, Pukun Zhao, Zexi Li, Yehang Zhang, Yangkai Wei, Wenqian Li, Han Yang, Kaiwen Zhou, Ying-Cong Chen, and Yinchuan Li.

Adapter contributor: Yizhao Chen (`545114583@qq.com`). Task author metadata credits the original benchmark authors. Source code provenance and checksums accompany the vendored scoring modules.
