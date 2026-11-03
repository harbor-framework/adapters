## EvoEval → Harbor Adapter

## Overview

EvoEval evaluates the Python code-generation ability of LLMs on problems that were
*evolved* from HumanEval by an LLM. Each problem is a Python function stub (signature +
docstring, sometimes with imports and helper functions) that must be completed; it is
graded by running the candidate on the problem's test inputs and comparing every output
with the output of the canonical solution.

- **Source**: [evo-eval/evoeval](https://github.com/evo-eval/evoeval) (code, commit
  `d5ca3104ec30b99f1076f51d4476eb4c3f29effa` = PyPI `evoeval==0.1.0`) and the data release
  [evo-eval/evoeval_release v0.1.0](https://github.com/evo-eval/evoeval_release/releases/tag/v0.1.0)
- **Paper**: [arXiv:2403.19114](https://arxiv.org/abs/2403.19114); website
  [evo-eval.github.io](https://evo-eval.github.io)
- **License**: Apache-2.0
- **Language / domain**: Python function-level code generation
- **This adapter**: the **EvoEval_difficult** dataset, **100 tasks** = all 100 problems
  (`EvoEval/0` … `EvoEval/99`) of `EvoEval_difficult.jsonl` in release v0.1.0. No problem is
  excluded. `--dataset` can select the other six EvoEval datasets (creative, subtle, combine,
  tool_use, verbose, concise), but only EvoEval_difficult is validated (oracle; parity
  results in the parity section).
- **Main adaptation**: the upstream harness asks a model for a completion and evaluates the
  returned program; here an agent writes the program to `/workspace/solution.py` and the
  unmodified upstream evaluator grades it.

## What is EvoEval?

EvoEval (Xia, Deng and Zhang, 2024, "Top Leaderboard Ranking = Top Coding Proficiency,
Always? EvoEval: Evolving Coding Benchmarks via LLM") turns the 164 HumanEval problems into
seven new benchmarks by prompting an LLM to transform them: *difficult*, *creative*, *subtle*,
*combine*, *tool_use* (semantic-altering) and *verbose*, *concise* (semantic-preserving). The
goal is to test whether high HumanEval scores reflect general coding ability or overfitting to
the original problems. **EvoEval_difficult** makes each problem harder by adding constraints,
requirements or extra reasoning steps. The paper reports greedy pass@1: a problem counts as
solved when the single generated program passes all test inputs. On EvoEval_difficult the
paper reports, for example, GPT-4 52.0, Claude-3-opus 50.0, DeepSeek-Coder-33B-Instruct 47.0
and ChatGPT 33.0 (Table 2).

## Adapter Features

- **Pinned data**: downloads `EvoEval_<name>.jsonl.gz` from the v0.1.0 release (the URL used
  by upstream `evoeval.data`) and checks the EvoEval_difficult md5
  (`5888868439a2392c01bbcf078c7ee810`); `--data-path` accepts a local copy.
- **Upstream grading**: each task's `tests/vendor/` holds byte-identical copies of the
  upstream evaluator (`evoeval/evaluate.py`, `data.py`, `eval_test/`) and of its dependency
  `evalplus` 0.2.0. `tests/evaluate.py` computes expected outputs and reference times with
  upstream `get_groundtruth` and judges every output with the upstream comparison
  (type-strict `is_equal`, float tolerance `np.allclose(atol=1e-6)`, the EvoEval/10 and
  EvoEval/32 special oracles) under the upstream CLI defaults (`--min-time-limit 1`,
  `--gt-time-limit-factor 4.0`, fast check, 4 GB memory limit, 60 s overall cap), plus two
  documented scoring bugfixes that the parity runs apply on both sides (see Notes).
- **Separate verifier sandbox**: `[verifier].environment_mode = "separate"`. Harbor copies
  `/workspace/solution.py` out of the agent's sandbox (task `artifacts`), stops that sandbox,
  and grades in a fresh `python:3.9.19-slim-bookworm` sandbox to which it uploads `tests/`;
  `test.sh` installs the pinned evaluator packages there. The hidden tests never enter the
  agent's container.
- **Isolated candidate execution**: upstream runs submitted code in a fork of the grader,
  where it could replace the comparison or read the hidden data. Here the candidate runs in a
  separate process as user `nobody` (`tests/isolated_runner.py`, same `reliability_guard`,
  `swallow_io` and time limits as upstream `unsafe_execute`), never receives the expected
  outputs, cannot read `/tests` (root-only), and returns plain-data outputs that the grader
  compares with its own copy of the inputs. Results cross the process boundary as pickles
  restricted to plain data (no class-creating globals such as `builtins.type`), so a forged
  result stream cannot fake a match.
- **Checked against upstream**: on 700 programs (100 canonical + the 600 released upstream
  samples of six models) the Harbor verifier, the pure upstream evaluator and the fork's
  evaluator with the two fixes give identical verdicts, and the per-model pass@1 equals the
  paper (parity upload: `results_collection/verifier_check_released_samples.json`). Each
  evaluator runs in its own interpreter, so the pure upstream baseline is unpatched.
- **Reward**: `1` if the base status is `pass`, else `0` (`/logs/verifier/reward.txt`);
  details (status, inputs checked, reason) go to `/logs/verifier/evaluation.json`. The mean
  reward over the dataset is EvoEval's pass@1. A verifier failure (not a wrong answer) writes
  the non-numeric marker `VERIFIER_ERROR`, so Harbor reports an error instead of a 0.
- **Agent environment**: `python:3.9.19-slim-bookworm` with `numpy==1.26.4` and the other
  third-party packages of the upstream evaluation image, pinned to their March 2024 releases
  (upstream's evaluation image is `python:3.9-slim-buster` + `pip install evoeval`). The
  image is the same for every task and contains no task data and no benchmark code. Agents
  run as the unprivileged user `agent` (`[agent].user`).
- **Oracle**: writes `prompt + "\n" + canonical_solution`, the exact program upstream uses as
  ground truth.
- **Parity agent** (`src/evoeval-auto/src/evoeval_auto/parity_agent.py`,
  `evoeval_auto.parity_agent:EvoEvalCodegenAgent`): the original EvoEval harness for API chat
  models as a Harbor agent. It sends one greedy chat completion with the upstream system
  message and template (`"Please complete the following code snippet.\n```\n{prompt}\n```"`),
  sets `max_tokens` like upstream (`num_tokens(message) + max_new_tokens`), applies the upstream
  `tool/sanitize.py` logic to the reply, and writes the result to `/workspace/solution.py`.
  The only setting that differs from upstream is `max_new_tokens` (32768 instead of 512, on
  both sides; see Notes).

## Generated Task Structure

```
datasets/evoeval-auto/
├── evoeval-difficult-0/
│   ├── task.toml                 # name, authors, limits, artifacts, separate verifier env
│   ├── instruction.md            # the upstream prompt + where to write the solution
│   ├── environment/
│   │   └── Dockerfile            # python:3.9.19 + pinned third-party packages
│   ├── solution/
│   │   ├── solve.sh              # copies solution.py to /workspace/solution.py
│   │   └── solution.py           # prompt + "\n" + canonical_solution
│   └── tests/
│       ├── test.sh               # installs evaluator deps, runs evaluate.py, writes the reward
│       ├── evaluate.py           # upstream ground truth + comparison for this problem
│       ├── isolated_runner.py    # runs the candidate as `nobody`
│       ├── problem.json          # the upstream problem record (prompt, canonical, inputs)
│       └── vendor/               # unmodified upstream evoeval evaluator and evalplus 0.2.0
├── evoeval-difficult-1/
└── ...
```

Task names are `evoeval/<dataset-slug>-<N>` for upstream id `EvoEval/N`
(e.g. `evoeval/evoeval-difficult-7`); directories drop the `evoeval/` prefix.

Adapter code layout:

```
src/evoeval-auto/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_evoeval-auto.yaml         # reference config (oracle by default)
├── run_evoeval-auto_parity.yaml  # Harbor side of parity (parity agent)
└── src/evoeval_auto/
    ├── __init__.py
    ├── adapter.py                # EvoEvalAdapter: load release data, write tasks
    ├── main.py                   # CLI (uv run evoeval-auto ...)
    ├── parity_agent.py           # EvoEvalCodegenAgent
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/Dockerfile
        ├── solution/solve.sh
        └── tests/{test.sh,evaluate.py,vendor/}
```

## Run Evaluation / Harness

### Running with Datasets Registry

The dataset is not published to the registry yet (registry link: not published). After
publishing it would be run with:

```bash
harbor run -d evoeval/evoeval-auto -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

From the repository root, after generating the tasks (see Usage):

```bash
# Oracle (default agent in the config)
uvx --python 3.12 --from "harbor[daytona,adapter]==0.23.0" harbor run \
  -c src/evoeval-auto/run_evoeval-auto.yaml --env-file oracle.env -y

# Any agent on the locally generated dataset
uvx --python 3.12 --from "harbor[daytona,adapter]==0.23.0" harbor run \
  -p datasets/evoeval-auto -a <agent_name> -m "<model_name>" -e daytona -n 12 --env-file oracle.env -y
```

`-e docker` works as well when Docker is available. Results are written to `jobs/`.

### Running Individual Trials

```bash
uvx --python 3.12 --from "harbor[daytona,adapter]==0.23.0" harbor run \
  -p datasets/evoeval-auto -i evoeval-difficult-10 -a oracle -e daytona --env-file oracle.env -y
```

## Usage: Create Task Directories

```bash
cd src/evoeval-auto
uv sync
uv run evoeval-auto                                   # all 100 EvoEval_difficult tasks -> <repo>/datasets/evoeval-auto
uv run evoeval-auto --output-dir /path/to/out --overwrite
uv run evoeval-auto --task-ids EvoEval/0 evoeval-difficult-1 2 --overwrite
uv run evoeval-auto --limit 10
uv run evoeval-auto --dataset EvoEval_creative --output-dir ../../datasets/evoeval-creative   # unverified datasets
```

Flags:

- `--output-dir`: where to write tasks (default `<repo>/datasets/evoeval-auto`)
- `--limit N`: only the first N tasks (by upstream number)
- `--overwrite`: replace existing task directories
- `--task-ids`: upstream ids (`EvoEval/7`), task names (`evoeval-difficult-7`) or numbers (`7`)
- `--dataset`: one of `EvoEval_difficult` (default), `EvoEval_creative`, `EvoEval_subtle`,
  `EvoEval_combine`, `EvoEval_tool_use`, `EvoEval_verbose`, `EvoEval_concise`
- `--data-path`: local `<dataset>.jsonl[.gz]` instead of downloading
- `--cache-dir`: optional cache directory for the downloaded release file

## Comparison with Original Benchmark (Parity)

**Oracle verification**: the oracle passes **100/100** tasks (mean reward 1.000, 0 errors) on
Daytona with Harbor 0.23.0 (job `oracle-r10`, final task format: separate verifier sandbox,
unprivileged agent, isolated candidate execution).

**Parity** (all 100 tasks, 3 runs per side, both sides run at the same time; scores are pass@1
in %, mean ± sample SEM):

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| evoeval-codegen@1.0.0 | deepseek-v4-1-flash-260910 | pass@1 (%) | 3 | 100 (100%) | 57.67 ± 1.20 | 60.33 ± 0.67 |

- Runs: original [56.0, 60.0, 57.0], Harbor [59.0, 61.0, 61.0]. The ranges [56, 60] and
  [59, 61] overlap, so the sides match under the guide's criterion.
- The original side applies the same two scoring fixes as the Harbor verifier (see Notes).
  Scored with the pure upstream evaluator, the original runs are also [56.0, 60.0, 57.0].
- Agent: `evoeval-codegen` is the original EvoEval harness as a Harbor agent (see Adapter
  Features). This is guide scenario 3 (custom agent): EvoEval has no agent, only one model
  call per problem. The model was requested as `deepseek-v4.1-flash` through an
  OpenAI-compatible gateway; every response on both sides reported
  `deepseek-v4-1-flash-260910`. Settings on both sides: temperature 0, `n=1`,
  `max_tokens = prompt tokens + 32768`, 900 s per request, no practical overall deadline,
  same retry waits. No request needed a retry; prompt tokens were identical on both sides
  (79,227 over 3 runs).
- Sanity check before the full runs (EvoEval/0–9): original 6/10, Harbor 5/10.
- **Why the sides differ by 2.7 points.** The model's output changes from call to call even at
  temperature 0: in run 1, 97 of 100 programs differed between the sides. Every one of the 600
  parity programs, plus the 100 canonical programs, gets the same verdict from the pure
  upstream evaluator, the Harbor verifier and the fork's evaluator with the fixes, each run in
  its own interpreter (parity upload: `results_collection/verifier_check_parity_programs.json`). Those verdicts reproduce each
  side's run scores. So grading and environment add nothing to the
  gap; it comes from which programs the model happened to produce. (The Harbor parity jobs
  ran before the last verifier change, a tighter result allow-list; this check re-grades their
  programs with the final verifier and gives the same 59/61/61.)
- **Tasks that disagreed in every run.** Debug playbook step 5: tasks 11, 30, 41, 50 and 84
  were re-run 8 times in isolation on each side (original vs Harbor passes): 5/8 vs 8/8,
  6/8 vs 8/8, 7/8 vs 5/8, 6/8 vs 6/8 and 3/8 vs 5/8. EvoEval/50 passed only on Harbor in all
  three runs but is equal in isolation, and tasks 30 and 41 move in opposite directions.
  This fits sampling noise, not a systematic difference.
- **Standard CLI agent** (required for custom-agent parity; not a parity comparison):
  terminus-2@2.0.0 with the same model, 1 run on the same 100 tasks, reward 1 on **64/100**.

Links: original benchmark [evo-eval/evoeval](https://github.com/evo-eval/evoeval); original-side
fork: not published yet (based on upstream `d5ca3104`); adapter PR: [harbor-framework/adapters#72](https://github.com/harbor-framework/adapters/pull/72);
dataset PR: [harbor-framework/harbor-datasets#271](https://github.com/harbor-framework/harbor-datasets/pull/271); parity results upload: not published yet.

Reproduction:

```bash
# Harbor side (from the repository root; tasks generated into datasets/evoeval-auto)
# oracle.env: OPENAI_API_KEY, OPENAI_BASE_URL (OpenAI-compatible endpoint), DAYTONA_API_KEY
PYTHONPATH=src/evoeval-auto/src TIKTOKEN_CACHE_DIR=$PWD/tmp/tiktoken-cache \
uvx --python 3.12 --from "harbor[daytona,adapter]==0.23.0" harbor run \
  -c src/evoeval-auto/run_evoeval-auto_parity.yaml -p datasets/evoeval-auto -n 10 \
  --env-file oracle.env -y --job-name parity-harbor-run1
# (sanity subset: add  -i 'evoeval-difficult-?')

# Original side: the EvoEval fork (base d5ca3104, not published yet); its README has the environment
cd evoeval-fork
fork-venv/bin/python harbor_parity/run_original.py --env-file ../oracle.env \
  --data-file EvoEval_difficult.jsonl --out-root ../parity-original --run-name run1 --shards 10
# (sanity subset: --task-numbers 0-9)

# Standard CLI agent
uvx --python 3.12 --from "harbor[daytona,adapter]==0.23.0" harbor run -p datasets/evoeval-auto \
  -a terminus-2 -m openai/deepseek-v4.1-flash \
  --ak 'model_info={"max_input_tokens":131072,"max_output_tokens":32768,"input_cost_per_token":0.0,"output_cost_per_token":0.0}' \
  -e daytona -n 8 --env-file oracle.env -y
```

A run's pass@1 (%) is 100 × (tasks with reward 1) / 100 on the Harbor side and 100 ×
(tasks with base status `pass`) / 100 on the original side (`summary.json`). Mean ± sample
SEM is computed over the three runs.

## Notes & Caveats

- **Only EvoEval_difficult is validated.** The other datasets can be generated with
  `--dataset`; the verifier uses the upstream evaluator's own dataset handling for them, but no
  oracle or parity run was done.
- **Complete-program grading, no sanitization in the verifier.** Upstream's
  `tool/sanitize.py` keeps only the target function plus the prompt's preamble from a raw LLM
  reply (dropping the model's own imports and helpers). Agents write a program file, which is
  executed as is; this matches the complete-code sample format in the upstream README. The
  parity agent applies the upstream sanitizer to its LLM reply, as the original pipeline does.
- **CRLF prompts.** Ten EvoEval_difficult prompts use CRLF line endings; the instruction uses LF
  (Harbor reads `instruction.md` with universal newlines anyway). `tests/problem.json` keeps the
  original text for the evaluator.
- **Reasoning-model token budget.** The parity model counts reasoning tokens in `max_tokens`;
  upstream's `max_new_tokens=512` returns empty answers, so both sides use 32768. The request
  timeout is 900 s on both sides (upstream: 100 s).
- **No `COPY` in the Dockerfile.** With Daytona, a Docker build context makes the Daytona SDK
  clear `os.environ` while uploading the context, which crashed the Harbor process (SIGSEGV)
  in our runs. The agent therefore creates `/workspace/solution.py` itself.
- **`OPENBLAS_NUM_THREADS=1`** is set in `test.sh` (and on the original side) so that OpenBLAS
  thread buffers cannot exhaust the evaluator's 4 GB address-space limit on many-core hosts.
- **Isolated execution vs. upstream's in-process execution.** The candidate runs in its own
  process (see Adapter Features). Outputs are reduced to plain data along upstream's
  `get_type` categories before they reach the grader: exact builtin and numpy values are
  unchanged, a subclass (e.g. a namedtuple or an `int` subclass defined in the solution) is
  compared as its base type, as upstream's `isinstance`-based `is_equal` does, and objects of
  other candidate-defined classes cannot match. Only a solution relying on a custom `__eq__`
  could be judged differently from upstream. The overall time budget starts once the runner's
  interpreter is up (upstream forks an already running interpreter).
- **Scoring bugfix 1, float shapes.** Upstream's `is_equal` compares float values with
  `np.allclose`, which broadcasts, and `is_floats([])` is true; so `[]` (or `[v]`) was accepted
  for any scalar float and `[v]` for `[v, v, v]`. For example, returning `[]` passed all 20
  inputs of EvoEval/4. The verifier requires equal shapes before the upstream comparison
  (wrapper in `tests/evaluate.py`; the vendored file is unchanged).
- **Scoring bugfix 2, special-oracle inputs.** Upstream passes the input object *after* the
  candidate's call to the EvoEval/10 and EvoEval/32 oracles (the upstream code has a TODO about
  this), so a candidate that mutates its input changes what is checked. The verifier passes its
  own copy of the input.
- **Effect of the fixes and how parity handles them.** On the 700 checked programs neither fix
  changes any verdict. The original side of parity applies the same two fixes (opt-in switches
  in the fork's evaluator) and also reports the pure upstream score of every run, so the
  original baseline stays visible (see the parity section).
- **Other upstream comparison properties are kept**: `2` vs `2.0` fails (type-strict), a tuple
  of floats matches a list of floats, NaN equals NaN.
- **Verifier errors are not scores.** `test.sh` replaces any existing reward file before
  grading; it writes `1`/`0` on a verdict and the non-numeric marker `VERIFIER_ERROR` if the
  verifier itself fails (e.g. the evaluator packages cannot be installed), which Harbor
  records as a verifier error. A failed verification is never turned into a 0 (guide debug
  playbook).
- **Network in the verifier sandbox.** `test.sh` installs the pinned packages from PyPI (about
  10 s); it retries three times.
- **Python 3.9 image.** Code that needs Python ≥ 3.10 syntax fails, as in the upstream
  evaluation image.
- **Parity time limits.** The original harness retries a request until it succeeds, with no
  overall deadline; the parity job therefore raises the Harbor agent deadline to 10 hours
  (`agent_timeout_multiplier: 30` in `run_evoeval-auto_parity.yaml`) and the fork gets the same
  36000 s per-problem deadline. The 900 s limit applies to the whole SDK call on both sides,
  retry waits are the same, and both sides log attempts per request.

## Installation / Prerequisites

- Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/) for the adapter (`cd src/evoeval-auto && uv sync`).
- Harbor 0.23.0: `uvx --python 3.12 --from "harbor[daytona,adapter]==0.23.0" harbor ...`
  (or `uv tool install "harbor[daytona,adapter]==0.23.0"`).
- Docker, or a Daytona account (`DAYTONA_API_KEY`) for `-e daytona`.
- Parity only: `OPENAI_API_KEY` and `OPENAI_BASE_URL` for an OpenAI-compatible endpoint that
  serves the model, and `PYTHONPATH=src/evoeval-auto/src` so Harbor can import the parity agent.

## Troubleshooting

- **Harbor process exits with code 139 on Daytona**: the task Dockerfile must not use `COPY`
  /`ADD` (see Notes). Regenerate the tasks with this adapter version. Delete leftover sandboxes
  of the crashed job.
- **Trial shows a verifier error instead of a reward** (`reward.txt` contains
  `VERIFIER_ERROR`): `/logs/verifier/evaluation.json` has a `verifier_error` traceback (e.g. the isolated runner could not start), or `pip.log` shows that
  the evaluator packages could not be installed in the verifier sandbox (it needs access to
  PyPI). This is an infrastructure problem, not a wrong answer; rerun the trial.
- **Daytona says "Only ephemeral sandboxes are permitted"** for the helper scripts: they
  already create ephemeral sandboxes (`ephemeral=True`); use the version in this adapter.
- **`No tasks matched the filter(s)`**: `-i` matches directory names such as
  `evoeval-difficult-10`, not `evoeval/evoeval-difficult-10`.
- **Parity agent import error**: set `PYTHONPATH=src/evoeval-auto/src` when running Harbor.
- **Empty model answers**: increase `max_new_tokens` (`--ak max_new_tokens=...`); reasoning
  tokens count against `max_tokens`.
- **Verifier reports `timeout` for a correct but slow solution**: the time limit per input is
  `max(1 s, 4 × reference time)`, as upstream.

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

This adapter was built by yuanganl (yuanganl@uci.edu) with an AI coding assistant (Claude Code). The
EvoEval benchmark and its evaluator are by Chunqiu Steven Xia, Yinlin Deng and Lingming Zhang
(University of Illinois Urbana-Champaign).

Issues and contributions: open an issue or pull request in the Harbor adapters repository.
