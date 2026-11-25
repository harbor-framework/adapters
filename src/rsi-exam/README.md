## RSI-Exam → Harbor Adapter

## Overview

RSI-Exam measures whether an AI agent can do **long-horizon, recursive self-improvement on executable research problems**. Each task gives the agent a working but weak method, plus a visible data split and a self-check. The agent then has up to **12 hours** to experiment and improve it. The method it leaves in `/app/methods/main/` is copied into a fresh, sealed verifier container and re-run once on a **hidden split it never saw**. That single normalized number is the score.

- **Domains (public split):** AI models & agents (8), systems & hardware (9), physical sciences & engineering (4), optimization/planning/control (6), life sciences & medicine (5), finance/law/business (3). Tasks include GPU/TPU kernel speedups, EDA placement, vector search, QEC decoders, single-cell genomics, post-training recipes, offline RL, routing/cutting/scheduling, valuation and legal casework.
- **Size:** the full benchmark has 88 tasks. **35 are public** and are published with their full grading containers on 🤗 [`RSI-Exam/RSI-Exam`](https://huggingface.co/datasets/RSI-Exam/RSI-Exam). The other 53 are held back by the authors.
- **This adapter produces 35 tasks**: one per public task directory at the pinned dataset revision `66f54935eaa576e27dae446f74c2ce17875c14da`. No tasks are excluded.
- **Provenance / license:** [github.com/aiming-lab/RSI-Exam](https://github.com/aiming-lab/RSI-Exam) and [rsi-exam.ai](https://rsi-exam.ai), MIT license. Some tasks wrap third-party data or code under their own terms; see each task's files.
- **Main adaptation:** none to prompts, environments or graders. RSI-Exam is authored natively in Harbor's task format, so the adapter copies each task **verbatim** and changes only two things:
  1. It rewrites `[task].name` to a stable, registry-safe `rsi-exam/<task_id>`.
  2. It changes oracle scripts under `solution/` only: a baseline (no-op) `solve.sh` for the 25 tasks without a runnable reference solution, and a fix for one upstream reference that can't build in the sealed grader (`mbff_banking_placement`).

## What is RSI-Exam?

RSI-Exam ("Benchmarking Recursive Self-Improvement through Executable Research") asks whether frontier agents can turn a weak method into one that **generalizes**, rather than one that overfits the visible proxy. The agent works under an "autoresearch" program: form a hypothesis, implement it, measure it with the task's self-check, log and snapshot every version, and repeat for the whole run window.

Grading uses two images with a sealed boundary between them: the agent's container (`environment/`) and a separate verifier container (`tests/`). The only thing that crosses is the submitted artifact (`/app/methods`). The verifier re-runs the artifact on the hidden split and normalizes the task's raw metric against frozen anchors: shipped **baseline = 0**, frontier-calibrated **reference = 0.6** (where one exists), proven **upper bound = 1**. The reward written to `/logs/verifier/reward.txt` / `reward.json` is that normalized score. The headline metric is the **mean normalized hidden-set score** across tasks. For comparison, the upstream leaderboard over all 88 tasks ranges from 0.309 (Gemini 3.7 Flash) to 0.464 (Claude Opus 5).

## Adapter Features

- **Pinned, partial download:** the adapter lists the HF dataset at a fixed revision and downloads only the selected task directories through `huggingface_hub`. `--task-ids` and `--limit` are applied *before* download, so one-task debugging is cheap. The full public set is about 570 MB.
- **Byte-identical tasks:** `instruction.md`, `environment/` (Dockerfile, weak baseline, visible data, `selfcheck.py`, `.dockerignore`, compose overlays) and `tests/` (sealed grader, anchors, hidden split) are copied unchanged. In `task.toml` only the `name = ...` line under `[task]` is rewritten. `solution/` is also copied unchanged, except for the oracle fixes listed under Oracle coverage. Everything else is untouched, including timeouts, `network_mode = "no-network"` for the agent and verifier phases, `environment_mode = "separate"`, resources, artifacts and upstream `authors`. The rewrite is checked by re-parsing.
- **Stable names:** each task id is the upstream directory name (already lowercase `[a-z0-9_]`), and the name is `rsi-exam/<task_id>`. Upstream `[task].name` values are inconsistent (`autoresearch-arena/...`, `campaign-003/glass_cutting_v1`, and some names that differ from the directory, e.g. `protein_ligand_cofolding` vs `protein_ligand_cofolding_posebusters`), so they are not used.
- **Oracle coverage:** 11 tasks ship an upstream `solution/solve.sh`. 9 are used as-is. Two needed adapter fixes, found by running the oracle on both sides:
  - `mbff_banking_placement`: a prebuild step is appended to the upstream script. Its reference solver compiles itself on demand, which fails in the grader because the submission runs as an unprivileged user in a root-owned directory. The oracle now builds it during the agent phase with the solver's own `_build()`, which is what an agent submitting C++ would do anyway. Both images share the same pinned base image and toolchain.
  - `qec_decoder_arena`: the upstream script is replaced by the baseline placeholder. It defaults to a `baseline` anchor folder that isn't in the release, so it exits 1; its `sota` anchor needs `chromobius`, which isn't installed, and upstream notes it "only runs author-side".

  The remaining 25 tasks get `task-template/solution/solve.sh`, which leaves the shipped baseline in place (see Notes & Caveats). The fixes are in `ORACLE_APPENDS` and `PLACEHOLDER_ORACLE_OVERRIDES` in `adapter.py`.
- **Upstream run protocol vendored:** `src/rsi_exam/protocol/` holds the unmodified upstream `autoresearch.j2` (prompt template), `autoresearch.md`, `budget.py` and `mount.yaml`, from `aiming-lab/RSI-Exam@085036f`. These are applied at run time with `prompt_template_path` and `extra_docker_compose`, the same way upstream runs the benchmark. Harbor's rendering of `autoresearch.j2` around each task's `instruction.md` therefore produces exactly the upstream prompt.
- **Local source:** `--source-dir` converts a local copy of the dataset instead of downloading it. For example, it can convert the full 88-task suite if the authors provide it.
- **No custom agents** are needed. Upstream supports Harbor's `codex`, `claude-code`, `qwen-coder`, `antigravity-cli` and `grok-build` agents.

## Generated Task Structure

```
datasets/rsi-exam/
├── {task_id}/                    # e.g. bbo_simopt_inventory
│   ├── task.toml                 # upstream config; [task].name = "rsi-exam/{task_id}"
│   ├── instruction.md            # upstream task brief (verbatim)
│   ├── environment/              # agent container: weak baseline in methods/main/, visible data, selfcheck.py
│   │   ├── Dockerfile
│   │   └── ...                   # (some tasks: docker-compose.yaml for GPU/TPU, .dockerignore)
│   ├── solution/
│   │   ├── solve.sh              # upstream reference installer, or the adapter's baseline placeholder
│   │   └── ...                   # (upstream reference methods where available)
│   └── tests/                    # sealed verifier container
│       ├── Dockerfile
│       ├── test.sh               # runs grade.py on /app/methods, writes /logs/verifier/reward.{txt,json}
│       └── ...                   # grade.py, anchors, hidden split
```

Adapter code layout:

```
src/rsi-exam/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_rsi-exam.yaml
└── src/rsi_exam/
    ├── __init__.py
    ├── adapter.py                # RSIExamAdapter: list → select → download → copy → rename
    ├── main.py                   # CLI
    ├── protocol/                 # vendored upstream run protocol (applied at run time)
    │   ├── autoresearch.j2
    │   ├── autoresearch.md
    │   ├── budget.py
    │   ├── mount.yaml
    │   └── SOURCE.md
    └── task-template/            # structural reference; only solution/solve.sh is rendered
        ├── task.toml
        ├── instruction.md
        ├── environment/Dockerfile
        ├── solution/solve.sh     # baseline placeholder oracle for tasks without an upstream one
        └── tests/test.sh
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the dataset is published:

```bash
# Oracle (environment build + sealed-grader smoke test)
harbor run -d rsi-exam/rsi-exam

# A real agent: always apply the upstream autoresearch protocol (see "Protocol" below)
harbor run -d rsi-exam/rsi-exam -a claude-code -m claude-opus-5 \
  --ak prompt_template_path=$PWD/src/rsi-exam/src/rsi_exam/protocol/autoresearch.j2 \
  --extra-docker-compose $PWD/src/rsi-exam/src/rsi_exam/protocol/mount.yaml \
  ...
```

### Protocol (required for agent runs)

The tasks themselves contain only the task brief. Upstream gives the agent the autoresearch program at run time, and every agent run must do the same to be comparable:

```bash
# From the adapters repo root
export ARB_PROGRAM=$PWD/src/rsi-exam/src/rsi_exam/protocol/autoresearch.md
export ARB_BUDGET_PY=$PWD/src/rsi-exam/src/rsi_exam/protocol/budget.py
export ARB_AGENT_TIMEOUT_SEC=43200      # 12h, matches [agent] timeout_sec
export ARB_OUTPUT_TOKEN_LIMIT=500000
# Only if you run tasks that call a model from inside the task (see Notes & Caveats):
# set -a; source .env.local; set +a
```

Example agent commands, identical to upstream's:

```bash
# claude-code + claude-opus-5
harbor run -p datasets/rsi-exam -a claude-code -m claude-opus-5 -y -n 1 \
  --ak prompt_template_path=$PWD/src/rsi-exam/src/rsi_exam/protocol/autoresearch.j2 \
  --extra-docker-compose $PWD/src/rsi-exam/src/rsi_exam/protocol/mount.yaml \
  --ak disallowed_tools="WebSearch,WebFetch" \
  --ak reasoning_effort=max \
  --ae ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-5 \
  --ae ANTHROPIC_DEFAULT_SONNET_MODEL=claude-opus-5 \
  --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-opus-5 \
  --ae CLAUDE_CODE_SUBAGENT_MODEL=claude-opus-5 \
  --allow-agent-host "*.anthropic.com" --allow-agent-host anthropic.com \
  --allow-agent-host "*.claude.ai"     --allow-agent-host claude.ai \
  --allow-agent-host "*.claude.com"    --allow-agent-host claude.com

# codex + gpt-5.6-sol
harbor run -p datasets/rsi-exam -a codex -m gpt-5.6-sol -y -n 1 \
  --ak prompt_template_path=$PWD/src/rsi-exam/src/rsi_exam/protocol/autoresearch.j2 \
  --extra-docker-compose $PWD/src/rsi-exam/src/rsi_exam/protocol/mount.yaml \
  --ak web_search=disabled \
  --ak reasoning_effort=max \
  --allow-agent-host "*.openai.com"  --allow-agent-host openai.com \
  --allow-agent-host "*.chatgpt.com" --allow-agent-host chatgpt.com
```

Commands for the other upstream harnesses (GLM-5.3 / DeepSeek via claude-code, qwen-coder, antigravity-cli, grok-build) are in the [upstream README](https://github.com/aiming-lab/RSI-Exam#-harnesses--models). Replace `$PWD/infra/prompts/` with `$PWD/src/rsi-exam/src/rsi_exam/protocol/`. The agent's model endpoint is the only network opening, and it is added at run time with `--allow-agent-host`.

### Using Job Configurations

`src/rsi-exam/run_rsi-exam.yaml` runs the oracle by default. It also contains commented-out `claude-code` and `codex` blocks that carry the protocol settings (`prompt_template_path`, `extra_docker_compose`, `extra_allowed_hosts`).

```bash
# From the adapters repo root
harbor run -c src/rsi-exam/run_rsi-exam.yaml

# Locally prepared dataset, subset of tasks
harbor run -p datasets/rsi-exam -i bbo_simopt_inventory -i "qec*" ...

# Resume a previously started job
harbor job resume -p /path/to/jobs/directory
```

Results go to `jobs/`. `verifier/reward.json` holds the hidden-set score plus the task's raw metric, and `artifacts/app/methods/` holds what the agent submitted, including `versions/` and `experiment_log.md`. Browse with `harbor view jobs`.

### Running Individual Trial

```bash
harbor trial start -p datasets/rsi-exam/bbo_simopt_inventory                 # oracle
harbor trial start -p datasets/rsi-exam/bbo_simopt_inventory -a <agent> -m "<model>" \
  --ak prompt_template_path=... --extra-docker-compose ...                     # agent + protocol
```

## Usage: Create Task Directories

```bash
cd src/rsi-exam
uv sync
uv run rsi-exam                                    # -> <repo>/datasets/rsi-exam (all 35 tasks)
uv run rsi-exam --output-dir /path/to/out --overwrite
uv run rsi-exam --task-ids bbo_simopt_inventory qec_decoder_arena
uv run rsi-exam --limit 3
uv run rsi-exam --split parity                     # the 22-task parity subset (CPU-only, no task-side API keys)
uv run rsi-exam --source-dir /path/to/local/RSI-Exam   # convert a local copy (e.g. the full 88-task suite)
```

Available flags:
- `--output-dir`: where tasks are written (default `datasets/rsi-exam` at the repo root)
- `--limit`: generate only the first N tasks, sorted by task id
- `--overwrite`: replace existing task directories. By default, complete existing tasks are skipped and incomplete ones are regenerated. Each task is built in a hidden staging directory and only moved into place after it validates, so a failed run never leaves a partial task or destroys the previous one
- `--task-ids`: generate only these task ids (upstream directory names)
- `--split`: `full` (default, all tasks) or `parity` (the 22 CPU-only, no-API-key tasks used for oracle verification and the proposed parity runs; `PARITY_TASKS` in `adapter.py`). Combines with `--task-ids` and `--limit`
- `--source-dir`: read tasks from a local directory instead of Hugging Face. It must not overlap `--output-dir`; the adapter refuses to run if it does
- `--repo-id` / `--revision`: HF dataset and revision (defaults: `RSI-Exam/RSI-Exam` @ `66f54935…`)

## Comparison with Original Benchmark (Parity)

**Status: pending.** No parity runs have been done yet. Per the adapter guide, the parity plan (agents, models, number of runs, possibly a CPU-only / no-API-key subset) must be agreed with the Harbor team first. Every trial can run for up to 12 hours.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| TBD | TBD | mean normalized hidden-set score | TBD | 35 (100%) | pending | pending |

How parity works for this benchmark: the original benchmark *is* a Harbor run, using upstream tasks plus the `infra/prompts` overlay. The Harbor-adapter side uses the same tasks, which differ only in `[task].name`, and the same protocol files, vendored unchanged. Any divergence would therefore come from run configuration rather than task content, so lock the following on both sides:
- Harbor commit
- agent version
- dated model id
- `ARB_*` values
- `--ak` / `--ae` flags
- allowed hosts

Reproduction:

```bash
# Original side (upstream repo, commit 085036f)
git clone https://github.com/aiming-lab/RSI-Exam && cd RSI-Exam && git checkout 085036f6efabe2db832332b1de87fffffb913e87
hf download RSI-Exam/RSI-Exam --repo-type dataset --revision 66f54935eaa576e27dae446f74c2ce17875c14da --local-dir tasks/
export ARB_PROGRAM=$PWD/infra/prompts/autoresearch.md ARB_BUDGET_PY=$PWD/infra/prompts/budget.py \
       ARB_AGENT_TIMEOUT_SEC=43200 ARB_OUTPUT_TOKEN_LIMIT=500000
harbor run -p tasks -a <agent> -m <model> -k <runs> \
  --ak prompt_template_path=$PWD/infra/prompts/autoresearch.j2 \
  --extra-docker-compose $PWD/infra/prompts/mount.yaml <harness-specific flags>

# Harbor adapter side (this repo)
cd src/rsi-exam && uv run rsi-exam --split parity && cd ../..
export ARB_PROGRAM=$PWD/src/rsi-exam/src/rsi_exam/protocol/autoresearch.md \
       ARB_BUDGET_PY=$PWD/src/rsi-exam/src/rsi_exam/protocol/budget.py \
       ARB_AGENT_TIMEOUT_SEC=43200 ARB_OUTPUT_TOKEN_LIMIT=500000
harbor run -p datasets/rsi-exam -a <agent> -m <model> -k <runs> \
  --ak prompt_template_path=$PWD/src/rsi-exam/src/rsi_exam/protocol/autoresearch.j2 \
  --extra-docker-compose $PWD/src/rsi-exam/src/rsi_exam/protocol/mount.yaml <harness-specific flags>
```

Per-run score = mean of `verifier/reward.json` → `reward` over tasks, with failed or errored trials counted as 0. Report mean ± sample SEM across runs; see `parity_experiment.json`.

Links: original benchmark [aiming-lab/RSI-Exam](https://github.com/aiming-lab/RSI-Exam) · tasks [🤗 RSI-Exam/RSI-Exam](https://huggingface.co/datasets/RSI-Exam/RSI-Exam) · adapter PR / dataset PR / parity PR: TBD.

## Notes & Caveats

- **Oracle is not 100%, by design.** Rewards are normalized so that baseline = 0, reference = 0.6 and upper bound = 1. The oracle was run on both sides on the 22 CPU-only, no-API-key tasks (m7i.16xlarge, Harbor 0.27.0, dataset revision `66f54935`):
  - **The two sides agree.** 21 of 22 tasks give identical rewards. `tddn_contraction_planning` gives 0.0055 vs 0.0084, both at baseline level, from grader randomness.
  - **Reference oracles** (5 in this subset after the fixes): `bbo_simopt_inventory` 0.60, `mbff_banking_placement` 0.60 (after the fix; 0.0 upstream), `multiview_dense_reconstruction` 0.60, `cxr_ood_triage_policy` 0.40 (anchors are per task, so references can land below 0.6), `bigann_filtered_vector_search` 0.0.
  - **`bigann_filtered_vector_search` scoring 0 is by design.** Its grader says there is "deliberately NO reference anchor": the baseline anchor *is* the shipped starter, and the upstream "reference" is the same textbook IVF method, so it scores about the baseline (172.7 vs 184.5 QPS). The `sota` anchor is a C++ system measured only on the authors' side.
  - **Placeholder tasks** (25 overall, 17 in this subset) score about 0 (at most 0.05): the grader scores the untouched baseline.
  - For placeholder tasks, the oracle only shows that the environment builds and the sealed grader runs end to end. It is not a solvability proof. Building stronger oracles (e.g. from successful agent trajectories) is future work.
- **Upstream oracle bugs found (both sides):** `qec_decoder_arena`'s `solve.sh` exits 1, and `mbff_banking_placement`'s reference scores 0 because it can't build in the grader. Both are fixed adapter-side, in `solution/` only (see Adapter Features); they are worth reporting upstream. The untouched upstream tasks show the same failures, so they come from upstream, not from the adaptation.
- **Some references are offline-only:** `device_iv_regime_extrapolation`, `feeder_phase_impedance_inversion`, `roadef_glass_cutting` and `warehouse_robot_macro_routing` ship reference *methods* under `solution/methods/` but no `solve.sh`. The roadef/warehouse references need GPL/contestant sources fetched at build time, or docker-in-docker, so they can't be installed under `no-network`. They get the baseline placeholder too.
- **The protocol is applied at run time, not baked into tasks.** This matches upstream and keeps the environments byte-identical. Many Dockerfiles have `.dockerignore` allowlists, compose overlays or `USER` switches that injected files could break. The catch: an agent run **without** `prompt_template_path` + `mount.yaml` sees only the task brief and is **not comparable** to upstream or leaderboard numbers. Don't pass the template twice.
- **Accelerators:** 8 tasks need NVIDIA GPUs through compose overlays: `clevr_cogent_grpo_qwen2vl`, `flashattention_varlen_feature_full_vjp_speedup`, `flashfftconv_multistream_gated_forward_speedup`, `lung_fewshot_celltype_annotation`, `paged_ragged_gqa_decode_speedup`, `perturbed_cell_morphology_generation`, `protein_ligand_cofolding_posebusters`, `teacher_student_math_posttraining`. `splash_attention_strata_speedup` needs a TPU v6e host with `HARBOR_TPU_CHIP` set. Kernel-speedup graders check `EXPECTED_GPU_NAME`. Upstream notes for GPU/no-network setups: [docs/gpu_docker_no_network.md](https://github.com/aiming-lab/RSI-Exam/blob/main/docs/gpu_docker_no_network.md).
- **Task-side API keys (4 tasks).** Each key reaches only the task that declares it. The model is pinned by the task, and overriding it invalidates that task's anchors. Unset keys fail loudly. The endpoint host must also be allowed at run time; see [network-policy.md](https://github.com/aiming-lab/RSI-Exam/blob/main/docs/network-policy.md).
  - `locomo_longterm_memory`: `MEMORY_LLM_API_KEY`
  - `legal_matter_caseload_regulatory`: `APEX_LLM_API_KEY`, used by the verifier's rubric judge
  - `lean_formal_proof_workflow_design`: `LEAN_LLM_API_KEY`
  - `discoveryworld_agent_harness_low2`: `DISCOVERYWORLD_LLM_API_KEY`
- **Cost/time:** each trial runs for up to 12h of agent time. Verifier timeouts range from 7 minutes to 13 hours (`[verifier].timeout_sec` 420–46800), and Docker builds are allowed up to 6h (`build_timeout_sec` up to 21600).
- **Upstream `harbor lint` findings, left unchanged** to preserve fidelity:
  - `unknown-config-field`: `[scoring]` and `verifier.cpus/memory_mb/storage_mb/gpus`, which Harbor ignores.
  - `unpinned-python-dependency`: in some Dockerfiles.
  - `paged_ragged_gqa_decode_speedup` uses `schema_version = "1.4"` and `tidal_friction_inverse` uses `"1.0"`. All 35 load with Harbor's `TaskConfig`.
- **Revision pinning:** scores are only comparable at the same dataset revision, because anchors and hidden splits live in `tests/`. Change `--revision` deliberately.
- **Private split:** the 53 held-back tasks aren't on HF. If the authors provide them, `--source-dir` converts them with the same rules.

## Installation / Prerequisites

- Docker installed and running. GPU tasks need the NVIDIA container toolkit; the TPU task needs a TPU v6e VM.
- Harbor CLI: `uv tool install harbor`. Upstream was validated against recent Harbor; record the Harbor commit you use. `antigravity-cli` runs need upstream's [`patch-antigravity-flags.sh`](https://github.com/aiming-lab/RSI-Exam/blob/main/infra/harbor/patch-antigravity-flags.sh).
- Adapter environment (Python ≥ 3.11):
  ```bash
  cd src/rsi-exam
  uv sync
  ```
- Network access to huggingface.co when generating tasks. Optionally set `HF_TOKEN` for higher rate limits.
- Agent credentials (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) and, for the 4 tasks above, task-side keys in `.env.local`. Copy upstream's [`.env.local.example`](https://github.com/aiming-lab/RSI-Exam/blob/main/.env.local.example).

## Troubleshooting

- **`invalid spec: :/app/AUTORESEARCH.md:ro`, or empty mount errors:** `ARB_PROGRAM` / `ARB_BUDGET_PY` are not exported. `mount.yaml` interpolates them from the host environment and needs absolute paths.
- **The agent never mentions the autoresearch loop or `/app/methods/versions`:** `prompt_template_path` wasn't passed, so the run isn't comparable. Re-run with the protocol flags.
- **A task fails immediately with a missing-variable error:** one of the 4 task-side API keys is unset. Keys are checked for *presence*, not value, so `KEY=` gives an empty string rather than the default; comment the line out instead.
- **The agent can't reach its model:** add the provider host with `--allow-agent-host`. The agent phase is `no-network` by default.
- **antigravity-cli runs end after about 5 minutes:** apply upstream's `patch-antigravity-flags.sh` after every Harbor upgrade.
- **`harbor view` shows a blank page:** point it at `jobs/`, not at a single job directory.
- **Reward 0 with `grader failed` in `verifier/grade_debug.json`:** the submission broke the method's I/O contract, or the verifier hit its timeout. Most graders fail closed by design.

## Citation

```bibtex
@misc{rsi-exam-2026,
  title        = {RSI-Exam: Benchmarking Recursive Self-Improvement through Executable Research},
  author       = {{RSI-Exam Team}},
  year         = {2026},
  howpublished = {\url{https://github.com/aiming-lab/RSI-Exam}}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Jack Wang](mailto:faldict@ucsc.edu). The benchmark, tasks, graders and run protocol are by the RSI-Exam Team ([rsi-exam.ai](https://rsi-exam.ai)); per-task authors are credited in each task's `[task].authors`.

**Issues and Contributions:**
- Adapter issues and PRs: [harbor-framework/adapters](https://github.com/harbor-framework/adapters)
- Task content or grading issues: upstream at [aiming-lab/RSI-Exam](https://github.com/aiming-lab/RSI-Exam)
