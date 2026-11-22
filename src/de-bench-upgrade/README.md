# de-bench Upgrade adapter

## Overview

Adapts the 62 upgrade-v2 tasks from Astronomer's de-bench at commit
`5dcfc2b81b13dcf58cff49e192e97f1ae05f8dbc`. This is an implementation and oracle
validation milestone, **not a parity-validated or published dataset**.

The final locked full-runtime Harbor oracle passes **62/62 tasks with zero
exceptions**. All oracle check outcomes match the original scoring body run in
Docker. See [validation evidence](validation/README.md) for baseline checks,
reproduction commands and the remaining parity gates.

## What is de-bench?

[de-bench](https://github.com/astronomer/de-bench) measures coding agents on data
engineering projects. The upgrade-v2 world supplies independent Airflow migration
projects, reference solutions, and 214 named static checks across 62 ready tasks.
All 62 tasks in this revision have `live_env: false`, no replay/history, no
external verifier, and no solution deletion manifests. Some checks named
`import_ok` inspect Python ASTs; they do not import Airflow or start a service.

## Adapter Features

- Uses the pinned upstream task parser, workspace/oracle archives, and unmodified
  scoring code. A dirty checkout or different commit is rejected.
- Preserves all declared checks, `delivered`, `do_not_modify`, tri-state outcomes,
  and the original binary `pass` aggregation. Legacy `scoring.weights` fields
  are not the metric used by de-bench's current `score_workspace` entry point.
- Captures a binary patch against the original private workspace, then rebuilds
  a clean scoring tree. Agent commits do not hide modifications. Upstream runtime
  output exclusions are extracted from its source, and stashed changes recovered
  in a temporary copy before capture. Recovery imports only validated Git objects
  and commit IDs into a fresh repository; submitted Git configuration, hooks,
  alternates and inherited Git settings are never used. Escaping file/directory
  symlinks are rejected before capture, after stash recovery and before scoring.
- Keeps scorer and reference answers outside the Docker build context. They are
  supplied by Harbor for verification, after the agent completes. Reference
  overlays support `.deleted` globs without allowing paths outside the workspace.
- Produces stable names, source hashes, complete inventory, and explicit selection.
  Unsupported runtime features fail closed rather than dropping their checks.
- `upstream-runtime` (default) installs a locked adaptation of the upstream runtime;
  `scoring-smoke` is a small Python 3.12 image for oracle/scorer validation only.

## Generated Task Structure

```text
<output>/
  inventory.json
  selection.json
  <task-id>/
    task.toml
    instruction.md
    provenance.json
    environment/{Dockerfile,bootstrap.py,add-excludes.json,workspace/}
    environment/runtime-requirements.txt  # full runtime only
    solution/{solve.sh,apply.py,overlay/}
    tests/{test.sh,verify.py,config.json,checks.yaml,workspace.tar,oracle/,upstream/}
```

`tests/upstream/` includes the upstream Apache-2.0 license and exact scorer source.
Generated task/data artifacts belong outside the adapter source repository.

## Run Evaluation / Harness

Registry execution is unavailable until publication. From the adapters repository
root, after generating the dataset below:

```bash
harbor run -p datasets/de-bench-upgrade -a oracle
# Equivalent reference configuration:
harbor run -c src/de-bench-upgrade/run_de-bench-upgrade.yaml
```

Only oracle runs have been authorized so far. Do not treat scoring-smoke results
as evidence about agent performance in the upstream tool environment.

## Usage: Create Task Directories

```bash
git clone https://github.com/astronomer/de-bench.git /tmp/de-bench-upstream
git -C /tmp/de-bench-upstream checkout 5dcfc2b81b13dcf58cff49e192e97f1ae05f8dbc
cd src/de-bench-upgrade
uv sync --locked

# Inventory only: stdout JSON, no task generation.
uv run de-bench-upgrade --upstream-root /tmp/de-bench-upstream \
  --output-dir ../../datasets/de-bench-upgrade --list-compatible

# All 62 tasks, using the fuller runtime image.
uv run de-bench-upgrade --upstream-root /tmp/de-bench-upstream \
  --output-dir ../../datasets/de-bench-upgrade

# Five predefined tasks covering DAG, imports, provider, Cosmos, DAG Factory.
uv run de-bench-upgrade --upstream-root /tmp/de-bench-upstream \
  --output-dir /tmp/de-bench-smoke --split smoke --environment-profile scoring-smoke
```

For full-runtime builds on networks with inaccessible PyPI endpoints, add
`--package-index-url https://mirrors.aliyun.com/pypi/simple/` (used in local runtime
validation). The selected index is recorded in provenance.

Also supports `--limit N`, `--task-ids ID [ID ...]`, and `--overwrite`.
Explicit unknown/unsupported IDs are errors. Overwrite only replaces selected
adapter-owned task directories; unrelated directories are rejected. Use a fresh
output directory when changing subsets: generation rejects unselected old tasks
rather than allowing Harbor to run a larger dataset than the selection manifest.
The `smoke` split is a deterministic engineering sample, not a statistical parity
sample. `--split parity` will be added when a parity subset is agreed.

## Comparison with Original Benchmark (Parity)

**Agent parity has not run.** No `parity_experiment.json` is supplied because no
agent/model experiment results exist. The maintainer has approved the benchmark;
agent/model/run-count/budget coordination is still pending.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| Pending team selection | Pending | pass@1 | Not run | Pending | Not measured | Not measured |

Reproduce local scoring comparisons (no model calls and no Modal):

```bash
uv run python scripts/validate_real.py \
  --upstream-root /tmp/de-bench-upstream --dataset /tmp/de-bench-smoke \
  --output /tmp/de-bench-scoring-comparison.json
DE_BENCH_ROOT=/tmp/de-bench-upstream uv run python -m unittest discover -s tests -v
```

The original `_score_trial` body was also executed locally in offline Docker:
62 reference solutions passed, 62 delivered baselines failed, and all 62 oracle
check maps matched Harbor. This excludes the Modal platform and runtime image.

The comparison script uses the exact upstream `_solution_patch` function and
`score_workspace` directly, then independently runs the generated verifier. It
compares every check for untouched, delivered-baseline, oracle, and reverted-oracle
states. The last state is an explicit reversion to baseline plus delivery marker,
not an independent mutation-fuzzing campaign. Agent changes are committed before
verifying to exercise commit-independent capture. See `validation/` for evidence.

For the upstream Modal harness, after installing/configuring de-bench, run:

```bash
de-bench prove --world upgrade-v2 --tasks \
  task-upgrade-v2-a1b2c3 task-upgrade-v2-23f2a0 task-upgrade-v2-2c5f8a \
  task-upgrade-v2-cosme01 task-upgrade-v2-dgfh01
```

That Modal command has **not** been run in this implementation milestone. Local
scorer equality does not establish cloud harness or agent parity. Full parity
must follow the repository's paired sanity → one run per side → three runs per
side sequence, after the team approves configurations and resources.

## Notes & Caveats

- `scoring-smoke` omits Airflow, providers, Node and agent tools. It is sufficient
  for this pinned scorer's static checks, but unsuitable for agent parity.
- `upstream-runtime` retains Airflow 3.0.3 and uses a checked 331-package Python
  lock at `src/de_bench_upgrade/runtime/requirements.lock`. The original pip
  auxiliary install failed with `ResolutionTooDeep: 200000`; installing extras
  alone also left inconsistent protobuf/OpenTelemetry consumers. The adapter
  jointly resolved all original runtime roots with uv 0.13.9, retaining the
  Airflow pin, keeping dbt-core on 1.x, and including the already-installed
  Snowpark/Prometheus consumers in resolution. `requirements.in` documents the
  inputs; the final image installs the frozen result and requires `pip check`
  plus Airflow DB initialization to succeed.
- This is an explicit runtime adaptation, not proof of identity with the cached
  Modal image. Snowpark and OpenTelemetry components changed within their
  compatible requirement ranges. Apply the same package lock on both sides
  before agent parity; `/opt/runtime-packages.txt` records the installed set.
- The generated instruction concatenates the original world system prompt and
  ticket. Their text is retained, but Harbor and upstream assign different message
  roles by default. Message-role placement and agent startup flags must be aligned
  before parity. Upstream Codex also inserts a `---` separator, and its model
  resolver can silently map an unfamiliar model ID to a default; see
  `validation/README.md`. No claim of prompt-level equivalence is made yet.
- No live Airflow service is started, matching the current upstream system prompt.
  `boot_airflow` defaults true in the parser but does not start a service in the
  current trial implementation. All 62 tasks disable `live_env`.
- The runtime uses an official Python Debian image rather than a Modal image and
  installs verifier dependencies in a separate Python environment. Compare its
  package/tool manifest with Modal before agent experiments.
- Agent CLI installation/version/settings are not selected automatically. Upstream
  pins Codex 0.146.1 and Claude Code 2.1.224; the team must choose the parity config.
- No task checks, thresholds, prompts, or reference fixes were rewritten. No tasks
  are excluded from the pinned corpus. Updating the upstream pin requires a new
  inventory and validation, rather than silently accepting a newer tree.

## Installation / Prerequisites

Python 3.12+, uv, Git, Docker daemon access, and Harbor CLI. Initial installation
and container builds need internet access. Validation used Harbor 0.27.0. The lock
file records the package index used during installation; use a reachable mirror
if your environment cannot access that index.

## Troubleshooting

An upstream revision/dirty-check error means the input differs from the audited
source. Restore a clean checkout at the recorded commit. An infrastructure error
must be diagnosed separately from reward 0; inspect Harbor trial logs and
`verifier/result.json`. `test.sh` removes stale rewards before running, so a crashed
verifier cannot reuse an old success. Unsupported check/runtime features are
rejected by the generator and must be implemented before adding such tasks.

## Citation

Astronomer, [de-bench](https://github.com/astronomer/de-bench), upgrade-v2 world,
commit `5dcfc2b81b13dcf58cff49e192e97f1ae05f8dbc`, Apache-2.0.

```bibtex
@misc{astronomer_de_bench,
  author = {{Astronomer}},
  title = {de-bench},
  howpublished = {\url{https://github.com/astronomer/de-bench}},
  note = {upgrade-v2, revision 5dcfc2b81b13dcf58cff49e192e97f1ae05f8dbc}
}
```

## Authors & Contributions

Original benchmark and reference solutions: Astronomer / de-bench contributors.
Adapter contributor: Billy1900. This adapter reuses the original scorer with
attribution and includes its license in generated verification artifacts.
