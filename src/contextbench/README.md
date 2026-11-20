# ContextBench to Harbor Adapter

## Overview

This adapter converts rows of the ContextBench benchmark into Harbor tasks. Each
task gives an agent a repository issue and a checkout of the repository at the
issue's base commit. When the agent finishes, the verifier (Harbor's scoring
step) determines which repository files and lines the agent was shown and
compares them with the row's gold context, the files and line ranges that
ContextBench's annotators marked as needed to resolve the issue. The task reward
is final file coverage, the fraction of gold files that the agent was shown.

The adapter supports the four datasets that ContextBench publishes at commit
`1436c28a8eb95496da4ea69ad458b9f8a8eb7d61`, and scores with ContextBench's own
evaluator from that commit. The default dataset, `verified`, has 500 tasks from
four source benchmarks in eight languages. Harbor records each agent run as an
[ATIF](https://harborframework.com/docs/agents/trajectory) trajectory, its
standard trajectory format, and one attribution rule
([`ATTRIBUTION.md`](ATTRIBUTION.md)) turns any agent's ATIF trajectory into the
retrieved context that the evaluator scores.

## What is ContextBench?

[ContextBench](https://github.com/EuniAI/ContextBench)
([paper](https://arxiv.org/abs/2602.05892)) measures how well coding agents
retrieve repository context while they resolve issues. Its rows come from
SWE-bench Verified, Multi-SWE-bench, SWE-PolyBench and SWE-bench Pro. Each row
holds an issue, a repository and base commit, the reference patch and the gold
context. The `full` dataset has 1,136 rows and `verified` has 500, split into
`verified-train` (450) and `verified-test` (50).

The evaluator compares retrieved context with gold context by file, by symbol
(definitions that tree-sitter finds), by byte span and by line. It reports final
coverage and precision, two trajectory metrics, and edit localization. The
trajectory metrics are coverage averaged over the agent's retrieval steps (AUC)
and redundancy, the share of retrieved context that repeats earlier steps. Edit
localization is the share of base lines changed by the agent's patch that lie
inside the gold context. ContextBench's benchmark score sums the final and
edit-localization counts over tasks before dividing, and averages the trajectory
metrics over tasks. ContextBench runs OpenHands, mini-swe-agent, SWE-agent,
Agentless and Prometheus natively, each with its own extractor that turns the
framework's trajectories into retrieved context.

## Adapter Features

- Downloads each dataset from the pinned commit, checks its SHA-256, and
  validates every row before writing any task.
- Repairs documented upstream data defects from checked-in sources and records
  each repair in a generation report (see Notes & Caveats).
- Builds the agent image from the task image that the source benchmark
  publishes (the native image), so the repository's dependencies are already
  installed. The build replaces the image's Git history with a one-commit
  checkout of the base commit and removes the source benchmark's grading files.
- Pins every base image, the native image included, by its linux/amd64 digest
  from `src/contextbench/image-digests.json`, because the source benchmarks
  republish images under the same tags. `scripts/image_digests.py` refreshes
  the file.
- Runs the verifier in a separate image (`environment_mode = "separate"`) that
  holds the gold context, a clean checkout and the evaluator, none of which the
  agent can read. A collect step exports the agent's changes as a Git patch.
- Vendors ContextBench's evaluator byte for byte in `src/contextbench/vendor/`,
  with its Apache-2.0 license and a SHA-256 manifest.
- Writes `metric.py` next to the tasks to compute ContextBench's benchmark-level
  metrics for a job.

The adapter adds no custom agent, and its verifier can score any agent whose
run produces an ATIF trajectory. `tests/test_harbor_agents.py` checks the output of
Harbor 0.26.0's ATIF converter for each registered coding agent, except the
three that cannot run a repository task (`computer-1`, `nemo-agent`, `eve`).
The parity experiment used a small OpenHands subclass,
`parity/openhands_agent.py`, that passes the pinned configuration and AWS
credentials.

### Attribution

The attribution rule applies to every agent and credits two kinds of evidence.
A structured read is a call to a read tool whose path argument names a file in
the checkout; it earns that file and the lines it declares. A receipt is text in
a tool's output that matches the base checkout, such as numbered source lines,
`path:line:content` search output, a run of consecutive source lines, or a diff
hunk. Command text earns nothing and only supplies hints, such as the working
directory and the paths it names. The verifier records a classification and the
deciding rule for every tool call. [`ATTRIBUTION.md`](ATTRIBUTION.md) states the
rule in full, measures its differences from ContextBench's OpenHands extractor,
and keeps its version history. The current `attribution_version` is 6, and
scores from different versions are not comparable.

## Generated Task Structure

```text
datasets/contextbench/
├── contextbench-generation-report.json
├── metric.py
└── verified-<16 hex digits>/
    ├── task.toml
    ├── instruction.md
    ├── environment/
    │   └── Dockerfile
    ├── solution/       # solve.sh, oracle-trajectory.json, solution.patch
    └── tests/          # Dockerfile, test.sh, score.py, gold.json, attribution.json,
                        # harbor_contextbench/ (scorer, attribution, vendored evaluator)
```

A task directory is named after its dataset and the first 16 hex digits of the
SHA-256 of the ContextBench `instance_id`, and the task name adds the
`contextbench` organization, as in `contextbench/verified-0009c6d08b72220d`.
Names are stable across runs. They include the dataset because one instance can
have different content in different datasets.

| File | Contents |
| --- | --- |
| `contextbench-generation-report.json` | For each dataset: source file and SHA-256, row count, invalid rows, corrections applied, problem statements decoded from JSON, generated tasks. |
| `task.toml` | Task name, source metadata (instance IDs, repository, base commit, source benchmark, language, native image), timeouts, resources and the collect command. |
| `instruction.md` | The issue text and a request to make minimal changes to non-test files in `/workspace`. |
| `environment/Dockerfile` | The agent image. `/workspace` links to the native repository path (`/testbed`, `/app` or `/home/<repo>`). |
| `solution/` | The oracle solution, which Harbor's oracle agent runs instead of a model. `solve.sh` copies `oracle-trajectory.json`, one structured read per gold range, to the agent log directory and applies `solution.patch`, the reference patch. |
| `tests/Dockerfile` | The verifier image: Python 3.12, Git, every tree-sitter grammar ContextBench can use, a clean checkout of the base commit, and the scorer with the vendored evaluator. |
| `tests/gold.json`, `tests/attribution.json` | The gold context with raw upstream paths, and the paths at which the agent image mounts the repository. |
| `tests/test.sh`, `tests/score.py`, `tests/harbor_contextbench/` | The scorer, the adapter's attribution code, and ContextBench's evaluator under `vendor/`. |

## Run Evaluation / Harness

After the dataset is registered (see Notes & Caveats), the registry is the
main way to run it, and Harbor applies the dataset's
`metric.py` as the job metric:

```bash
uvx --from harbor==0.26.0 harbor run -d contextbench/contextbench -a <agent> -m "<model>"
```

To run from local paths, generate the tasks (see Usage) and, from
`src/contextbench`, run one of these:

```bash
# Oracle on every generated task, with ContextBench's benchmark metrics
uv run --extra harbor harbor run -c run_contextbench.yaml

# One agent on every generated task; reports only Harbor's mean reward
uv run --extra harbor harbor run -p datasets/contextbench -a <agent> -m "<model>"

# One task
uv run --extra harbor harbor trial start -p datasets/contextbench/<task> -a <agent> -m "<model>"
```

For a local dataset, only the `metrics` block in `run_contextbench.yaml` applies
`metric.py`. To run an agent with it, comment out the oracle in that file and
uncomment one of the example agents. The benchmark score differs from the mean
of task rewards because counts are summed before dividing, and because a trial
with no retrieved context gets a reward of 0.0 that `metric.py` leaves out of
the sums, as ContextBench does. `metric.py` also leaves out trials that have no
reward at all, such as a missing trajectory or a verifier timeout. Report
`contextbench_num_valid` and `contextbench_num_total` with the score, so that a
run with many such trials is not compared as if it were complete.

The reward measures recall only: an agent that prints every file in the
repository reaches 1.0. Report file precision alongside it, as ContextBench
does; `metric.py` computes both.

On the largest `verified` checkout (mui/material-ui, 43,287 files), with the
task's 2 CPUs and 4 GB, the verifier scored the longest parity trajectory in
11 seconds and a synthetic trajectory of 200 shell calls with 20,000-line
outputs in 104 seconds, against its 600-second timeout.

The verifier writes two files. `/logs/verifier/reward.json` holds the reward,
ContextBench's 18 per-task metrics and the counts that `metric.py` adds up.
`/logs/verifier/contextbench-metrics.json` holds the evaluator's result, the
projected context and one evidence record per tool call.

The oracle exercises both images, the collect step, attribution and the
evaluator, and it does not measure retrieval. Its expected reward is 1.0 on
every task except those whose gold context names files that no prediction can
match. `scripts/output/upstream-defects.json` lists them with each task's
maximum: 13 in `verified`, 3 in `verified-test`, 19 in `verified-train` and 88
in `full` (see Notes & Caveats).

### Oracle results

The oracle ran through Harbor 0.26.0 on every `verified` task and on a sample
of 26 `full` tasks that are not in `verified`: six from each source benchmark,
plus the two rows that the corrections file restores or replaces. Every reward
equals the expected value: 1.0, or the documented maximum listed in
[`scripts/output/upstream-defects.json`](scripts/output/upstream-defects.json).

| Dataset | Tasks run | Reward 1.0 | At the documented maximum | Other |
| --- | ---: | ---: | ---: | ---: |
| `verified` | 500 | 487 | 13 | 0 |
| `full`, sample | 26 | 24 | 2 | 0 |

The other 607 `full` tasks are generated and their images are pinned, but they
have not been built or run.

## Usage: Create Task Directories

From `src/contextbench`:

```bash
uv sync

# Default: the 500 verified tasks, written to datasets/contextbench
uv run contextbench

# The full dataset; the 3 rows that cannot be restored are skipped and reported
uv run contextbench --dataset full --skip-invalid-source-rows --output-dir datasets/contextbench-full

# The ten parity tasks
uv run contextbench --split parity --output-dir datasets/contextbench-parity
```

| Option | Effect |
| --- | --- |
| `--dataset {verified,verified-train,verified-test,full}` | Pinned dataset to download; the default is `verified`. Downloads are cached under `~/.cache/harbor/contextbench/`. |
| `--dataset-path PATH` | A local parquet file. A copy of a pinned file keeps its name; any other is labeled `custom-<first 8 hex digits of its SHA-256>`. |
| `--split {full,parity}` | `full`, the default, generates the selected dataset; `parity` generates the ten parity tasks from `verified-test`. |
| `--output-dir PATH` | The default is `datasets/contextbench`. |
| `--task-ids IDS` | Comma-separated ContextBench `instance_id` values, generated in the given order. |
| `--limit N` | Generate at most N tasks. |
| `--overwrite` | Replace existing task directories. Without it, generation stops before writing if a selected task exists. |
| `--skip-invalid-source-rows` | Generate the valid rows when the selection contains invalid rows. |

| Dataset | Rows | Tasks | SWE-bench Verified | Multi-SWE-bench | SWE-PolyBench | SWE-bench Pro |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `verified` | 500 | 500 | 174 | 156 | 116 | 54 |
| `verified-train` | 450 | 450 | 157 | 140 | 104 | 49 |
| `verified-test` | 50 | 50 | 17 | 16 | 12 | 5 |
| `full` | 1,136 | 1,133 | 313 | 458 | 219 | 143 |

The `verified` tasks cover 59 repositories. By language they are Python 266,
TypeScript 66, JavaScript 60, Go 40, C 23, Rust 20, Java 15 and C++ 10.

## Comparison with Original Benchmark (Parity)

The parity experiment ran OpenHands 1.2.1 with Claude Sonnet 4.5 on Bedrock
(`us.anthropic.claude-sonnet-4-5-20250929-v1:0`) on ten tasks, three times
through ContextBench's own harness and three times through Harbor. The tasks are
the first ten SWE-bench Verified rows of `verified-test` in file order, which
`--split parity` generates. Both sides shared the rendered prompt, SWE-bench
image, workspace path, OpenHands configuration (200 iterations, a 1,800-second
timeout, temperature 0) and serial execution, which
`parity/harness_experiment.json` pins. The trials ran on 2026-08-30 and
2026-08-31 from a Harbor checkout based on harbor-framework/harbor commit
`74cc6312` (Harbor 0.22.0), with an earlier revision of this adapter whose
verifier used attribution version 2. Each side completed three runs.
ContextBench's second run failed to start six times on infrastructure errors
before any agent step, the last three while building OpenHands's runtime image,
and its seventh start completed. No completed run was repeated or discarded. A
separate single run on 2026-08-21 used a superseded design and serves only as a
calibration corpus.

The metric is ContextBench's micro-averaged final file coverage, the number of
gold files found in the ten tasks divided by their 23 gold files. ContextBench's
side is scored by its own OpenHands extractor and evaluator. Harbor's scores
come from the rewards that the adapter's verifier recorded during the runs. The
current verifier (attribution version 6, Harbor 0.26.0) reproduces them exactly
from the published trajectories. Harbor's parity criterion requires the ranges
of run scores on the two sides to overlap. Scores are mean ± sample standard
error of the mean (SEM) over the three runs.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
| --- | --- | --- | ---: | --- | --- | --- |
| openhands@1.2.1 | bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0 | Micro-averaged final file coverage | 3 | 10 (2% of 500) | 0.811594 ± 0.028986 | 0.768116 ± 0.028986 |

ContextBench's runs scored 0.782609, 0.782609 and 0.869565 (18, 18 and 20 of 23
gold files), and Harbor's scored 0.826087, 0.739130 and 0.739130 (19, 17 and
17). The ranges overlap, so the parity criterion holds. The three run pairs cost
$834.24.

- Original benchmark, used without a fork (the runner adds two pinned OpenHands
  compatibility files at run time; see [`parity/README.md`](parity/README.md)):
  <https://github.com/EuniAI/ContextBench/tree/1436c28a8eb95496da4ea69ad458b9f8a8eb7d61>
- Parity artifacts:
  <https://huggingface.co/datasets/harborframework/parity-experiments/discussions/269>
- Adapter PR: <https://github.com/harbor-framework/harbor/pull/3129>
- Dataset PR: none yet (see Known limitations).

The experiment covers less than the adapter does. To hold the agent's inputs
constant, `parity/prepare.py` replaces each task's instruction, image and
working directory, so the experiment does not test the default task image or
instruction. The experiment covers only ContextBench's SWE-bench Verified
runner.

### Scoring both sides with both extractors

`parity/run_harness_parity.sh rescore` scores the published trajectories of
both sides again, without calling a model, under ContextBench's OpenHands
extractor (the upstream extractor) and under the attribution rule. The rule
reads ContextBench's histories as converted to ATIF by Harbor, and the extractor
reads Harbor's raw OpenHands logs. All eight final metrics, mean ± SEM:

| Metric | ContextBench, upstream extractor | ContextBench, rule | Harbor, upstream extractor | Harbor, rule |
| --- | --- | --- | --- | --- |
| File coverage | 0.811594 ± 0.028986 | 0.811594 ± 0.028986 | 0.768116 ± 0.028986 | 0.768116 ± 0.028986 |
| File precision | 0.401190 ± 0.015476 | 0.381221 ± 0.005087 | 0.341880 ± 0.011897 | 0.322308 ± 0.017441 |
| Line coverage | 0.444265 ± 0.036028 | 0.440849 ± 0.041165 | 0.386911 ± 0.022590 | 0.418015 ± 0.018858 |
| Line precision | 0.176533 ± 0.016150 | 0.165917 ± 0.016942 | 0.152857 ± 0.014344 | 0.154227 ± 0.008220 |
| Span coverage | 0.433495 ± 0.038345 | 0.433486 ± 0.043674 | 0.376373 ± 0.027709 | 0.411463 ± 0.017430 |
| Span precision | 0.184495 ± 0.017288 | 0.165245 ± 0.019872 | 0.162361 ± 0.014407 | 0.159826 ± 0.006040 |
| Symbol coverage | 0.505952 ± 0.012973 | 0.523810 ± 0.011905 | 0.449405 ± 0.011905 | 0.497024 ± 0.010731 |
| Symbol precision | 0.159893 ± 0.001750 | 0.127726 ± 0.002803 | 0.143956 ± 0.007853 | 0.120972 ± 0.000993 |

File coverage is the same under both extractors, run by run, so the difference
between the two sides comes from the agent runs. Only file coverage gates
parity. For the parity pair (ContextBench with the upstream extractor, Harbor
with the rule), the run ranges of file precision and symbol precision are
disjoint. Under the upstream extractor on both sides, the run ranges of file
precision and symbol coverage are disjoint. All other ranges overlap.

### Calibration

ContextBench's pinned OpenHands extractor is the reference against which the
rule is checked. `parity/calibrate.py` fetches published trajectories, projects
them with both, and compares the totals with the pinned summaries in
`parity/calibration-summary*.json`. Each pair below is rule / extractor.

| Corpus | Gold files | Gold files found | Predicted files | Spans | Lines | Trajectories with the same predicted files |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Harbor side of the parity runs (30 trajectories) | 69 | 53 / 53 | 165 / 155 | 631 / 218 | 15,105 / 14,364 | 22 of 30 |
| Earlier single run on the same tasks (10 trajectories, 2026-08-21) | 23 | 19 / 20 | 53 / 55 | 186 / 73 | 4,942 / 4,965 | 8 of 10 |

The rule credits what an output displayed, and the extractor credits what a
call requested. The rule therefore credits files shown by recursive searches and
tracebacks, which the extractor ignores, and records more, narrower spans. The
extractor credits single-file searches whose output was empty, and the rule does
not.

### Reproduction

[`parity/README.md`](parity/README.md) gives the prerequisites, including
ContextBench's OpenHands environment. From `src/contextbench`:

```bash
uv sync --extra harbor --group dev
CB=/tmp/contextbench                  # ContextBench at 1436c28a8eb9
OUT=/path/to/contextbench-parity
export AWS_PROFILE=my-profile

parity/run_harness_parity.sh prepare "$CB" "$OUT"
parity/run_harness_parity.sh preflight "$CB" "$OUT"
for run in 1 2 3; do
  parity/run_harness_parity.sh original "$CB" "$OUT" "$run"  # ContextBench side
  parity/run_harness_parity.sh harbor "$CB" "$OUT" "$run"    # Harbor side
done
parity/run_harness_parity.sh report "$CB" "$OUT"

# Score retained trajectories (a finished work directory or the published
# bundle's adapters/contextbench directory) with the current verifier
parity/run_harness_parity.sh rescore "$CB" "$OUT" "$RETAINED"
```

### Runs with other agents

These runs check that other agents work with the adapter. They are not parity
runs. Claude Code 2.1.328 and mini-swe-agent 2.4.6 ran Claude Sonnet 5.5 on
Bedrock (`us.anthropic.claude-sonnet-5-5`) with Harbor 0.26.0, on 8
`verified-test` tasks (two from each source benchmark), with one attempt each.
The rewards are the ones the verifier recorded during the runs, at attribution
version 6.

| Agent | Trials with a reward | Mean file coverage | Benchmark file coverage (`metric.py`) | Tool calls | Credited calls | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| claude-code@2.1.328 | 8 of 8 | 0.703 | 0.529 | 33 | 24 | $0.49 |
| mini-swe-agent@2.4.6 | 8 of 8 | 0.712 | 0.559 | 86 | 46 | $1.02 |

Both agents read the repository only through shell commands, so all of their
credit came from receipts; structured reads are exercised by the OpenHands
parity trajectories. Ten of mini-swe-agent's calls are `malformed` because of
a Harbor converter defect (see Known limitations); the files they showed were
credited by other calls.

## Notes & Caveats

### Upstream data defects

[`scripts/output/upstream-defects.json`](scripts/output/upstream-defects.json)
lists every affected row, and
[`src/contextbench/corrections.json`](src/contextbench/corrections.json) holds
each corrected value with its source and revision.

| Defect | `verified` | `full` | Handling |
| --- | ---: | ---: | --- |
| Empty gold context | 0 | 3 rows | Cannot be restored, because only ContextBench has its annotations. Generation stops unless `--skip-invalid-source-rows` is passed. |
| Empty problem statement | 0 | 1 row | Restored from SWE-bench Pro v1, which has the same base commit and patch. |
| Problem statement for a different change than the gold patch | 1 row | 2 rows | Replaced with the SWE-bench Pro V2 statement. The rows are the NodeBB instance whose ID ends in `ac8400d9` and, in `full` only, the vuls instance ending in `2cef67df`. |
| Problem statement stored as a JSON string literal | 29 rows | 67 rows | Decoded, except for the NodeBB row, which is replaced. |
| `repo` column cut at the first hyphen (`fasterxml/jackson` for `fasterxml/jackson-core`) | 34 rows | 88 rows | Ignored. The repository comes from `repo_url` or `original_inst_id`, and a row where they disagree is rejected. |
| Gold files that no prediction can match | 13 tasks | 88 tasks | Kept, as in native scoring, so these tasks cannot reach a reward of 1.0. |
| Gold ranges that end past the end of the file | 72 rows | 357 rows | The verifier clamps declared read ranges to the file, so the oracle's reads are credited. |

Gold files fail to match for two reasons. ContextBench's gold parser removes
leading `.` characters from repository-relative paths, so `.github/x.yml` is
scored as `github/x.yml`. Other gold files are scripts that the annotator wrote,
which do not exist at the base commit. In `verified`, 10 files are of the first
kind and 8 of the second. Separately, 16 `verified-test` rows and 140
`verified-train` rows differ from the same instance in `verified`, 100 of them
in gold context. Each dataset keeps its own content.

### Native image edits

In 104 of the 500 `verified` tasks the native image's build edits or deletes
tracked files (18 SWE-bench Verified, 15 Multi-SWE-bench, 70 SWE-PolyBench and
1 SWE-bench Pro image, listed in
[`scripts/output/native-image-edits-verified.json`](scripts/output/native-image-edits-verified.json)).
The agent image keeps these edits, as native agents see them, and records the
resulting tree as the baseline of the model patch, so the patch holds only the
agent's changes. Git in the agent image ignores file modes, so the mode changes
in 33 SWE-bench Verified images do not show as edits.

SWE-PolyBench images also leave their build `Dockerfile` untracked in
`/testbed`. ContextBench's OpenHands runner exports patches with `git add -A`,
so its patches add that file, which changes no metric; the adapter's patches
leave it out. In 8 `verified` tasks the repository tracks a root `Dockerfile`
that the image overwrote. There upstream's patch shows `Dockerfile` edits that
lower edit-localization precision, and the adapter's patch does not.

### Other differences from native ContextBench

- One attribution rule replaces the per-framework extractors (measured on
  OpenHands trajectories in the parity section).
- A trial with no retrieved context gets a reward of 0.0 and
  `status: no_context_extracted`. ContextBench's evaluator returns an error for
  such a row and leaves it out of its averages, and `metric.py` does the same.
- An empty model patch is replaced with a placeholder, so a trial without edits
  scores 0 for edit localization. ContextBench's evaluator would otherwise score
  the gold patch.
- A trial whose patch collection failed keeps its context scores but has no
  edit localization (`contextbench_editloc_present` is 0), and `metric.py`
  leaves it out of the edit-localization sums.
- Multi-SWE-bench agent images lose their grading files (`fix.patch`,
  `test.patch` and the run scripts), and every agent image loses its native Git
  history.

### Earlier published Harbor scores

An offline rescore published in September 2026 reported Harbor runs of
0.869565, 0.826087 and 0.826087 for the same trajectories. On one task it
credited five gold-file matches across the three runs (one in the first, two
in each of the others) from blank lines in the diff of an older commit, which
the attribution rule has not credited since version 5. The parity figures
above replace it.

### Known limitations

- Harbor 0.26.0's OpenHands converter gives every call in a multi-call model
  response the first call's arguments, so a parallel batch of structured reads
  would credit the first file to every read. None of the 60 OpenHands logs kept
  from the parity runs has such a response.
- Harbor 0.26.0's mini-swe-agent converter drops `source_call_id` from tool
  results and appends format-error messages as extra results. When a step has
  more results than calls, the rule cannot pair them, so it marks the step's
  calls `malformed` and credits nothing for them.
- Receipts are conservative. Transformed source, such as reflowed text, earns
  nothing, and so does a single unnumbered source line. Tools without an
  attribution contract, such as Claude Code's `Monitor` and `Workflow`, are
  `unmapped`.
- Program output that happens to equal a unique run of checked-in source is
  credited as if the agent had read that source. Runs in files that the command
  did not name need three non-blank lines, which limits such chance matches.
- The dataset is not registered yet. Registration waits for the Harbor team's
  decision on parity coverage.

## Installation / Prerequisites

- Docker that can run `linux/amd64` images. The native images are published
  only for that platform, and the generated Dockerfiles pin every base image to
  its linux/amd64 digest. Docker Desktop emulates them on Apple Silicon; the
  adapter has been run only on x86-64 Linux hosts, so timeouts under emulation
  are untested.
- Python 3.12 or newer, and [uv](https://docs.astral.sh/uv/).
- Harbor 0.26.0. From `src/contextbench`, `uv sync` installs what task
  generation needs, and `uv sync --extra harbor` adds Harbor.
- Network access to GitHub, Docker Hub and GHCR when images are built. The
  verifier image downloads its tree-sitter grammars at build time and scores
  without network access.
- Credentials for the model of any agent other than the oracle.

## Troubleshooting

- If generation reports invalid rows, the message names each one. For `full`,
  the 3 rows with empty gold context are expected, and
  `--skip-invalid-source-rows` generates the others.
- If generation reports that `image-digests.json` has no digest for an image,
  run `uv run python scripts/image_digests.py`, with `--dataset-path` for a
  local parquet.
- If a trial has no reward, the `status` in `contextbench-metrics.json` is
  `input_error` for a missing or unusable trajectory, and
  `infrastructure_error` for a fault in the task or the verifier.
- If `patch_collection.status` in `contextbench-metrics.json` is `failed`, the
  trial was scored without edit localization. Its `reason` is
  `collect_incomplete` if the collect step did not finish, for example at its
  timeout, `git_state_invalid` if the agent damaged the Git metadata, and
  `model_patch_missing` or `collection_status_missing` if an artifact did not
  arrive.
- A reward of 0.0 with `status: no_context_extracted` means that no tool call
  validated against the checkout. The `evidence` records give each call's
  classification and reason.
- An oracle reward below 1.0 is expected only for the tasks that
  `upstream-defects.json` lists under `unmatchable_gold_files` for that
  dataset, at the maximum it gives. Anywhere else it is a bug.

## Citation

```bibtex
@misc{li2026contextbenchbenchmarkcontextretrieval,
  title={ContextBench: A Benchmark for Context Retrieval in Coding Agents},
  author={Han Li and Letian Zhu and Bohan Zhang and Rili Feng and
          Jiaming Wang and Yue Pan and Earl T. Barr and Federica Sarro and
          Zhaoyang Chu and He Ye},
  year={2026},
  eprint={2602.05892},
  archivePrefix={arXiv},
  primaryClass={cs.LG},
  url={https://arxiv.org/abs/2602.05892}
}
```

## Authors & Contributions

[Jonathan Buck](mailto:jonathan.j.buck@gmail.com) built the Harbor adapter. The
ContextBench dataset, annotations and evaluator are the work of the benchmark's
authors, cited above.
