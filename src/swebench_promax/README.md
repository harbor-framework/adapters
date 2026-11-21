# SWE-Bench-ProMax → Harbor Adapter

## Overview

This adapter converts [SWE-Bench-ProMax](https://huggingface.co/datasets/swe-bench-promax/SWE-Bench-ProMax)
(COLM 2026) into Harbor task directories.

- **Source:** HF dataset `swe-bench-promax/SWE-Bench-ProMax` (pinned revision in `adapter.py`,
  `HF_REVISION`): `swe-bench-promax.json` + `eval.json`, together with the 2026-11-20 benchmark fix
  (rebuilt task images, see Notes & Caveats).
- **Size:** all 170 tasks are adapted; none are excluded.
- **Languages:** C 20, C++ 22, Go 23, Java 26, Python 29, Rust 22, TypeScript 28.
- **Metric:** resolved rate (pass@1), same pass rule as the original harness.

## What is SWE-Bench-ProMax?

SWE-Bench-ProMax is a multilingual benchmark for large-scale, cross-file code refactoring. All
instances come from real GitHub issues created after 2025, to limit training-data contamination. Each
instance has a problem statement, a pinned repository image, a reference patch, a hidden test patch and
an official eval script. The original harness (`src/evaluation/test_run.py`) starts the task image with
`--network none`, applies the candidate patch, runs the eval script and counts the task as resolved iff
the script exits 0 and prints `OMNIGRIL_EXIT_CODE=0` (and the hidden test patch applied).

Paper: https://openreview.net/forum?id=12gyjCxLXM

## Adapter Features

- Runs the benchmark's own per-instance images (`key4127/refactor-dockerhub:<instance_id>`) directly
  (`[environment].docker_image`), so nothing is built locally; `environment/Dockerfile` is only used
  with `--force-build`.
- Copies the official eval script verbatim into `tests/eval.sh`; `tests/test.sh` reproduces the
  original pass rule (`analyze_test_output`) and writes the reward. Like the original harness, a failure
  whose log matches a known transient signature (`initialize timeout: Elapsed`) is re-run up to 2 more
  times; here the eval script is re-run in place, since it restores the test files itself.
- The original harness also requires the reference patch to pass on the same image before counting a
  model patch as resolved. The reference patch passes on all 170 tasks, so the adapter grades the
  agent's patch alone.
- **Separate verifier, like the original harness.** The original grades a candidate patch in a fresh
  container. Here `[verifier] environment_mode = "separate"`: after the agent finishes, a
  `[[verifier.collect]]` command exports everything it changed in `/testbed` relative to the task's base
  commit (new files and commits included) to `/logs/artifacts/model.patch`; the verifier starts a fresh
  container from the task image, applies that patch with the original commands (`git apply -v`, fallback
  `patch -p1`; an apply failure scores 0) and then runs the eval script. Nothing else from the agent's
  container reaches grading.
- Verifier runs with `network_mode = "no-network"`, matching the original offline grading.
- Oracle (`solution/solve.sh`) applies the reference patch with the same commands as the original
  harness (`git apply -v`, fallback `patch -p1`).
- `--languages`, `--task-ids`, `--limit`, `--split parity` selection.

## Generated Task Structure

```
swebench_promax/<instance_id>/
├── task.toml              # name, authors, image, resources; separate verifier + patch collection
├── instruction.md         # problem statement + one line saying where the repo is
├── environment/
│   └── Dockerfile         # used only with --force-build; the image already contains these steps
├── solution/solve.sh      # applies the reference patch
└── tests/
    ├── test.sh            # applies the agent's patch, runs eval.sh, applies the original pass rule
    └── eval.sh            # official eval script (verbatim)
```

## Run Evaluation / Harness

Once the dataset is registered, run it from the registry:

```bash
harbor run -d swe-bench-promax/swebench-promax -a mini-swe-agent -m <provider/model>
```

From locally generated tasks (see Usage below), with the reference config (oracle by default) or a path:

```bash
harbor run -c src/swebench_promax/run_swebench_promax.yaml
harbor run -p datasets/swebench_promax -a oracle -n 4
```

A single task:

```bash
harbor trial start -p datasets/swebench_promax/mikf__gallery-dl-7872 -a oracle
```

Every trial keeps the agent's patch (`<trial>/artifacts/logs/artifacts/model.patch`) next to its logs, so a finished job can be
regraded without rerunning the agent: `harbor job regrade <job-dir>`.

Some tasks compile large projects (Angular/Bazel, Kubernetes, Hibernate, Rust workspaces); on a single
machine keep concurrency moderate (we used `-n 4` per job).

## Usage: Create Task Directories

```bash
cd src/swebench_promax
uv sync
uv run swebench_promax --output-dir ../../datasets/swebench_promax            # all 170 tasks
uv run swebench_promax --output-dir /tmp/pmx --languages python rust --limit 5
uv run swebench_promax --output-dir /tmp/pmx --task-ids astral-sh__ruff-21445 --overwrite
uv run swebench_promax --output-dir /tmp/pmx_parity --split parity            # 56-task parity subset
uv run swebench_promax --output-dir /tmp/pmx --data-dir /path/to/local/json   # offline source files
```

## Comparison with Original Benchmark (Parity)

**Status: pending — plan to be agreed with the Harbor team.**

Proposed plan:

- **Subset:** `parity_task_ids.txt`, 56 tasks, 8 per language (all 7 languages), drawn by
  `make_parity_subset.py` with a fixed seed (20261121) from tasks sorted by instance id. The selection
  rule was fixed before any parity run, and the script reproduces the exact list. Both sides use the
  same images and eval scripts.
- **Agent:** `mini-swe-agent` (Harbor has a built-in implementation), pinned version, same
  step and cost limits on both sides, model chosen with the Harbor team.
- **Runs:** sanity check on 5–10 tasks per side, then 1 full run per side, then 3 runs per side.
- Reported as mean ± sample SEM with the run-range overlap criterion.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|---|---|---|---|---|---|---|
| mini-swe-agent@TBD | TBD | Resolved rate (%) | 3 | 56 (32.9%) | TBD | TBD |

Reproduction:

```bash
# Original side: run the agent on the instances in parity_task_ids.txt, collect patches into
# preds.json, then grade with the original harness.
python src/evaluation/test_run.py --pred preds.json \
    --golden data/swe-bench-promax.json --eval data/eval.json --output pass_rate.json

# Harbor side
uv run swebench_promax --split parity --output-dir datasets/swebench_promax_parity
harbor run -p datasets/swebench_promax_parity -a mini-swe-agent -m <model> -n 2
```

## Notes & Caveats

- **Benchmark fix (2026-11-20), done upstream in SWE-Bench-ProMax and used by this adapter:**
  - *Future history removed from the images.* The original images kept the upstream clone's branches
    and tags, so `git log --all` / `git show` in `/testbed` reached commits newer than the task's base
    commit, including the fix itself (169 of 170 images; an agent was observed copying the fix this
    way). All refs that are not ancestors of `HEAD` are deleted and unreachable objects pruned;
    `HEAD`, its history and the working tree are unchanged.
  - *Eval scripts fail when the build fails.* 21 scripts ignored a failed build and then ran a stale
    test binary left in the image; because of this `deskflow__deskflow-c_5fa70d0` and
    `bloomberg__blazingmq-827` passed with an empty patch. Both are now included.
  - *Offline dependencies baked in.* Six Angular tasks used to download Bazel at test time, and four
    PlantUML tasks and one Hibernate task missed Gradle jars needed by `gradlew --offline`; their images
    now contain them.
  - *Clean `git status`.* Each image lists its own untracked files (build outputs) in
    `.git/info/exclude` and marks its own edits to tracked files skip-worktree, so a collected patch
    contains only what the agent changed.
  - With the original harness (`test_run.py`, `--network none`): reference patch passes 170/170, empty
    patch passes 0/170.
- **Instruction:** the problem statement is wrapped with one sentence giving the repository location
  (`/testbed`) and asking not to edit existing tests. The same wording should be used on the original
  side during parity.
- **Agent network:** the agent phase uses Harbor's default network policy because agents need their
  model API. ProMax issues are recent; agents with internet access can still look up upstream fixes,
  so for leaderboard use consider an allowlist that only permits the model endpoint.
- **Oracle validation (2026-11-21):** `harbor run` (Harbor 0.26.0, local Docker) on all **170** tasks, one job
  per agent with `-n 4`, separate verifier with no network: the `oracle` agent gives reward 1.0 on 170/170
  and the `nop` agent gives 0.0 on 170/170, 0 exceptions. The tasks used local builds of the release images
  as `docker_image`s.
- **Grading integrity.** The verifier sees only the patch, in a fresh container, so changes to the agent's
  environment (installed packages, `sitecustomize.py`, `PYTHONPATH`, background processes) cannot affect
  grading. A patch that touches `.git/` is rejected, and the reward file starts at 0 and is only set when
  `test.sh` finishes. As in the original harness, the patched code itself runs during evaluation, so a patch
  can still change how the project's own test setup behaves (e.g. a `conftest.py` outside the restored test
  files); the hidden test files are restored before the hidden test patch is applied.
- **Retries run in place.** The original re-runs a known transient failure in a fresh container; here the
  eval script is re-run in the same verifier container.
- **Image-side files hidden from patches.** Two Bazel images (`bazelbuild__bazel-c_2be8c98`,
  `bazelbuild__bazel-c_c5b4e33`) ship an edited `.bazelversion` marked skip-worktree, so an agent's change
  to that file would not be part of its patch.
- **Hidden test patch location:** the eval script embeds the hidden test patch, and it lives in
  `tests/`, which Harbor only mounts for the verifier.

## Installation / Prerequisites

- Docker (with Compose v2 and buildx), Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), Harbor
  (`uv tool install harbor`).
- About 2–10 GB disk per image; the full set is several hundred GB.
- Network access to pull the task images.

## Troubleshooting

- **`unknown flag: --file` when a task uses `network_mode = "no-network"`:** Harbor builds its egress
  control sidecar with `docker buildx`; install the buildx plugin.
- **`--force-build` on Docker 20.10:** its built-in BuildKit (0.8) can resolve `FROM` to the wrong tag
  when several tags of the same repository are built at the same time (observed here: a task's
  container held another task's repository). Use `-n 1` with `--force-build` on such hosts, or a newer
  Docker. Without `--force-build` nothing is built.
- **Timeouts on Angular/Hibernate:** these compile large projects; raise `--timeout-multiplier` or
  lower concurrency.

## Citation

```bibtex
@misc{shi2026swe,
  title={SWE-Bench ProMax: Benchmarking Agents on Large-Scale Multilingual Code Refactoring},
  author={Yuling Shi and Jinghan Xu and Kelin Fu and Wenhao Zeng and Shilin He and Lei Zhang and Yue Liu and Zelin Zhao and Terry Yue Zhuo and Jialun Cao and Siyu Ye and Tianyu Liu and Kai Cai and Shing-Chi Cheung and Xiaodong Gu},
  year={2026},
  eprint={2608.09802},
  archivePrefix={arXiv},
  primaryClass={cs.CL},
  url={https://arxiv.org/abs/2608.09802}
}
```

## Authors & Contributions

Adapter built by Yuling Shi (yuling.shi@sjtu.edu.cn), first author of SWE-Bench-ProMax. Issues and
questions: open an issue or PR in this repository.
