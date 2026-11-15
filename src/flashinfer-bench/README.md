# FlashInfer-Bench → Harbor Adapter

## Overview

This adapter turns FlashInfer-Bench GPU kernel definitions into Harbor tasks.
An agent submits one implementation for a definition; the verifier checks and
times it across that definition's released workloads against the upstream baseline.
The adapter packages the benchmark's data and execution entry points while
retaining its prompts, numerical checks, timing method and score formula.

- **Adapted scope:** 95 definitions and all 2,699 associated workloads from a
  190-definition public snapshot. [The other 95](#exact-scope-exclusions) lack
  released workloads or the unique baseline required by the scorer.
- **Benchmark revision:** [`15618a67e8d7b7f49ca61b5ba3b9f26a876d0bee`](https://github.com/flashinfer-ai/flashinfer-bench/tree/15618a67e8d7b7f49ca61b5ba3b9f26a876d0bee).
- **Dataset revision:** [`da915083d4c7c5e61aa3005e3d17ae488e0fc71c`](https://huggingface.co/datasets/flashinfer-ai/flashinfer-trace/tree/da915083d4c7c5e61aa3005e3d17ae488e0fc71c).
- **Metric:** uncapped average speedup over the released baseline, averaged
  equally across scorable definitions.
- **Status:** direct GPU oracle validation covers `rmsnorm_h128` and its 14
  workloads. Agent parity is **pending approval**; tasks are not registered.

## What is FlashInfer-Bench?

[FlashInfer-Bench](https://github.com/flashinfer-ai/flashinfer-bench) evaluates
kernel implementations using mathematical references for correctness and
library baselines for performance.
[FlashInfer-Trace](https://huggingface.co/datasets/flashinfer-ai/flashinfer-trace)
provides three records used by this adapter:

| Record | Role in a task |
| --- | --- |
| Definition | Operation contract, input/output specifications and mathematical reference |
| Workload | A concrete instance of the definition, identified by UUID, with dimensions and input-generation or public-tensor specifications |
| Solution | Implementation sources and a `BuildSpec` describing how to build and call them |

A definition is the unit of a Harbor task. Workloads are the instances used to
check whether the submitted implementation works across the released inputs.
The mathematical reference remains visible to the agent, as it does in the
upstream native prompt. The released baseline is supplied to the final verifier
and oracle, rather than included as an agent-visible solution.

### Scoring

Final grading calls upstream
[`TraceSet.get_solution_score(..., baseline_author="baseline")`](https://github.com/flashinfer-ai/flashinfer-bench/blob/15618a67e8d7b7f49ca61b5ba3b9f26a876d0bee/flashinfer_bench/data/trace_set.py#L390-L514).
For a passing candidate, the definition's score is the arithmetic mean of
`baseline_latency / candidate_latency` over workloads where the baseline passed.
A score above 1 means the candidate is faster; the value is neither capped nor
converted to a binary reward.

| Evaluation outcome | Upstream score / adapter result |
| --- | --- |
| Candidate passes all workloads and the baseline has passing workloads | Mean latency ratio over the passing-baseline workloads |
| Any evaluated candidate trace fails and comparable workloads exist | Entire definition scores **0**, including a failure outside the passing-baseline subset |
| Baseline fails on some workloads | Those workloads leave the scoring denominator; the definition can still receive a score |
| No comparable workloads, or no loadable candidate | No score; the adapter publishes no reward |
| Missing traces, incomplete evaluation or invalid performance data | Execution fails without publishing a reward |

The verifier requires complete baseline/candidate evaluations before scoring,
so a worker failure cannot silently reduce the workload set. Upstream then
calculates the score, including baseline-failure handling.

The reference YAML uses [a custom Harbor metric](src/flashinfer_bench/aggregate.py)
to preserve upstream's equal weighting of scorable definitions. For example,
`[4.0, 0.0, missing]` yields `avg_speedup = 2.0`, two scored definitions and one
unscored definition. Harbor's default mean would include the missing reward as
zero. Report the coverage counts with the mean so an incomplete run remains
visible.

## Adapter Features

The execution path has four stages:

1. **Generate tasks.** Read the pinned dataset's Git objects, select eligible
   definitions, and copy their records into tasks. Stable names and `scope.json`
   record the selection; local checkout edits do not affect extraction.
2. **Prepare the environment.** Install pinned upstream source and download public
   tensor inputs, checking sizes and SHA-256 digests against Git LFS pointers.
3. **Produce a submission.** Write a Solution JSON with sources and `BuildSpec`
   to `/workspace/solution.json`. CLI agents receive `instruction.md`; the native
   agent invokes upstream `KernelGenerator` directly.
4. **Evaluate from fresh state.** Harbor 0.25.0 transfers the submission to a
   separate verifier. It loads pristine workloads and baseline with empty traces,
   evaluates both solutions on the same GPU, and writes the upstream score and traces.

### Native generation protocol

[FlashInferNativeAgent](src/flashinfer_bench/native_agent.py) transports execution
into the task environment. Upstream owns prompt construction, generation,
feedback and candidate selection:

- Select one feedback workload using Python's `random.choice`.
- Run the sequential optimization loop for ten rounds by default.
- Return the best passing candidate by upstream feedback speedup, or the last
  generated candidate if none passed, as upstream specifies.
- Allow up to two whole-generation attempts, matching the example driver. Saving
  the resulting JSON happens outside that retry loop, so a disk/serialization
  failure does not trigger another model attempt.
- Default to Triton and high reasoning effort, with FFI and beam search disabled.
  An optional seed controls Python's workload choice; it does not seed the model API.

The native model receives upstream prompts, without `instruction.md` being
inserted. CLI agents have a different interaction protocol. Native feedback uses
`BenchmarkConfig()` and its selected workload; final grading uses
`BenchmarkConfig.default()` and all released workloads, retaining upstream's
bundled YAML and operation-specific settings. Feedback speedup is therefore a
search signal; the final reward comes from comparison with the released baseline.

## Generated Task Structure

```text
<output>/
├── scope.json
└── <sanitized-definition>/
    ├── instruction.md
    ├── task.toml
    ├── environment/
    │   ├── Dockerfile
    │   ├── docker-compose.yaml
    │   ├── manifest.json
    │   ├── data/{definitions,workloads}/
    │   └── runtime/
    ├── solution/{solve.sh,solution.json}
    └── tests/
        ├── test.sh
        ├── baseline.json
        ├── manifest.json
        ├── data/{definitions,workloads}/
        └── runtime/
```

- Task names are `flashinfer-ai/flashinfer-bench--<sanitized-definition>`.
- The manifest records source revisions, target GPU, tensor digests/sizes and
  expected workload UUIDs.
- `environment/` supplies agent-visible inputs; `tests/` supplies final verification
  inputs and the baseline. Only `/workspace/solution.json` is declared for transfer
  into the fresh verifier's workspace.

## Run Evaluation / Harness

From `src/flashinfer-bench`, on Linux with Docker, NVIDIA Container Toolkit and
one B200:

```bash
uv sync --extra harbor
uv run flashinfer-bench --output-dir ../../datasets/flashinfer-bench --task-ids rmsnorm_h128
uv run harbor run -c run_flashinfer-bench.yaml
```

- The reference config defaults to the oracle and one concurrent trial to avoid
  competing GPU timings. Omit `--task-ids` to generate the complete eligible scope.
- The oracle copies baseline code/build settings, changing only name/author.
  Expect speedup near 1× with timing noise; check every trace's correctness rather
  than requiring reward exactly 1.0.
- Native model execution uses the commented agent stanza in
  [run_flashinfer-bench.yaml](run_flashinfer-bench.yaml). Set the exact model ID,
  `LLM_API_KEY` and optional `BASE_URL`. The example model is not an approved parity choice.
- Run from the adapter directory so dataset and custom-metric paths resolve.
  Dataset generation is separate from registry publication; no registry tag exists yet.

The verifier retains the evidence needed to interpret each reward:

| File under `/logs/verifier` | Contents |
| --- | --- |
| `traces.jsonl` | Per-workload baseline/candidate outcomes and measured performance |
| `eval_config.json` | Resolved upstream final-evaluation settings |
| `score.json` | Upstream `SpeedupMetrics`, including workload count and success/win rates |
| `reward.txt` | Unmodified `avg_speedup` consumed by Harbor |

Native generation output goes to `/logs/agent/native.log`. Missing/malformed
submissions fail with the original file/model error; execution failures do not
create a replacement zero reward.

## Usage: Create Task Directories

```bash
cd src/flashinfer-bench
uv sync
uv run flashinfer-bench --output-dir /tmp/flashinfer-tasks
uv run flashinfer-bench --output-dir /tmp/flashinfer-smoke --limit 1
uv run flashinfer-bench --output-dir /tmp/flashinfer-rms --task-ids rmsnorm_h128
uv run flashinfer-bench --output-dir /tmp/flashinfer-rms --task-ids rmsnorm-h128 --overwrite
```

| Option | Behavior |
| --- | --- |
| `--source PATH` | Read an existing Git repository containing the pinned dataset commit; otherwise fetch metadata into `~/.cache/harbor-flashinfer-bench/trace` |
| `--task-ids ...` | Select original definition names or sanitized directory names |
| `--limit N` | Generate the first N definitions after selection |
| `--overwrite` | Replace existing selected task directories |
| `--target-gpu MODEL` | Set the runtime device and native prompt target; defaults to `B200` |

- Git LFS is not required on the host. Records are read from the pinned commit,
  regardless of the working tree.
- Generation processes the selected definitions sequentially and stops on the
  first error. Completed/partial task directories remain; `scope.json` is written
  only after every selected task finishes. Correct the error and rerun with `--overwrite`.
- An output directory with tasks outside the requested selection is rejected so
  its scope report stays accurate. Use a fresh directory when narrowing the selection.
- Changing the GPU target does not make architecture-specific baselines portable.
  The runtime requires exactly one visible CUDA GPU matching that target.

## Comparison with Original Benchmark (Parity)

**Pending team approval; no agent parity runs completed.** The proposed comparison
runs upstream `KernelGenerator` outside Harbor versus `FlashInferNativeAgent`
invoking the same pinned generator/evaluator through Harbor. Both use `gpt-6.1-sol`.
It does not compare with a historical leaderboard score.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| KernelGenerator / FlashInferNativeAgent | gpt-6.1-sol | Average speedup | 3 per side (planned) | 10 definitions (~10.5% of 95) | Not run | Not run |

- **Protocol:** retain Triton, ten rounds, two attempts and high reasoning effort.
  Match exact model ID, API settings, prompts, workloads, timeouts, image/package
  inventory and timing backend. Use an identical built image and one NVIDIA B200
  on each side, with matched GPU clocks and no concurrent GPU timing jobs.
- **Cohort and repeats:** 10 definitions, one from each operation family, retaining
  every released workload for each selected definition. Freeze and publish the
  task IDs and workload count before execution; use the same cohort for three
  matched runs per side with Python seeds `0`, `1`, `2`. Full oracle verification
  across all 95 definitions remains separate from this agent-parity subset.
- **Execution order:** pending team approval of this plan, hardware and budget.
  After approval, sanity-check 5–10 definitions on both sides, complete one full
  10-definition run on each side, then report costs, scores and failure counts
  for team review before the remaining two runs. Generation and grading use
  separate fresh containers; only the submitted Solution JSON enters final evaluation.
- **Analysis:** compute the same unweighted scorable-definition mean on each side.
  Keep evaluated candidate failures as zeros and disclose unscored attempts with
  reasons, with attempted, scored and failed counts. Report raw run arrays,
  mean ± sample SEM and the guide's range-overlap criterion: each side's maximum
  must be at least the other's minimum. Conclusions apply to the selected cohort.
- **Evidence:** retain configurations, source/image identifiers, model IDs,
  selected workloads, traces and attempt records, including failed attempts.
  `parity_experiment.json` and parity costs remain unrecorded until results exist.

<details>
<summary>Entry points for the proposed comparison</summary>

- **Harbor:** enable the native agent stanza in `run_flashinfer-bench.yaml`, set
  the approved model and seed, export `LLM_API_KEY` and optional `BASE_URL`, then
  run `uv run harbor run -c run_flashinfer-bench.yaml`.
- **Original side:** use the same pinned image and original input records outside
  Harbor, invoking the transport script that calls upstream `KernelGenerator`:

```bash
python /opt/adapter-runtime/generate.py --model "$MODEL_ID" --seed 0 \
  --language triton --rounds 10 --attempts 2 --reasoning-effort high
# In a fresh container, with solution.json transferred and tests/ mounted at /tests:
python /tests/runtime/evaluate.py --task /tests \
  --solution /workspace/solution.json --output /logs/verifier
```

- Mount the generated task's `tests/` in the final evaluator, and hydrate its data
  using the same pinned tensor manifest. Generation must not receive verifier files.
- Supply model credentials only to generation and forward the provider's exact
  model ID. A provider prefix should only be present if it belongs to that ID.
- The one-definition oracle does not exercise model generation. A standard CLI
  agent needs its own matched original-side protocol for a parity claim.

</details>

## Validation

The completed checks cover data packaging, score semantics and one definition's
GPU evaluation. They do not establish full-bank execution or agent parity.

| Check | Completed evidence | What it establishes |
| --- | --- | --- |
| CPU suite | **34 passed**, plus two strict expected failures for upstream grading isolation | Selection, overwrite/failure handling, native transport arguments, upstream scoring cases and Harbor config/artifact handoff |
| Generated tasks | All 95 previously checked against Harbor 0.25.0 and upstream schemas; `rmsnorm_h128` regenerated after cleanup | Current single-definition output has 14 byte-identical non-runtime files, including inputs, baseline, oracle, manifests and task config |
| Code quality | Lint, formatting and whitespace checks pass | Source and diff checks |
| Structural validator | **28 passed**, one error for absent `parity_experiment.json`, one warning for unknown parity cost | Required adapter structure is present; parity requirements remain outstanding |
| GPU oracle | All **14 baseline and 14 oracle traces passed** for `rmsnorm_h128` | Direct execution of the generated verifier across this definition's released workloads |
| Score recomputation | Reward **0.9953046987205659** matches the mean of raw baseline/candidate latency ratios | Recorded reward agrees with upstream's formula |

### One-definition GPU run

- **Date/hardware:** 2026-11-15; one NVIDIA B200, driver 580.126.09.
- **Runtime:** PyTorch 2.8.0+cu129, FlashInfer 0.6.4, TVM FFI 0.1.6.
  The setup reproduced a dependency conflict with FFI 0.1.2; the Dockerfile now
  pins 0.1.6, satisfying FlashInfer's requirement, and installation succeeded.
- **Timing:** upstream CUDA-event fallback; CUPTI was not installed.
- **Coverage:** direct verifier invocation in the requested base-image environment.
  A complete adapter-image build, Harbor GPU job, other 94 definitions, live
  model transport and matched agent parity remain unverified.
- **Evidence:** raw traces, configuration, package inventory and diagnostic sources
  remain local at `/tmp/flashinfer-isolation-20261115/gpu/evidence/`; no upload yet.

### Reproduce CPU checks

From this adapter directory:

```bash
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
python3 ../../scripts/validate_adapter.py .
```

The 34-test result includes optional Harbor/upstream checks. To enable them,
point to a clean upstream checkout at the documented pin and generated tasks
containing `rmsnorm_h128`:

```bash
FIB_UPSTREAM=/path/to/pinned/flashinfer-bench FIB_GENERATED=/path/to/tasks \
uv run --extra harbor --with torch==2.8.0 --with safetensors==0.6.2 \
  --with pydantic==2.14.3 --with docstring-parser==0.16 --with numpy==2.2.6 pytest -q -rx
```

- Run structural validation on clean source: the validator recursively scans
  ignored virtualenvs and can otherwise report strings from dependencies.
- The two strict expected failures use upstream's actual Python builder and
  default evaluator in subprocesses with CPU tensors, no-op CUDA synchronization
  and a fixed timing sentinel. They demonstrate in-process mutation; they do not
  measure GPU latency.

## Notes & Caveats

- **Inherited upstream grading-isolation issue:** upstream imports candidate
  Python/Triton code inside evaluator workers, allowing it to replace the checker
  or timer. The adapter retains this execution boundary and makes no adversarial-sandbox claim.
  - Harbor's fresh verifier prevents reuse of agent-modified libraries, caches,
    settings and background processes. It still imports the submission during grading.
  - The [reproduction probes](tests/probes/grading_isolation.py) demonstrate both
    attacks; the [strict expected failures](tests/test_isolation.py) keep the issue visible.
- **Separate Python environments:** adapter and upstream both import as
  `flashinfer_bench`. Keep adapter/Harbor on the host and upstream in the task
  image, with runtime scripts invoking the latter.
- **Runtime reproducibility:** the base CUDA/PyTorch image is pinned by digest
  and core Python dependencies by version. OS packages and transitive build
  dependencies are not fully locked; retain the built image digest and package
  inventory for comparable measurements. Upstream is installed from source so
  its bundled `eval_config.yaml` remains available.
- **GPU and storage:** runtime requires one GPU matching the requested target.
  Public tensors can consume about 6 GB per task before cache/copy duplication;
  full-bank resource limits and costs have not been measured.

<details>
<summary>Why the experimental grading-isolation boundary was rejected</summary>

- Upstream [imports submitted source into its evaluator process](https://github.com/flashinfer-ai/flashinfer-bench/blob/15618a67e8d7b7f49ca61b5ba3b9f26a876d0bee/flashinfer_bench/compile/builders/python_builder.py#L112-L145).
  CPU probes show checker replacement accepting an incorrect all-zero RMSNorm
  output and timer replacement accepting a candidate-selected 0.001 ms in place
  of a 123 ms sentinel. These values describe the probe, not measured GPU performance.
- A B200 prototype ran candidate code under another UID/process, passed tensor
  data across the boundary, and kept checking/timing in the parent. On one
  `rmsnorm_h128` workload it rejected the checker attack and ignored forged timing.
- The boundary also changed what the upstream timer measured by including
  IPC/context overhead. The same honest mathematical-reference candidate scored:

  | Execution | Two diagnostic speedup runs |
  | --- | --- |
  | Direct upstream execution | 0.178981, 0.178991 |
  | Separate-process proxy | 0.879493, 0.888306 |

- Both implementations passed correctness, but their score ranges did not
  overlap. The prototype was rejected and is not packaged. The adapter therefore
  documents the upstream issue while preserving its execution and scoring.
  Read-only files or changing the UID of the whole evaluator do not isolate
  mutable checker/timer objects from candidate code.

</details>

### Exact scope exclusions

| Exclusion reason | Definitions |
| --- | ---: |
| No released workloads | 79 |
| Workloads present, no baseline | 9 |
| Workloads present, two baselines | 5 |
| Workloads present, three baselines | 2 |
| **Total excluded** | **95** |

- The scorer requires exactly one baseline per definition. Selecting among
  multiple baselines would change the comparison, so those definitions are excluded.
- These are dataset/scorer eligibility rules, independent of measured correctness
  or speed. All 2,699 workloads of the 95 eligible definitions are retained.
- The full list below matches generated `scope.json`.

<details><summary>expected exactly one baseline; found 0 (9)</summary>

- `gqa_paged_decode_h16_kv2_d128_ps1`
- `gqa_paged_decode_h16_kv2_d128_ps64`
- `gqa_paged_prefill_causal_h16_kv2_d128_ps1`
- `gqa_ragged_prefill_causal_h16_kv2_d128`
- `top_k_sampling_from_probs_v202048`
- `top_k_top_p_sampling_from_probs_v202048`
- `top_k_top_p_sampling_from_probs_v248320`
- `top_p_sampling_from_probs_v129280`
- `top_p_sampling_from_probs_v202048`

</details>

<details><summary>expected exactly one baseline; found 2 (5)</summary>

- `gdn_prefill_qk4_v8_d128_k_last`
- `gdn_prefill_qk8_v16_d128_k_last`
- `gemm_mxfp4_n2048_k2048`
- `gemm_mxfp4_n4096_k4096`
- `gemm_mxfp4_n5120_k2048`

</details>

<details><summary>expected exactly one baseline; found 3 (2)</summary>

- `gemm_nvfp4_n2048_k2048`
- `gemm_nvfp4_n4096_k4096`

</details>

<details><summary>no released workloads (79)</summary>

- `dsa_sparse_attention_h16_ckv512_kpe64_topk2048_ps1`
- `fused_add_rmsnorm_h3072`
- `fused_add_rmsnorm_h5376`
- `gdn_decode_qk16_v32_d128_k_last`
- `gdn_mtp_qk16_v32_d128_k_last`
- `gdn_prefill_qk16_v32_d128_k_last`
- `gemm_n10240_k8192`
- `gemm_n16384_k3072`
- `gemm_n2048_k5376`
- `gemm_n21504_k5376`
- `gemm_n256_k3072`
- `gemm_n3072_k3072`
- `gemm_n3072_k6144`
- `gemm_n3072_k8192`
- `gemm_n3584_k18944`
- `gemm_n3584_k3584`
- `gemm_n37888_k3584`
- `gemm_n4096_k5376`
- `gemm_n4608_k3584`
- `gemm_n5120_k3072`
- `gemm_n5376_k21504`
- `gemm_n5376_k4096`
- `gemm_n57344_k8192`
- `gemm_n8192_k28672`
- `gemm_n8192_k3072`
- `gemm_n8192_k8192`
- `gqa_paged_decode_h24_kv8_d128_ps64`
- `gqa_paged_decode_h32_kv16_d128_ps1`
- `gqa_paged_decode_h32_kv16_d128_ps64`
- `gqa_paged_decode_h6_kv1_d128_ps1`
- `gqa_paged_decode_h6_kv1_d128_ps64`
- `gqa_paged_prefill_causal_h32_kv16_d128_ps1`
- `gqa_paged_prefill_causal_h32_kv16_d128_ps64`
- `gqa_paged_prefill_causal_h32_kv8_d128_ps64`
- `gqa_paged_prefill_causal_h5_kv1_d128_ps64`
- `gqa_paged_prefill_causal_h6_kv1_d128_ps1`
- `gqa_paged_prefill_causal_h6_kv1_d128_ps64`
- `gqa_ragged_prefill_causal_h5_kv1_d128`
- `gqa_ragged_prefill_causal_h6_kv1_d128`
- `mamba_ssu_decode_h128_d64_s128_ng8`
- `mamba_ssu_decode_h64_d64_s128_ng4`
- `mla_paged_decode_h16_ckv512_kpe64_ps64`
- `mla_paged_decode_h8_ckv512_kpe64_ps1`
- `mla_paged_prefill_causal_h16_ckv512_kpe64_ps64`
- `mla_paged_prefill_causal_h8_ckv512_kpe64_ps1`
- `mla_ragged_prefill_causal_h8_qk192_vo128`
- `moe_fp8_block_scale_ds_routing_topk8_ng1_kg1_e384_h7168_i2048`
- `moe_fp8_block_scale_ds_routing_topk8_ng1_kg1_e48_h7168_i2048`
- `moe_fp8_block_scale_renorm_topk10_e128_h2048_i512`
- `moe_fp8_block_scale_renorm_topk8_e128_h2048_i768`
- `moe_fp8_block_scale_renorm_topk8_e128_h4096_i1536`
- `rmsnorm_h3072`
- `rmsnorm_h5376`
- `rope_with_cos_sin_cache_neox_style_d128_rd64`
- `top_k_sampling_from_probs_v152064`
- `top_k_sampling_from_probs_v163840`
- `top_k_sampling_from_probs_v200064`
- `top_k_sampling_from_probs_v262208`
- `top_k_top_p_sampling_from_probs_v152064`
- `top_k_top_p_sampling_from_probs_v163840`
- `top_k_top_p_sampling_from_probs_v200064`
- `top_k_top_p_sampling_from_probs_v262208`
- `top_p_sampling_from_probs_v152064`
- `top_p_sampling_from_probs_v163840`
- `top_p_sampling_from_probs_v200064`
- `top_p_sampling_from_probs_v262208`
- `trtllm_fp4_block_scale_moe_topk10_e128_h2048_i512`
- `trtllm_fp4_block_scale_moe_topk1_e128_h5120_i8192`
- `trtllm_fp4_block_scale_moe_topk1_e16_h5120_i8192`
- `trtllm_fp4_block_scale_moe_topk8_e128_h2048_i768`
- `trtllm_fp4_block_scale_moe_topk8_e64_h4096_i1536`
- `trtllm_fp4_block_scale_routed_moe_topk10_e128_h2048_i512`
- `trtllm_fp4_block_scale_routed_moe_topk1_e128_h5120_i8192`
- `trtllm_fp4_block_scale_routed_moe_topk1_e16_h5120_i8192`
- `trtllm_fp4_block_scale_routed_moe_topk8_e128_h2048_i768`
- `trtllm_fp4_block_scale_routed_moe_topk8_e64_h4096_i1536`
- `trtllm_fp8_per_tensor_scale_moe_topk1_e128_h5120_i8192`
- `trtllm_fp8_per_tensor_scale_moe_topk1_e16_h5120_i8192`
- `trtllm_fp8_per_tensor_scale_moe_topk8_e128_h2048_i768`

</details>

## Installation / Prerequisites

- **Host:** Python 3.12+, `uv` and Git. Each adapter is an independent uv project;
  `uv sync --extra harbor` installs the tested Harbor 0.25.0 dependency.
- **Execution:** Linux amd64 Docker with NVIDIA Container Toolkit and one
  matching CUDA GPU; the reference configuration targets B200.
- **Network:** public Git/source and tensor downloads; model API access for native
  generation. Oracle execution and final verification require no LLM key.

## Troubleshooting

- **Existing output:** pass `--overwrite` to replace selected tasks, or choose a
  fresh directory for a smaller selection.
- **Generation error:** fix the reported input/Git/filesystem error and rerun
  with `--overwrite` to replace partial output. A completed run writes `scope.json`.
- **Unknown task:** check original or sanitized names against `scope.json` and
  the exclusion list above.
- **Missing reward:** inspect the verifier traceback and `traces.jsonl`. Confirm
  whether the run was incomplete or had no comparable baseline workloads before
  interpreting the aggregate; use the reference YAML's scored/unscored counts.
- **Tensor checksum error:** remove the named corrupt cache file and rerun.
  The adapter stops at the error and does not silently download a replacement.
- **Native generation error:** inspect `/logs/agent/native.log`, exact model ID,
  `LLM_API_KEY`, optional `BASE_URL` and the requested GPU target.

## Citation

Please credit the [FlashInfer-Bench authors and project](https://github.com/flashinfer-ai/flashinfer-bench)
and the [FlashInfer-Trace dataset](https://huggingface.co/datasets/flashinfer-ai/flashinfer-trace).
The implementation uses their Apache-2.0 source; generated assets retain upstream
content and benchmark authorship. No new benchmark/scoring method is introduced.

```bibtex
@misc{flashinferbench,
  author = {{FlashInfer team}},
  title = {FlashInfer-Bench},
  howpublished = {\url{https://github.com/flashinfer-ai/flashinfer-bench}}
}
```

## Authors & Contributions

- Original benchmark, native generator, evaluator and dataset: FlashInfer team.
- Harbor adapter: vyomakesh0728.
- Implementation assisted by Codex. Validation scope and evidence are documented above.
