## EvoEval → Harbor Adapter

## Overview

This adapter converts **EvoEval_difficult** from [EvoEval](https://github.com/evo-eval/evoeval) into Harbor tasks.

- **Task type:** Python function completion. Each task gives a function signature and docstring, and the agent writes the function body.
- **Language:** Python 3.10, with the standard library and numpy available.
- **Size:** 100 tasks, which is every problem of `EvoEval_difficult` in the EvoEval v0.1.0 data release (`EvoEval/0` … `EvoEval/99`). Nothing is excluded.
- **Provenance:** the paper is [arXiv 2403.19114](https://arxiv.org/abs/2403.19114), the code is [evo-eval/evoeval](https://github.com/evo-eval/evoeval) (Apache-2.0), and the data comes from [evo-eval/evoeval_release](https://github.com/evo-eval/evoeval_release/releases/tag/v0.1.0).
- **Scoring:** a task is solved only if the solution passes every hidden test input under the original EvoEval evaluator. The benchmark score is pass@1, the mean reward over tasks.
- **Main adaptation:** the original harness asks a model for one completion and extracts the function from its reply. Here an agent works in a container and saves the completed code to `/workspace/solution.py`. That file is then scored by the original evaluator code. See [Notes & Caveats](#notes--caveats).
- **Other datasets:** `--dataset` can generate any of the seven EvoEval datasets (`EvoEval_difficult`, `creative`, `subtle`, `combine`, `tool_use`, `verbose`, `concise`). Only `EvoEval_difficult` is in scope: it is the dataset that is oracle-verified, used for parity and released here.

## What is EvoEval?

EvoEval (Xia, Deng and Zhang, 2024) is a set of coding benchmarks. It was built by using LLMs to "evolve" the 164 HumanEval problems into new problems.

Each problem was evolved in one of several ways: harder (`difficult`), more creative (`creative`), slightly changed (`subtle`), merged with another problem (`combine`), or requiring the use of given helper functions (`tool_use`). Two more datasets rephrase the HumanEval prompts, as `verbose` and `concise`.

The benchmark measures whether leaderboard rankings on HumanEval hold up on new problems. The paper reports an average drop of 39.4% for 51 LLMs.

Each problem ships with a canonical solution and a list of test inputs. The original evaluator works in three steps:

1. It runs the canonical solution on the inputs to get the expected outputs and reference runtimes.
2. It runs the candidate in a separate, resource-limited process. The time limit per input is `max(1 s, 4 × reference time)`, and memory is capped at 4 GiB.
3. It compares the outputs. Floats must match within `atol=1e-6`, and two problems (`EvoEval/10`, `EvoEval/32`) use special oracles.

The reported metric is pass@1 with greedy decoding.

## Adapter Features

- **Pinned data.** It downloads the EvoEval v0.1.0 release file, the same file `evoeval.data.get_evo_eval` uses, and checks its md5. You can also pass a local copy with `--data-file`, or keep a cache with `--cache-dir`.
- **Dataset selection.** `--dataset` selects one of the seven EvoEval datasets. The default is `EvoEval_difficult`.
- **Stable task names.** Each task is named `evo-eval/evoeval-auto__<dataset>-<n>`, for example `evo-eval/evoeval-auto__difficult-7` for upstream `EvoEval/7`. The task directory uses the local part, e.g. `difficult-7`.
- **Original prompt.** `instruction.md` starts with the original EvoEval prompt for API models (`Please complete the following code snippet.` followed by the code). One sentence is added that says where to save the code, which function to define, and that it must work with Python 3.10.
- **Original evaluator, vendored.** `tests/evoeval_eval/` holds the evaluator code from EvoEval v0.1.0 and EvalPlus 0.2.0. Only the import lines were changed. `tests/evaluate.py` is `evoeval.evaluate` reduced to one problem, with its default settings:
  - `--min-time-limit 1`
  - `--gt-time-limit-factor 4.0`
  - fast check, which stops at the first failing input
  - the same special oracles and the same `is_equal` comparison

  It computes the expected outputs inside the verifier container, as upstream does on its own machine. A local replay of the GPT-4 samples released by the EvoEval authors gives the same per-task results as upstream: 52/100, with 0 differences in reward or status.
- **Separate verifier container.** Grading runs in a fresh container built from `tests/Dockerfile` (`[verifier].environment_mode = "separate"`), never in the agent's container. Only `/workspace/solution.py` is copied over (`artifacts` in `task.toml`). The agent therefore cannot change the interpreter, the libraries or the grader used for scoring, and the task files with the problem data and canonical solution are never in the agent's container.
- **No network for the agent, except its model API.** While the agent runs, it has no network (`[agent] network_mode = "no-network"`). `--allow-agent-host` adds the agent's model API host. The verifier also runs without network (`[verifier] network_mode = "no-network"`).
- **Candidate isolated from the grader.** Upstream runs the candidate in a forked copy of the evaluator, which holds the expected outputs and the comparison code. Here `tests/sandbox_runner.py` runs the candidate in a fresh Python process as the unprivileged user `nobody`, which cannot read `/tests` or write the reward. This process sends back only its return values (`tests/codec.py`: builtin-only pickle or typed JSON, and nothing is executed on load). `evaluate.py` does every comparison with the upstream code, and it enforces the upstream time budget from outside.
- **Honest errors.** `test.sh` uses fixed paths, deletes any old reward file before scoring, and writes the reward only after a completed evaluation. If grading itself fails, no reward is written and the trial is reported as a verifier error, not as a 0.
- **Oracle.** `solution/solve.sh` writes `prompt + "\n" + canonical_solution` to `/workspace/solution.py`. This is the same program the original evaluator uses as ground truth.
- **Container images.**
  - **Agent:** `environment/Dockerfile` is `python:3.10.22-slim` with `numpy==2.2.6`, curl, git and build tools. It is identical for all tasks, so it is built once.
  - **Verifier:** `tests/Dockerfile` is `python:3.10.22-slim` with `numpy==2.2.6`, plus that task's `tests/`.

## Generated Task Structure

```
datasets/evoeval-auto/
├── difficult-0/
│   ├── task.toml                 # name = "evo-eval/evoeval-auto__difficult-0", authors, timeouts, resources
│   ├── instruction.md            # original EvoEval prompt + where to save the solution
│   ├── environment/
│   │   └── Dockerfile            # python:3.10.22-slim + numpy 2.2.6 (identical for all tasks)
│   ├── solution/
│   │   ├── solve.sh              # copies solution.py to /workspace/solution.py
│   │   └── solution.py           # prompt + canonical_solution
│   └── tests/                    # only in the separate verifier container
│       ├── Dockerfile            # verifier image: python:3.10.22-slim + numpy 2.2.6 + tests/
│       ├── test.sh               # runs evaluate.py, writes /logs/verifier/reward.txt
│       ├── evaluate.py           # evoeval.evaluate for one problem (ground truth + comparison)
│       ├── sandbox_runner.py     # runs the candidate as "nobody" and returns its outputs
│       ├── codec.py              # transfer of return values (builtin-only pickle / typed JSON)
│       ├── problem.json          # the original problem row (+ dataset name)
│       └── evoeval_eval/         # vendored EvoEval v0.1.0 / EvalPlus 0.2.0 evaluator
├── difficult-1/
└── ...                           # difficult-0 … difficult-99
```

Adapter code layout:

```
src/evoeval-auto/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── uv.lock
├── run_evoeval-auto.yaml            # oracle on the local dataset (Daytona)
├── run_evoeval-auto-parity.yaml     # Harbor side of the parity experiment
└── src/evoeval_auto/
    ├── __init__.py
    ├── adapter.py                   # EvoevalAutoAdapter: download, select, render tasks
    ├── main.py                      # CLI (--output-dir, --limit, --overwrite, --task-ids, --dataset, ...)
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/Dockerfile
        ├── solution/solve.sh
        └── tests/{Dockerfile, test.sh, evaluate.py, sandbox_runner.py, codec.py, evoeval_eval/}
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the dataset is published:

```bash
# Oracle (reference solutions)
harbor run -d evo-eval/evoeval-auto -a oracle

# An agent and model; the agent may reach only its model API host
harbor run -d evo-eval/evoeval-auto -a <agent_name> -m "<model_name>" \
  --allow-agent-host <model API host>
```

The tasks give the agent no network while it runs (`[agent] network_mode = "no-network"`), because the EvoEval data, including the canonical solutions and test inputs, is public. Pass the host of your agent's model API with `--allow-agent-host` (for example `api.openai.com` or `api.anthropic.com`; the flag can be repeated). The agent's install step still has network access. For agents built on litellm (such as `mini-swe-agent`), also set `--ae LITELLM_LOCAL_MODEL_COST_MAP=True`. Otherwise litellm tries to download its model cost map from GitHub when it starts, and the failed fetch can crash it. The verifier also runs without network.

### Using Job Configurations

From the repository root, after generating the tasks (see [Usage](#usage-create-task-directories)):

```bash
# Oracle on all tasks (Daytona; set DAYTONA_API_KEY)
harbor run -c src/evoeval-auto/run_evoeval-auto.yaml

# Or use the local dataset path directly
harbor run -p datasets/evoeval-auto -a <agent_name> -m "<model_name>" -e daytona \
  --allow-agent-host <model API host>

# Resume a job
harbor job resume -p jobs/<job-name>
```

Results are saved in `jobs/`.

### Running Individual Trial

```bash
harbor trial start -p datasets/evoeval-auto/difficult-0 -a oracle -e daytona
harbor trial start -p datasets/evoeval-auto/difficult-0 -a <agent_name> -m "<model_name>" -e daytona \
  --allow-agent-host <model API host>
```

## Usage: Create Task Directories

```bash
cd src/evoeval-auto
uv sync
uv run evoeval-auto --output-dir ../../datasets/evoeval-auto
```

Flags:

- `--output-dir`: where tasks are written. The default is `datasets/evoeval-auto` at the repository root.
- `--limit N`: generate only the first N tasks, in upstream order.
- `--overwrite`: replace existing task directories.
- `--task-ids ...`: generate only these tasks. Both upstream IDs (`EvoEval/7`) and local IDs (`difficult-7`) work.
- `--dataset NAME`: which EvoEval dataset to convert. The default is `EvoEval_difficult`. The choices are `EvoEval_difficult`, `EvoEval_creative`, `EvoEval_subtle`, `EvoEval_combine`, `EvoEval_tool_use`, `EvoEval_verbose` and `EvoEval_concise`.
- `--data-file PATH`: use a local copy of the release file (`.jsonl` or `.jsonl.gz`). Its md5 must match the v0.1.0 release.
- `--cache-dir DIR`: keep the downloaded release file in this directory. The default is to download into memory without caching.

## Comparison with Original Benchmark (Parity)

Both sides run the same CLI agent on all 100 `EvoEval_difficult` tasks: `mini-swe-agent@2.4.6`, requesting `openai/deepseek-v4.1-flash` through an OpenAI-compatible endpoint. The endpoint served every response from the snapshot `deepseek-v4-1-flash-261017`. Answers are scored with pass@1, where the per-run score is the percentage of tasks solved.

EvoEval has no agent harness; its original pipeline prompts a model once. So the original side is a fork of EvoEval (branch `harbor-parity`) with a runner that gives the agent the same instruction in the same container image. That runner reproduces Harbor's install command, CLI flags, environment variables, working directory, 1800 s timeout and network policy: during the agent run, only the model API host is reachable on both sides. It then scores the saved files with the fork's `evoeval.evaluate`: upstream, plus the float element-count correction described in Notes & Caveats.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| mini-swe-agent@2.4.6 | deepseek-v4-1-flash-261017 | pass@1 (%) | 3 | 100 (100%) | 65.33 ± 0.6667 | 65.33 ± 0.6667 |

Scores are mean ± sample SEM over 3 runs per side. The per-run scores are 66.0, 66.0 and 64.0 on the original side, and 66.0, 64.0 and 66.0 on Harbor. The ranges (64–66 on both sides) overlap. No run on either side had an infrastructure error.

- **Cross-scoring.** Every parity solution was also scored by the other side's evaluator: the 300 Harbor solutions with the fork's `evoeval.evaluate`, and the 300 original-side solutions with the Harbor verifier. The two evaluators gave the same result for all 600 solutions.
- **Unpatched baseline.** Scored with unpatched upstream `evoeval==0.1.0`, the original-side runs give 66.0, 66.0 and 64.0, the same as with the float correction.
- **Network.** In both setups, the agent could reach only the model API while it ran. Some agents ran commands that tried to reach the web, and these were blocked: 5–7 tasks per run on Harbor and 4–7 on the original side.

Links: [original benchmark](https://github.com/evo-eval/evoeval) · [parity fork](<original_parity_repo>) · [adapter PR](<adapter_pr>) · [dataset PR](<dataset_pr>) · [parity results](<parity_pr>)

**Reproduce the Harbor side** (from the repository root, after generating the tasks):

```bash
# env file with OPENAI_API_KEY, OPENAI_BASE_URL and DAYTONA_API_KEY
harbor run -c src/evoeval-auto/run_evoeval-auto-parity.yaml --env-file <env file> -y \
  --allow-agent-host <host of OPENAI_BASE_URL>
# equivalent flags:
harbor run -p datasets/evoeval-auto -e daytona -n 6 --env-file <env file> -y \
  -a mini-swe-agent -m openai/deepseek-v4.1-flash --ak version=2.4.6 \
  --ae UV_EXCLUDE_NEWER=2026-10-17T00:00:00Z --ae LITELLM_LOCAL_MODEL_COST_MAP=True \
  --allow-agent-host <host of OPENAI_BASE_URL>
```

**Reproduce the original side** (the fork's `harbor_parity/README.md` has the details):

```bash
git clone -b harbor-parity <original_parity_repo> evoeval && cd evoeval
uv venv --python 3.10.22 .venv
uv pip install --python .venv/bin/python -e . -r harbor_parity/requirements.txt
RUN=harbor_parity/runs/run1
.venv/bin/python harbor_parity/run_agent.py --run-dir $RUN --env-file <env file> \
  --model openai/deepseek-v4.1-flash --agent-version 2.4.6 --n-concurrent 6 \
  --agent-env UV_EXCLUDE_NEWER=2026-10-17T00:00:00Z --agent-env LITELLM_LOCAL_MODEL_COST_MAP=True \
  --allow-agent-host <host of OPENAI_BASE_URL>
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m evoeval.evaluate \
  --dataset EvoEval_difficult --samples $RUN/samples.jsonl --parallel 8
.venv/bin/python harbor_parity/summarize.py $RUN --out $RUN/result.json
```

The score is the percentage of the 100 tasks with reward 1 on Harbor, and with status `pass` in `evoeval.evaluate` on the original side.

## Notes & Caveats

The differences from the original harness fall into two groups:

- **Applied on both parity sides:** the agent writes a file, with no sanitizer; the added instruction sentence; no network for the agent except its model API; `OPENBLAS_NUM_THREADS=1`; the pinned versions; and the float element-count correction. The original side gets the correction as a documented one-line bugfix in the fork.
- **Harbor-side verifier hardening only:** the separate verifier container without network, and the candidate running in its own process with typed return values and the grader's own copy of the special-oracle arguments. The original side runs the unmodified upstream evaluator design.

  The hardening changes results in two semantic cases: return values whose own code decides equality, and functions that change their own arguments in `EvoEval/10`/`EvoEval/32` (details below). It also changes timing and memory slightly:
  - Returning values across processes adds time inside the same budget. On the slowest task, `EvoEval/9`, that is 29.5 s against 24.9 s upstream, within 56 s.
  - The candidate process starts with less memory counted against its 4 GiB limit.

  To show that these did not affect the parity numbers, every parity solution was scored by both evaluators (the cross-scoring in the parity section). They agreed on all 600 solutions.

- **An agent writes a file; no single completion is sanitized.** The original harness asks the model once. Its sanitizer (`evoeval/tool/sanitize.py`) then keeps only the target function from the reply and prepends the prompt header, so any helper functions or imports the model wrote outside the function are dropped. Here the agent saves `/workspace/solution.py`, and the verifier executes that file as written, without the sanitizer. This can change a score: a solution that needs its own top-level helper passes here, but would fail after sanitizing. The original-side parity runner scores the same file the same way.
- **The instruction adds one sentence.** `instruction.md` is the original API-model prompt (`Please complete the following code snippet.` with the code in a fence, using `prompt.strip()`). It is followed by one sentence naming the output file, the function and Python 3.10. Both parity sides use exactly the same text.
- **Expected outputs are computed per trial.** Like upstream, the verifier runs the canonical solution on the inputs to get the expected outputs and reference runtimes. Upstream caches them once per machine; here they are computed in each trial container. The time limits are relative to that reference runtime, so the limit and the candidate are timed on the same machine. This does not change a score.
- **numpy threads are limited.** The verifier sets `OPENBLAS_NUM_THREADS=1`. The upstream evaluator caps the candidate process at 4 GiB of virtual memory (`RLIMIT_AS`), and numpy's thread pool adds virtual memory in proportion to the CPU count. On a many-core machine this alone can make a correct solution fail; with the newer `evalplus` 0.3.1 this happens to the canonical solution of `EvoEval/9`. The original-side parity evaluation uses the same setting. It does not change a correct score.
- **The candidate runs in its own process.** Upstream runs the candidate in a process forked from the evaluator, so it starts with the evaluator's memory: the inputs and expected outputs of all 100 problems. It also compares the outputs inside that process. Here the candidate runs in a fresh interpreter as user `nobody`, with the same modules loaded (numpy, the vendored utilities), the same temporary working directory, `reliability_guard(4 GiB)`, `swallow_io` and per-input `time_limit`. It returns its outputs, and the grading process compares them with the unchanged upstream code. The overall budget is still `min(60, sum of limits) + 2` s, with the comparison time counted inside it. The process starts with less memory counted against the 4 GiB limit, which only matters for solutions that use close to 4 GiB.

  Return values are rebuilt exactly in the grader when they are one of the following:

  - builtin values: `None`, `bool`, `int`, `float`, `str`, `bytes`, `complex`, `list`, `tuple`, `dict`, `set`, `frozenset`;
  - numpy arrays and numpy scalars;
  - `collections.UserString`, `UserList` and `UserDict`, `fractions.Fraction` and `decimal.Decimal`.

  Subclasses of builtins are reduced to their builtin base (e.g. `np.float64` becomes `float`, a namedtuple becomes `tuple`), which is how the upstream `get_type` classifies them. A dict key or set member of another type is sent as the builtin `str`/`int`/`float`/`bytes` it hashes and compares equal to, because upstream only hashes and compares keys and members. Any other object becomes a value equal to nothing; upstream gives it the type `Unknown`, which fails against every builtin expected output of `EvoEval_difficult`.

  A differential test ran the canonical solution of all 100 tasks through 22 output transformations (numpy scalars and arrays, namedtuples, `UserString`/`UserList`/`UserDict` values and keys, `Fraction`, `Decimal`, type changes, an empty-array exploit, printing, exceptions). Both the upstream in-process check (with the float correction below) and this verifier scored every one of the 2,200 cases, and they gave the same status in all of them. The GPT-4 replay also matches upstream exactly.

  Values made only of exact builtin types (the normal case) cross as a pickle. The grader loads that pickle with an unpickler that refuses every global, so it can rebuild only builtin objects and never runs code. Other values cross as typed JSON. The slowest task, `EvoEval/9` with a 1M-element output, needs 29.5 s here against 24.9 s for the upstream in-process check on the same machine. Its budget is 56 s.

  Scores can still differ for return values whose own code decides equality: a builtin subclass that overrides `__eq__`, or an object of another type that equals something only through its own `__eq__`/`__hash__`. Upstream would run that code inside the comparison; here it is never run in the grader. The other difference is in the special oracles of `EvoEval/10` and `EvoEval/32`. Upstream checks the answer against the arguments as they are after the call, so a function that changes its own arguments changes its check. Here the oracles use the grader's own copy of the arguments.
- **Pinned versions.** The evaluator code is vendored from EvoEval v0.1.0 and EvalPlus 0.2.0. The verifier container runs Python 3.10.22 with numpy 2.2.6. Upstream does not pin `evalplus` or numpy. With evalplus 0.2.0 the canonical solutions pass 100/100, both locally and on Daytona.

  The vendored files are kept verbatim except for their import lines, so they can be diffed against upstream. They therefore still contain helpers that the adapter does not call (`untrusted_check`, `unsafe_execute`, `estimate_pass_at_k`, `evaluateb_files`, `trusted_check_exec`, ...) and upstream's bare `except` clauses.
- **The two `EvoEval_difficult` special oracles are kept.** `EvoEval/10` (palindrome) and `EvoEval/32` (polynomial root within `2e-2`) use the upstream checks. These are the GitHub-release oracles, which differ from the `test` field of the Hugging Face copy (that one uses `1e-6` for `EvoEval/32`). The adapter uses the GitHub release, as `evoeval.data` does.
- **Other EvoEval datasets are not validated.** `--dataset` can generate `creative`, `subtle`, `combine`, `tool_use`, `verbose` and `concise` tasks with the same evaluator branches as upstream. Only `EvoEval_difficult` is oracle-verified and used for parity. For `verbose` and `concise`, the reward is the base-test status, which is the upstream `pass@1`. The extra-test (`+`) status is recorded in `eval_result.json`.
- **Float comparison: one correction, on both sides.** Upstream `is_equal` compares float values (floats, or lists, tuples and arrays of floats) with `np.allclose(expected, output, atol=1e-6)`, which broadcasts. So an empty or shorter float list or array "matches". For example, returning `np.empty((0, 1))` passes every float-valued task, and `[2.0]` matches `[2.0, 2.0]`.

  The adapter (`tests/evaluate.py`) and the original-side fork (`evoeval/eval_test/__init__.py`) both add one check: two float values must have the same number of elements. Everything else is unchanged, including `atol=1e-6` and numpy's default `rtol=1e-5`.

  The correction changes no result of the 100 canonical solutions or of the 100 released GPT-4 solutions. For the parity runs, the original side also reports the unpatched upstream score as a baseline. In 29 of the 100 tasks, at least one expected output contains a value that upstream compares as a float. This count includes empty lists, which upstream's `is_floats` classifies as float lists. `EvoEval/5`, `EvoEval/20` and `EvoEval/21` return non-empty float lists.
- **The agent can reach only its model API.** The EvoEval data, including the canonical solutions and test inputs, is public. In parity runs made with open network, agents searched the web in some tasks, and in a few tasks they downloaded the benchmark data and used its canonical solution and tests. So the tasks give the agent no network while it runs, except the hosts given with `--allow-agent-host`. The original-side runner applies the same policy in the same way. This matches the original pipeline more closely: there, a model answers from the prompt alone. The agent's install step keeps network access. The verifier has no network either, so a solution cannot download answers while it is graded; this part is Harbor-only. One limit remains on the Harbor side. Harbor 0.23.0 restores the environment's network after the agent phase and only then collects `/workspace/solution.py`. So an agent that leaves a background process running could still change its file in that short window. The task cannot keep the restriction longer, because agent installs run under the same environment network. The original-side runner keeps the restriction until its sandbox is deleted. In the parity runs, some agents started background processes. All of them were calls to the model API that wrote to `/tmp`, and none touched `/workspace` or `solution.py`.
- **Benchmark issues found.**
  - **Data:** all 100 canonical solutions pass the original evaluator. The data, canonical solutions included, is public, so any harness that gives the agent open network lets it look up the answers. The network policy above closes this.
  - **Evaluator:** the upstream evaluator has two weaknesses:
    1. **Float broadcasting.** The float comparison broadcasts. This is fixed on both sides, as described above.
    2. **Candidate inside the evaluator.** Upstream runs the candidate inside the evaluator process, next to the expected outputs and the comparison code. Code there can read the expected outputs, replace the comparison, or change the special-oracle arguments. The adapter closes this with the Harbor-side isolation described above.

  Neither fix changes the score of the canonical or the GPT-4 solutions.

## Installation / Prerequisites

- [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer to run the adapter. The adapter has no third-party dependencies.
- Harbor installed as a CLI tool. The experiments here used `harbor==0.23.0`:
  ```bash
  uv tool install "harbor[daytona]==0.23.0"
  ```
- A container backend: Docker locally, or Daytona with `DAYTONA_API_KEY` set. All experiments here ran on Daytona.
- For agent runs, the model API keys, for example `OPENAI_API_KEY` and `OPENAI_BASE_URL` for an OpenAI-compatible endpoint.
- Network access to `github.com` when generating tasks, to download the EvoEval release file.

## Troubleshooting

- **`md5 ... expected ...` when generating:** the downloaded or local file is not the v0.1.0 release file. Delete the cached copy, or pass the correct file with `--data-file`.
- **Verifier error with no reward:** the evaluator could not compute the expected outputs, for example because the container ran out of memory. Check `verifier/test-stdout.txt` in the trial folder. The tasks need about 4 GB of RAM because some inputs are very large: `EvoEval/9`, `/16` and `/23` use inputs of 1M–10M elements.
- **`eval_result.json`:** the verifier writes this file to `/logs/verifier/`. It holds the status (`pass`, `fail` or `timeout`), the number of inputs checked and the index of the first failing input.
- **Timeouts on slow machines:** the per-input time limits are relative to the reference runtime measured in the same container, so they adapt to the machine. Even so, very overloaded hosts can cause spurious timeouts. Use fewer concurrent trials if this happens.

## Citation

```bibtex
@article{evoeval,
  author    = {Xia, Chunqiu Steven and Deng, Yinlin and Zhang, Lingming},
  title     = {Top Leaderboard Ranking = Top Coding Proficiency, Always? EvoEval: Evolving Coding Benchmarks via LLM},
  year      = {2024},
  journal   = {arXiv preprint},
}
```

## Authors & Contributions

This adapter was developed by [Yuangang Li](mailto:yuanganl@uci.edu).

EvoEval is by Chunqiu Steven Xia, Yinlin Deng and Lingming Zhang (University of Illinois Urbana-Champaign).

**Issues and Contributions:**

- Submit issues and pull requests to [harbor-framework/adapters](https://github.com/harbor-framework/adapters).
- For problems with the benchmark data or the original evaluator, use [evo-eval/evoeval](https://github.com/evo-eval/evoeval).
