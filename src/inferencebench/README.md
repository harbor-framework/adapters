# InferenceBench → Harbor Adapter

## Overview

InferenceBench measures how well a coding agent can deploy and optimize an OpenAI-compatible LLM inference server.

- **Task type:** open-ended systems optimization with a wall-clock budget
- **Size:** 12 tasks (4 scenarios × 3 seed pairs), all of them adapted
- **Model served:** `mistralai/Mistral-7B-Instruct-v0.3`
- **Resources per task:** 1 NVIDIA H100 80 GB GPU, 16 CPUs, 180 GB of memory, a 2-hour agent budget
- **Score:** speedup over a naive PyTorch server. It is unbounded, and a failed run counts as 1×. A run is graded only if the integrity judge returned valid verdicts.
- **License:** Apache-2.0 (benchmark code). The adapter derives its verifier scripts from the benchmark's own Harbor adapter, `src/harbor_adapter`.

Task IDs have the form `inferencebench-<scenario>-mistral-7b-<development seed>-<evaluation seed>`, for example `inferencebench-a-mistral-7b-21-1337`.

## What is InferenceBench?

[InferenceBench](https://github.com/aisa-group/InferenceBench) ([paper](https://arxiv.org/abs/2607.20468), [site](https://inferencebench.ai/)) gives an agent a model, one GPU, an optimization scenario, and a time budget. The agent writes a launcher, `start_server.sh`. The harness then restarts that launcher in a clean process tree and measures it on requests chosen by a held-out seed.

| Scenario | Requests | Primary metric |
|---|---|---|
| A (input heavy) | 8192 tokens in, 1024 out | 1 / TTFT p50 |
| B (output heavy) | 1024 tokens in, 8192 out | 1 / TPOT p50 |
| C (high load) | 1024 in, 1024 out; burst, Poisson, and constant load | geometric mean of request throughput |
| D (general) | 4096 in, 2048 out | geometric mean of 1 / TTFT p50, 1 / TPOT p50, and request throughput |

Two gates decide whether a run counts. The quality gate requires at least 95% of the PyTorch baseline's accuracy on 500 MMLU-Pro questions. The integrity gate is a Claude judge that reviews the submission for disallowed shortcuts.

## Adapter Features

- Generates all 12 tasks from a pinned upstream commit, using upstream's prompt, evaluator, quality gate, judge, and package locks.
- Runs on Harbor's Daytona, Modal, and Docker environments with no extra volumes. `harbor run -d` works without setup steps.
- Runs the final evaluation in a separate verifier sandbox. The agent's work reaches it through the trial directory, so `harbor jobs regrade` can grade a trial again without rerunning the agent. See [Separate verifier](#notes--caveats).
- Reports the paper's numbers. See [the reward table](#reward).
- Grades a trial only after the integrity judge returned two valid verdicts. Without them the trial gets no reward. A run without the judge is possible only as an explicit, unscored diagnostic run. See [Judge](#notes--caveats).
- Uses vLLM with default settings as the oracle, and compares it with the paper's "vLLM default" row. The oracle is judged like any other run.
- Pins the model repository to a commit, and records each trial's hardware, software, revisions, and data checksums in `environment.json`.
- Recomputes the quality gate's PyTorch reference with upstream's own procedure (`INFERENCE_BENCH_ORACLE=pytorch-reference`).
- Adds `inferencebench.agents:ClaudeCodeUntilDeadline` for parity runs. It repeats upstream's agent wrapper: it stops the CLI at the task's deadline, reruns it with upstream's "continue" prompt until then, and restarts it after a failure as `run_task.sh` does (at most three runs; a restart resumes the session and, if that fails, starts a new one with the task prompt). The parity configuration sets Harbor's own agent timeout two minutes later, so that it only backs the deadline up.
- Adds `inferencebench-score`, which computes the paper's per-scenario means and aggregate from Harbor job directories, and lists the trials that are ungraded, ended in an error, or recomputed the quality reference.

### Reward

The verifier writes `/logs/verifier/reward.json` only for a graded trial, that is, one whose judge returned two valid verdicts. It has these keys:

| Key | Value |
|---|---|
| `reward` | `speedup` when `valid` is 1, otherwise 1.0. This is one cell of the paper's Table 2. |
| `valid` | 1 when the run passes both gates and the judge did not flag it |
| `speedup` | `primary_metric` divided by the PyTorch baseline; 0 if there is no valid measurement |
| `primary_metric` | the raw metric from the table above |
| `eval_valid`, `speed_pass`, `quality_pass` | 1 or 0 for the evaluation and its checks |
| `judge_valid` | always 1 in a reward file |
| `contamination_detected`, `disallowed_use_detected` | 1 or 0 from the judge |

The PyTorch baseline comes from the paper's Table 12: 840 ms TTFT (A), 41 ms TPOT (B), 0.132 req/s (C), and a score of 1.68 (D).

A graded run that fails a gate, ships no working server, or is flagged by the judge keeps the paper's outcome for a failed run: `reward` is 1.0 and `valid` is 0.

A trial without two valid verdicts is **ungraded** and has no reward file; Harbor records it as an error without a reward. The verifier writes `ungraded.json` instead, with the reason and, if the server was measured, the measurement. There are three cases. If the judge failed to start or returned no valid verdicts in three attempts, the verifier still measures the server, as `run_task.sh` does after its judge. If the run had no judge credential, the verifier skips the evaluation, because the trial can never be graded; the original benchmark does not start such a run. A diagnostic run with `INFERENCE_BENCH_JUDGE=off` skips the judge and measures the server. To get a reward, run the trial again with a working judge.

Harbor's default `Mean` averages raw speedups across very different scales, counts a trial without a reward as 0, and cannot tell a failed run (1.0) from a run that matches the baseline. Use `inferencebench-score` for results that compare with the paper.

Upstream's own Harbor adapter reports the raw metric as `reward`, scores a failed run 0, and keeps the judge's verdicts out of `reward`. This adapter reports the quantity in the paper's Table 2 instead.

## Generated Task Structure

```
inferencebench-a-mistral-7b-21-1337/
├── task.toml             # resources, timeouts, per-task environment, separate verifier, collect hook
├── instruction.md        # prompt from upstream's get_prompt.py
├── environment/
│   ├── Dockerfile        # upstream's image, plus the evaluator bundle and benchmark samples
│   ├── collect.sh        # stops the agent and packs its work for the verifier
│   ├── handoff.py        # packs, checks, and unpacks the hand-off between the two sandboxes
│   ├── agent_processes.sh  # stops user agent's processes and checks the result
│   ├── download_model.py   # caches the pinned model revision (healthcheck and verifier)
│   ├── inference_eval/   # evaluator available to the agent
│   └── home/task/        # the agent's working directory
├── solution/
│   ├── solve.sh          # oracle: installs vLLM 0.11.0 and upstream's runtime shims
│   ├── start_server.sh   # upstream's default vLLM launcher
│   ├── vllm-constraints.txt
│   ├── vllm_runtime_shims.py
│   ├── pytorch_reference.sh  # recomputes the PyTorch quality reference; not an oracle run
│   ├── torch-constraints.txt
│   └── ib/               # upstream's PyTorch server and baseline procedure
└── tests/
    ├── test.sh           # hand-off, judge, final evaluation, reward
    ├── write_reward.py   # reward.json for a graded trial, ungraded.json otherwise
    ├── record_environment.py  # writes environment.json
    ├── manifest.json     # what the task pins: commits, seeds, timeouts, checksums
    └── ib/               # evaluator, scenario files, and judge for the final evaluation
```

Adapter code:

```
src/inferencebench/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_inferencebench.yaml       # oracle on a Docker host with GPUs
├── inferencebench_daytona.yaml   # oracle on Daytona
├── inferencebench_modal.yaml     # oracle on Modal
├── inferencebench_parity.yaml    # Harbor side of a parity run
├── tests/test_adapter.py
└── src/inferencebench/
    ├── adapter.py
    ├── agents.py                 # continuation-loop agent
    ├── main.py
    ├── score.py
    ├── data/quality/             # PyTorch accuracy reference
    └── task-template/
```

## Run Evaluation / Harness

### Running with the registry

The dataset is not published yet. After publication:

```bash
harbor run -d aisa-group/inferencebench -e daytona -a claude-code -m anthropic/claude-sonnet-4-6
```

### Using a job configuration

Every job configuration runs one trial at a time by default. On Daytona and Modal each trial gets its own sandbox and GPU, so `-n` can raise the concurrency. The host needs `HF_TOKEN` and a judge credential; see [Installation / Prerequisites](#installation--prerequisites).

```bash
cd src/inferencebench
uv run inferencebench --output-dir ../../datasets/inferencebench
cd ../..

# Oracle on Daytona, one task
uv run --project src/inferencebench --with 'harbor[daytona]==0.26.0' harbor run -c src/inferencebench/inferencebench_daytona.yaml \
    -p datasets/inferencebench -i inferencebench-a-mistral-7b-21-1337

# The same on Modal, or on a Docker host with GPUs
uv run --project src/inferencebench --with 'harbor[modal]==0.26.0' harbor run -c src/inferencebench/inferencebench_modal.yaml \
    -p datasets/inferencebench -i inferencebench-a-mistral-7b-21-1337
uv run --project src/inferencebench --with harbor==0.26.0 harbor run -c src/inferencebench/run_inferencebench.yaml \
    -p datasets/inferencebench -i inferencebench-a-mistral-7b-21-1337
```

Without `-p` and `-i`, a configuration runs all 12 tasks.

### Oracle pilot

Run the oracle in three stages, each only after the one before it has passed:

```bash
ib_run() {
    uv run --project src/inferencebench --with 'harbor[daytona]==0.26.0' harbor run \
        -c src/inferencebench/inferencebench_daytona.yaml -p datasets/inferencebench "$@"
}
ib_run -i inferencebench-a-mistral-7b-21-1337            # scenario A, seed pair 21:1337
ib_run -i 'inferencebench-[bcd]-mistral-7b-21-1337'      # the other scenarios of that seed pair
ib_run -x 'inferencebench-*-21-1337'                     # the other two seed pairs

# The three jobs together are one run of the benchmark.
uv run --project src/inferencebench inferencebench-score --pool jobs/<job 1> jobs/<job 2> jobs/<job 3>
```

An oracle trial passes if `valid` and `judge_valid` are 1: the evaluation finished with complete and finite measurements, all 500 quality requests succeeded, the speed and quality checks passed, and the judge returned two valid verdicts and did not flag the run. The paper's values in [the parity section](#comparison-with-original-benchmark-parity) are a sanity check, not a threshold.

### Running without the judge

A diagnostic run skips the judge and measures the server; every trial stays ungraded:

```bash
ib_run -i inferencebench-a-mistral-7b-21-1337 --ve INFERENCE_BENCH_JUDGE=off
```

### Recomputing the PyTorch quality reference

The quality gate compares a server's accuracy with the PyTorch baseline's accuracy on the same 500 MMLU-Pro questions. The original benchmark does not ship this number; each installation computes it with `run_precompute_all_baselines.sh`. The following run does the same inside a task's image. It installs the packages of upstream's torch baseline container under its lock into a virtual environment, so that torch loads the CUDA libraries it was installed with, as in upstream's container. It then starts upstream's reference server on the pinned model revision and runs upstream's `precompute_quality_baseline` at concurrency 1 on the question set that the image caches. It stops if torch loads CUDA libraries from anywhere else.

```bash
ib_run -i inferencebench-a-mistral-7b-21-1337 --ae INFERENCE_BENCH_ORACLE=pytorch-reference \
    --ve INFERENCE_BENCH_JUDGE=off --agent-timeout-multiplier 3
```

The 500 questions run one at a time with up to 2048 new tokens each; the multiplier gives the run 6 hours instead of the task's 2. The trial is not a benchmark result: it leaves no server, and `inferencebench-score` lists it as `reference`. Its product is in the trial directory under `artifacts/logs/artifacts/pytorch_reference/`: the registry file `quality/mistralai_Mistral-7B-Instruct-v0.3_torch.json`, every question's output, `provenance.json` (GPU, torch, CUDA and cuDNN versions, the CUDA libraries that torch loaded, the model revision, and the questions' checksum), the server log, and the installed packages. To adopt the result, copy the registry file to `src/inferencebench/data/quality/` and generate the tasks again.

### Running individual trials

```bash
harbor trial start -p datasets/inferencebench/inferencebench-a-mistral-7b-21-1337 -e daytona -a oracle
```

### Reading the results

```bash
uv run --project src/inferencebench inferencebench-score jobs/<job-name>
```

A job directory is one run of the benchmark; with `--pool`, the given job directories together are one run. The command prints a summary for each agent, with one row per trial:

| Status | Meaning | In the means |
|---|---|---|
| `valid` | graded, and the run passed both gates and the judge | its speedup |
| `failed` | graded, but a gate failed, no server worked, or the judge flagged the run | 1× |
| `ungraded` | no valid judge verdicts; the row gives the reason and, if the server was measured, its speedup | no |
| `error` | the verifier wrote neither a reward nor `ungraded.json` | no |
| `reference` | a run that recomputed the PyTorch quality reference | no |

The command reports the aggregate only for a complete run. If a cell of the 4 × 3 grid has no graded trial or more than one, it names the cell and exits with status 1. It also lists, with `GPU:`, the trials whose two sandboxes had different GPUs or a GPU other than an H100; they stay in the means.

Each trial directory keeps the evidence: `verifier/environment.json`, `verifier/metrics.json` and one `metrics.attempt-<n>.json` per evaluation attempt, `verifier/eval.log`, `verifier/server.log`, `verifier/judge.log`, the verdict files of every judge attempt, `verifier/handoff.json` and `verifier/handoff.log` for the hand-off, `verifier/model_download.log`, and a snapshot of the task directory. The hand-off itself, which is what the agent submitted, is under `artifacts/var/lib/ib_handoff/`: the stream's parts (`part.000`, ...), `manifest.json`, and `collect.log`. `harbor jobs regrade` grades a job again from these files.

## Usage: Create Task Directories

```bash
cd src/inferencebench
uv run inferencebench --output-dir ../../datasets/inferencebench
uv run inferencebench --output-dir ../../datasets/inferencebench --limit 4 --overwrite
uv run inferencebench --output-dir ../../datasets/inferencebench --task-ids inferencebench-a-mistral-7b-21-1337
```

The adapter fetches the pinned upstream commit into `~/.cache/harbor-inferencebench`. `--upstream-dir` uses another checkout, and `--num-hours` changes the budget (the paper's main results use 2).

## Comparison with Original Benchmark (Parity)

Parity has not been run yet.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|--------------------------------|----------------------------|
| TBD | TBD | Aggregate speedup | TBD | 12 (100%) | TBD | TBD |

Oracle reference values from the paper's "vLLM default" row. They are a sanity check for the oracle, not a pass threshold:

| Scenario | A | B | C | D | Aggregate |
|---|---|---|---|---|---|
| Speedup | 1.25× ± 0.04 | 2.25× ± 0.10 | 48.69× ± 1.74 | 1.96× ± 0.06 | 4.05× ± 0.07 |

Links: [original benchmark](https://github.com/aisa-group/InferenceBench), [adapter PR](https://github.com/harbor-framework/adapters/pull/71). The fork, dataset PR, and parity PR are pending.

Reproduction scripts for both sides will be added with the parity results.

## Notes & Caveats

**Oracle.** The score is an unbounded speedup, so no solution can earn a fixed maximum. The oracle ships vLLM 0.11.0 with default settings. It installs it from upstream's lock and loads upstream's runtime shims (`src/eval/inference/runtime_shims`), as upstream's baseline measurement does; this vLLM release does not start with the pinned transformers release without them. The oracle is judged like any other run. An oracle trial passes if `valid` and `judge_valid` are 1; the values in the table above are a sanity check. Read `valid`, not the mean reward: a run whose server fails also scores 1.0. The oracle confirms the task and verifier end to end, but says nothing about agent capability.

The PyTorch server itself cannot be the oracle. Upstream measures its baseline at concurrency 1 with a 900 s request timeout, whereas the final evaluation uses each scenario's concurrency and a 300 s timeout. In scenario B, about half of its requests would exceed the timeout, and a failed run also scores 1×, so a score near 1× would not show that anything worked.

**Evaluation time limit.** Upstream's own Harbor adapter limits each evaluation attempt to 2 hours. This adapter does not, because scenario B alone takes vLLM's default settings about 2.4 hours, and any valid server slower than about 15 ms per token would fail on Harbor but not on the original benchmark. The evaluation stops 11.5 hours after the verifier starts, which assumes that Harbor's 12-hour verifier timeout is not scaled down; timeout multipliers below 1 are not supported.

**Judge.** A trial is graded only if the judge exits with status 0 and writes two valid verdict files. The judge needs `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` (it prefers the latter) and gets three attempts. Otherwise the trial is ungraded, as [Reward](#reward) describes, and has to be run again; this holds for the oracle too. Without a credential the verifier does not run the evaluation, so a forgotten credential costs the agent phase but not the hours of measurement; `INFERENCE_BENCH_JUDGE=off` is the explicit diagnostic mode. The judge reviews a read-only copy of the task directory at `/var/lib/ib_judge/task`, with the `/tmp` targets that the task directory links to in place, while the agent's home directory is closed to it. The three paths in upstream's prompt change accordingly.

**Quality reference.** `data/quality/` holds the PyTorch baseline's accuracy on the 500 cached MMLU-Pro questions. The value in this repository is still the paper's (128/500) and has not been measured for this adapter yet; [Recomputing the PyTorch quality reference](#recomputing-the-pytorch-quality-reference) describes the run that measures it. Every trial's `metrics.json` names the reference entry that its quality gate used.

**Model revision.** The healthcheck downloads commit `c170c708` of `mistralai/Mistral-7B-Instruct-v0.3`, which the repository's main branch has pointed at since 2025-12-03, into the agent's cache, and stores it as the cache's `main` reference so that a lookup by name finds it. The verifier downloads the same commit in its own sandbox; see [Separate verifier](#notes--caveats). The original benchmark downloads whatever `main` is. An agent's server that asks the Hub for `main` gets a newer commit if the repository has moved; `environment.json` lists the revisions in the agent's cache.

**Environment record.** Before the judge and the evaluation, the verifier writes `environment.json` to its log directory: the GPU model, memory, and driver; CPUs, memory, and disk; the image's Python packages, CUDA toolkit, package lock checksum, and agent CLI versions; the packages that the agent installed for its server; the model revision and the content hashes of the tokenizer files that the evaluator uses; the checksums of the cached samples and of the quality reference; the judge's CLI version and model; the hand-off (when it was packed, the parts' sizes and checksums, and which downloaded model files the agent changed); the agent's sandbox's GPUs and driver, whether they match the verifier's, and whether both are H100s; and the task's manifest (upstream commit, seeds, timeouts, lock file checksums). It also copies identifiers that a provider may set in the sandbox (`MODAL_REGION`, `MODAL_CLOUD_PROVIDER`, `MODAL_IMAGE_ID`, `MODAL_TASK_ID`, `MODAL_ENVIRONMENT`, `DAYTONA_SANDBOX_ID`, `DAYTONA_SANDBOX_SNAPSHOT`) when they are present, and no credential. The image digest is not visible inside the sandbox, and Harbor writes its own version and the resolved job to `lock.json` in the job directory; anything else about the machine comes from the provider. The recorder has five minutes, so a GPU that does not answer cannot hold up the verifier.

**Separate verifier.** The final evaluation runs in a second sandbox, which Harbor makes from a copy of `[environment]`: the same image, GPU, resources, and variables. This is Harbor's default for new tasks ([harbor#3712](https://github.com/harbor-framework/harbor/pull/3712)), and upstream's own Harbor adapter also uses a second sandbox, to which it passes `/home/agent` through a Modal volume. Here the hand-off goes through the trial directory instead, so it needs no volume, works on Daytona, Modal, and Docker, and stays with the trial:

- `collect.sh`, the `[[verifier.collect]]` hook, runs as root in the agent's sandbox after the agent phase. It stops every process of user `agent` and checks that none is left, as the end of the agent's container does in the original. It removes the state and credential files of the agent CLIs that upstream's adapter lists (Claude Code, Codex, Gemini CLI, OpenCode), Hugging Face tokens, and git and netrc credentials; a key that the agent wrote into any other file stays in the hand-off. It then packs `/home/agent`, and the `/tmp` targets of symbolic links in the task directory, which is what `run_task.sh` keeps of `/tmp`, into one tar stream in `/var/lib/ib_handoff`, a directory that only root can write. Symbolic links stay as they are, and hard links within the home or within the `/tmp` targets stay hard links; a `/tmp` file that shares its content with a file in the home gets a copy of its own, as with `cp -a`. Sockets, pipes, and device files are left out. The manifest lists the stream's parts with their sizes and checksums, and the GPUs and driver of the agent's sandbox. The agent tunes its server on one GPU and the verifier measures it on another, which can be a different H100 variant or run a different driver, whereas the original benchmark uses the same GPU for both. `environment.json` therefore records both sandboxes' GPUs and says whether they match and whether both are of the type that the task asks for. If not, `test-stdout.txt` has a warning and `inferencebench-score` lists the trial, which is graded and counted all the same.
- The model weights stay behind if the agent did not change them. The healthcheck records the files that it downloaded; `collect.sh` checks each one against the content hash that the Hub names it after, and leaves out those that match. A hard link to such a file, or a copy of it, anywhere in the hand-off is recorded instead of its content. The verifier downloads the same revision, with five attempts of up to an hour each, and puts all of them back. A file that the agent changed or added travels in the stream, and so does everything else in the home except the xet client's download cache, `hf_cache/xet`.
- The stream is split into parts of 2 GiB, below the 5 GiB that Harbor can download from a Modal sandbox in one file ([harbor#3924](https://github.com/harbor-framework/harbor/issues/3924)), and `task.toml` declares the manifest and 40 parts as artifacts, so the hand-off can hold up to 80 GiB. Harbor downloads each file on its own to the trial directory, stops the agent's sandbox, starts the verifier's, and uploads the files to the same path there. A file never passes through Harbor's directory archives, which have a ten-minute limit.
- `test.sh` takes the hand-off over as root and checks it against the manifest. Root then reads the parts and passes the stream over a pipe to user `agent`, who unpacks it into an empty `/home/agent` and puts the model files back. The hand-off itself stays closed to that user and to the judge. The unpacking refuses any member that would leave its destination, pass through a symbolic link, or link to anything but a file of the stream. It clears set-user-ID, set-group-ID, and sticky bits and gives directories their modes last, so a read-only directory can still receive the model files. If the hand-off is missing, damaged, or for another model revision, the trial gets no reward. An agent cannot place a hand-off of its own, because it cannot write to `/var/lib`.
- The agent's code still runs in the verifier's sandbox, as user `agent`: the evaluation server and whatever the judge's CLI starts. So the verifier keeps its own files from that user. It makes `/tests` and `/logs/verifier` owned by root before it uses them, so only root can write a reward. It builds the evaluator's requests with a tokenizer cache under `/opt/ib_eval_hf` that only root can write. Its scripts use a clean `PATH` and `PYTHONPATH`, and the image lists the agent-writable bin directory last, so root does not run a program that the agent planted. It starts the evaluation server and the judge with `no_new_privs`, and it stops every process of user `agent` after the judge, when the evaluation server's supervisor exits, and before it writes the reward.
- On Daytona and Modal, Harbor's uploads keep the uid of the user who runs Harbor. The image therefore gives user `agent` a uid that host users do not have (upstream's image uses 1000).

The hand-off has costs. The verifier downloads the pinned revision again, 29 GB in both of the repository's weight formats, before it starts. Everything else in the agent's home passes through the machine that runs Harbor twice, down from the agent's sandbox and up to the verifier's; for the oracle, that is mostly the vLLM packages that it installs. While Harbor uploads the parts, it stages a copy of each, so that machine needs free disk for about twice the hand-off. The trial directory keeps the parts as they are. Each part starts with a header that holds a NUL byte, so Harbor's secret scrubbing, which rewrites text files at the end of a trial, never changes a part and `harbor jobs regrade` finds them intact; it also means that the parts are not scrubbed. The stream is not compressed, so a search for a credential's value, such as `grep -a -F`, finds it in the parts too.

One limit remains. Harbor runs the collect hook in the task directory, which belongs to the agent. An agent that removes or renames that directory keeps the hook from running, so the trial has no hand-off and gets no reward, where the original would count a failed run. The model weights are the agent's to change, as in the original benchmark; the judge reviews the task directory, so it does not see a change to the model cache, here or in the original.

**Differences from the original benchmark:**

| | Original (HTCondor and Apptainer) | Harbor |
|---|---|---|
| Agent runs | runs the CLI under `timeout`, reruns it with a "continue" prompt until the budget ends, and starts the wrapper again after a failure (at most 3 runs) | stock agents run once, until Harbor's agent timeout; `ClaudeCodeUntilDeadline` repeats upstream's wrapper, and parity runs use it |
| Budget start | right before the agent starts | when the healthcheck finishes downloading the model |
| Server port | a free port chosen per run | fixed at 8000 |
| Evaluation time limit | none | evaluation stops 30 minutes before Harbor's 12-hour verifier limit, and the run then counts as failed |
| Agent's `PATH` | the user bin directory first | first for Claude Code and the evaluation server; other agents find it after the system directories |
| Prompt clause | "non-interactive mode" clause only for Claude | kept for every agent, because a registered task has one instruction |
| `nvidia-smi` wrapper, `check_cuda.py` | present | omitted |
| Starting points | `default`, `vllm_running`, `bare` | `default` only |
| `/data` bind mount | binds the host's `/data` read-only if it exists | none |
| Isolation | the agent and the final server each run in a container with its own PID namespace | each runs in a sandbox of its own; in the verifier's, the judge and the server run as user `agent`, and the verifier stops that user's processes between them |
| Hand-off | the final server's container mounts the agent's home and model cache | `collect.sh` packs `/home/agent` without the model files that the agent left unchanged and without the credential files that it knows of, and Harbor carries it to the verifier, which downloads the same revision for those files |
| Judge failure | the job exits with the judge's status and can be judged again (`run_rejudge.sh`) | the judge gets three attempts; then the trial is ungraded and has to be run again |
| No judge credential | the run does not start | the agent runs, but the evaluation does not, and the trial stays ungraded; `INFERENCE_BENCH_JUDGE=off` makes it a diagnostic run that is measured but not graded |
| Model download | the `main` branch at the time of the run | a pinned commit, downloaded in both sandboxes |
| Judge's view | the task directory, mounted read-only at `/home/agent/task`, and everything the agent left in `/tmp` | a read-only copy at `/var/lib/ib_judge/task` (the prompt's three paths change), and the `/tmp` targets of symbolic links in the task directory |
| Samples in the agent image | all cached seeds | the task's development seed and the quality seed |

**Samples.** LongBench-v2 has exactly 503 rows and the benchmark samples 503, so the cached file is byte-identical for all seeds and the seed only chooses requests at evaluation time. The image build downloads it and checks its sha256. Tasks therefore stay under 1 MB, and the build needs access to Hugging Face. A local Docker build cache shares that layer between the 12 tasks; environments that build each task's image separately download the samples once per task.

**Environments.** Daytona is the default for GPU runs. Modal runs GPU sandboxes under gVisor. The effect of either sandbox on latency measurements has not been measured; the oracle comparison will show it. On Docker, run one trial at a time: Harbor asks for a GPU by count and does not give concurrent trials different GPUs.

**Limitations.** The adapter covers the paper's main condition only: Mistral-7B on H100 with a 2-hour budget. The ablations with other models, budgets, and starting points are not included.

## Installation / Prerequisites

- [uv](https://docs.astral.sh/uv/) and Harbor 0.26.0 or newer
- One of:
  - Daytona: `uv tool install 'harbor[daytona]'`, then set `DAYTONA_API_KEY`
  - Modal: `uv tool install 'harbor[modal]'`, then `modal setup`
  - A host with Docker, the NVIDIA container runtime, and H100 GPUs
- `HF_TOKEN`: a read-only Hugging Face token; the task configuration requires the variable. If `mistralai/Mistral-7B-Instruct-v0.3` is gated for your account, accept its terms first.
- `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` for the judge, for every run including the oracle, and `ANTHROPIC_BASE_URL` if the API key belongs to a proxy. The judge uses `claude-sonnet-4-6`. Without a credential, no trial is evaluated or graded.
- The API key of your agent

## Troubleshooting

- **The trial ends with `RewardFileNotFoundError`:** read the last lines of `verifier/test-stdout.txt`. An `[ungraded]` line means that the trial has no valid judge verdicts; the reason is on that line and in `verifier/ungraded.json`, and `verifier/judge.log` has the judge's output. A `[fatal]` line means that the verifier stopped. If it names the hand-off, read `artifacts/var/lib/ib_handoff/collect.log` in the trial directory for the agent's side, `artifacts/manifest.json` for the files that Harbor did or did not bring, and `verifier/handoff.log` or `verifier/model_download.log` for the verifier's side. Otherwise, processes of user `agent` could not be stopped.
- **`inferencebench-score` exits with status 1:** a cell of the grid has no graded trial or more than one. The message names the cell, and the lines after it name the ungraded trials, the errors, and the reference runs.
- **`valid` is 0 and `quality_pass` is 0:** read `verifier/metrics.json`. A quantized server can fall below the 95% threshold; this is a real benchmark outcome.
- **`eval_valid` is 0:** read `verifier/eval.log` and `verifier/server.log`.
- **The image build fails at `sha256sum`:** the Hugging Face dataset changed. The samples no longer match the published benchmark.
- **The healthcheck fails, or the verifier cannot download the model:** check that `HF_TOKEN` can read the model repository and that the pinned commit still exists.
- **`collect.log` says that the hand-off is larger than 40 parts:** the agent's home, without the unchanged model files, is larger than 80 GiB. The trial cannot be graded.

## Citation

```bibtex
@article{yeon2026inferencebench,
  title   = {InferenceBench},
  author  = {Yeon, Jehyeok and Rank, Ben and Andriushchenko, Maksym},
  journal = {arXiv preprint arXiv:2607.20468},
  year    = {2026}
}
```

## Authors & Contributions

This adapter is developed and maintained by Yuanfan Chen. It builds on the Harbor adapter by the InferenceBench authors in [`src/harbor_adapter`](https://github.com/aisa-group/InferenceBench/tree/main/src/harbor_adapter) (Apache-2.0); `collect.sh` and `test.sh` are modified copies of their scripts.

**Issues and Contributions:** Please open issues or pull requests in the [adapters repository](https://github.com/harbor-framework/adapters).
