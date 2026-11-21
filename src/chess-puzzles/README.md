# Chess Puzzles → Harbor Adapter

## Overview

Converts all 100 Epoch AI Chess Puzzles into Harbor tasks with a separate verifier.
The original-prompt variant runs
the pinned upstream `qa_agent` through a Harbor custom agent. Real-model parity
is pending; offline simulations are not model performance results.

Source: [epoch-research/chess-puzzles-mirror](https://github.com/epoch-research/chess-puzzles-mirror/tree/2c9416aac2a6b0731a3680eadfff3735fdaad396),
pinned to public benchmark **2.0.1**, commit
`2c9416aac2a6b0731a3680eadfff3735fdaad396`. The CSV is verified with SHA-256
before generation. No puzzles are excluded.

## What is Chess Puzzles?

Each puzzle supplies a FEN position and asks for the single best next move.
The public upstream task uses Inspect's `qa_agent`, whose only tool is
`submit_answer`, and scores accuracy with Inspect `exact()`. Released gold moves
are in the upstream CSV's `target` column.

## Adapter Features

- Standard-library task generation and verifier; no chess engine or GPU needed.
- Stable IDs `chess-puzzles-001` through `chess-puzzles-100` in CSV row order.
- Original question plus a clearly disclosed answer-file handoff.
- `--variant original` retains the upstream question verbatim and uses the
  upstream `submit_answer` tool; `--variant cli` keeps the file-answer handoff.
- `EpochChessAgent` runs Inspect in a separate host process, then writes the
  submitted answer into the Docker task. Harbor collects `/app/answer.txt` and
  grades it in a fresh container built from `tests/Dockerfile`.
- `--split parity` defaults to the original-prompt variant; the full split defaults
  to CLI. An explicit `--variant` overrides either default.
- The original variant uses registry names `epoch-ai/chess-puzzles-original__chess-puzzles-NNN`;
  CLI names remain `epoch-ai/chess-puzzles__chess-puzzles-NNN`. Directory names stay the same.
- `--split parity` selects rows 4, 14, 15, 18, 29, 32, 36, 82, 87 and 95,
  sampled with `sorted(random.Random(42).sample(range(1, 101), 10))` before runs.
- Lightweight Inspect 0.3.273 exact normalization, retaining its full MIT notice.
- Oracle writes released gold; targets stay in `tests/` and `solution/`, outside
  the agent image build context. The verifier image includes the grader and gold.
- Temporary task staging, overwrite protection and rejection of stale selections.

## Generated Task Structure

```text
datasets/chess-puzzles/
├── chess-puzzles-001/
│   ├── instruction.md
│   ├── task.toml
│   ├── environment/Dockerfile
│   ├── solution/solve.sh
│   └── tests/
│       ├── Dockerfile
│       ├── test.sh
│       ├── grade.py
│       ├── scoring.py
│       └── record.json
├── ...
└── generation_manifest.json
```

Adapter code belongs at `src/chess-puzzles/` in the adapters repository.
Generated datasets, caches and full job logs are ignored and published separately.

## Run Evaluation / Harness

Registry publication is pending; use local paths for this WIP. All commands below
run from the adapter package directory (`src/chess-puzzles/`). Harbor is an external
dependency; `uvx` selects the recorded runtime without changing a global install.

```bash
# Single-task oracle
uvx --from harbor==0.27.0 harbor run -p datasets/chess-puzzles-separate/chess-puzzles-001 -a oracle

# Full 100-task oracle (YAML selects oracle and four concurrent trials)
uvx --from harbor==0.27.0 harbor run -c run_chess-puzzles.yaml
```

No model API key is needed for oracle. Its expected result is 100 trials, zero
exceptions and mean reward 1.000. Results are saved under the printed `jobs/` path.

## Usage: Create Task Directories

```bash
cd src/chess-puzzles
uv sync --locked --no-editable
uv run --locked --no-editable chess-puzzles --output-dir datasets/chess-puzzles-separate
```

`--output-dir` defaults to `datasets/chess-puzzles-separate` relative to the working directory.
Other flags: `--limit`, `--task-ids` (e.g. `7` or `chess-puzzles-007`), `--overwrite`,
`--data-path` for a verified offline CSV, and `--cache-dir`. Use a fresh output
directory when changing the selected task set. Answers are downloaded and inserted
into the oracle scripts during generation, not hardcoded in the source template.

Tasks generated before the separate-verifier migration must be regenerated. The
commands above and reference YAML use a new `datasets/chess-puzzles-separate`
directory to preserve earlier tasks and logs. The generator default and reference YAML now both use
`datasets/chess-puzzles-separate`. Do not reuse the old 0.25/shared-verifier job as evidence
for the new layout.

Both task variants declare `artifacts = ["/app/answer.txt"]` and
`verifier.environment_mode = "separate"`. Only that file is declared as a submission;
the grader reads it at the same absolute path in its fresh container. Harbor also
collects its conventional `/logs/artifacts` directory, which this grader does not
read. Verifier scripts and gold data are bundled at image build time, rather than
uploaded into the agent environment. The verifier uses the same Python base image
and unchanged standard-library scoring code. No model credentials are needed.
Verifier networking follows Harbor's default: the grader makes no network requests,
but no runtime network blockade is claimed. This avoids the extra network-control
sidecar and kernel-probe requirements of `network_mode = "no-network"`. The original
agent container's Compose `network_mode: none` is unchanged.

## Comparison with Original Benchmark (Parity)

| Agent | Model | Metric | Number of Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|---|---|---|---|---|---|---|
| Pending | Pending | accuracy | 0 | 100 | Not run | Not run |

`parity_experiment.json` is intentionally empty. Both sides use the same verified
2.0.1 source snapshot, Inspect version, endpoint and model settings. Original-side
evaluation uses the upstream CSV and scorer. Harbor-side evaluation gives the solver
only the position, disables host-side scoring and checks its submitted answer in
Docker. CLI-agent results remain separate.

The original-side entry point is a wrapper around upstream `chess_puzzles()`, not
an unmodified `inspect eval` command. Both sides explicitly set the same response
cap, cumulative solver budget, compaction threshold and Inspect time limit. Both
use two SDK HTTP retries, zero outer Inspect retries and zero sample/trial retries.
The zero-retry setting is applied to the model instance as well as `eval_async`:
Inspect's `count_tokens()` and native compaction read the instance configuration;
setting only the evaluation override leaves their retry loop unbounded.
These wrapper settings are recorded with source, task and dependency fingerprints.
Any reduced solver budget must be disclosed against upstream's published 1M setting.

The supplied profiles explicitly select `"token_count_mode": "local"`. This is a
shared compatibility change on **both** sides, not an unmodified upstream run:
PPAPI's counting endpoints returned 503 in the interface checks, while ordinary
generation succeeded. `provider` mode remains available; a 503 never silently
changes the counting mode. Missing mode fields in older profiles retain `provider`.

Local mode uses `tiktoken==0.14.0`, `o200k_base`, on the pinned Anthropic provider's
count-time message representation, including roles and function-call arguments,
serialized as compact JSON. It returns `ceil(tokens * 1.1)` (algorithm
`anthropic-json-o200k-1.1-v1`). The 10% buffer is a heuristic, **not** a measured
error bound or a guarantee of overcounting Haiku. Readable thinking is counted as
text; opaque signatures/redacted thinking are omitted following the pinned
provider's own counting normalization. They are not removed from generation.
Only text/reasoning/tool-call inputs are supported; other content is rejected.

Inspect's existing compaction logic still uses actual input usage (including cache
reads/writes) as the baseline after each response and estimates newly added messages.
The upstream solver's output budget still uses actual `usage.output_tokens`.
Counting never replaces usage or billing data. `token-counts.jsonl` records estimates,
sample IDs and omitted opaque-block counts without text, signatures or credentials;
`outcome.json` records the mode and compaction events. Native Inspect logs retain
the actual usage and conversation. A changed mode/algorithm requires a new experiment
directory. Agreement here establishes parity under this shared compatibility setup,
not equivalence to the original provider counter. Review compaction events before
interpreting model scores; remote-versus-local count accuracy is still unmeasured.
Inspect has a second counter for diagnostic `reasoning_tokens` when the API does
not provide a thinking-token breakdown. The same instance's SDK counting method
also estimates that value locally, with `purpose: reasoning_usage_estimate` in the
audit. It never changes the API-reported total input/output/cache usage or solver
budget. Native thinking-token details, when supplied, remain untouched.

Individual `estimated_tokens` audit rows can count only a new message segment, or
serve the diagnostic thinking counter; they are not necessarily the full input
used for a compaction decision. Do not compare their maximum directly with the
200k threshold or divide them by the next response's input usage as an error rate.
That comparison needs aligned message scopes, system/tool overhead and cache
read/write usage. Inspect compaction events and the complete generation traces
during sanity; absence of compaction is an observation, not a guaranteed bound.

```bash
uv sync --locked --extra runtime --no-editable --reinstall-package harbor-chess-puzzles-adapter
# Create a local settings file only if one does not already exist.
cp -n parity_settings.json parity_settings.local.json
# Set budgets and source_dir in parity_settings.local.json, never put a key there.
# Downloads/verifies upstream source and creates the ten original-prompt tasks.
uv run --locked --extra runtime --no-editable chess-puzzles-parity --settings parity_settings.local.json prepare
# Optional authenticated model-list lookup, with a hidden key prompt; no inference.
uv run --locked --extra runtime --no-editable chess-puzzles-parity --settings parity_settings.local.json models
# Small paid interface check; no benchmark scores (64/256/256 output caps).
# Omitting --execute only prints the plan; failure stops before later requests.
uv run --locked --extra runtime --no-editable chess-puzzles-parity --settings parity_settings.local.json probe --execute

# Before running: fill the three token limits and timeout in parity_settings.local.json.
# These commands prompt for the key if ANTHROPIC_API_KEY is not set.
uv run --locked --extra runtime --no-editable chess-puzzles-parity --settings parity_settings.local.json run-pair --phase sanity --execute
uv run --locked --extra runtime --no-editable chess-puzzles-parity --settings parity_settings.local.json run-pair --phase formal --round 1 --execute
# Inspect both sides' logs before continuing with rounds 2 and 3.
uv run --locked --extra runtime --no-editable chess-puzzles-parity --settings parity_settings.local.json run-pair --phase formal --round 2 --execute
uv run --locked --extra runtime --no-editable chess-puzzles-parity --settings parity_settings.local.json run-pair --phase formal --round 3 --execute
uv run --locked --extra runtime --no-editable chess-puzzles-parity --settings parity_settings.local.json report
```

The `probe` action tests the selected counting mode, one automatic-tool streaming request and
explicit forced-tool requests in non-streaming and streaming modes. It sends three
fresh diagnostic conversations through the pinned Inspect Anthropic provider with
SDK retries disabled. The requested output caps total 576 tokens; this is not a
guarantee about provider billing. Probe logs are separate from parity and do not
establish multi-turn thinking or compaction compatibility. No key is saved.
With local mode, a passed counting check is explicitly a **local estimate**;
the report lists the provider counting endpoint as untested, not working.

For a visible upstream checkout beside this repository, check out commit
`2c9416aac2a6b0731a3680eadfff3735fdaad396` in `chess-puzzles-upstream` and set
`source_dir` in a git-ignored `parity_settings.local.json` to that checkout. The examples above all pass
`--settings parity_settings.local.json`; the tracked JSON stays a template. Both sides
verify and import that same snapshot; they share this package's locked environment.
There is no need to install the upstream package into a second environment.

The local starter profile uses a 32,000 response cap, 64,000 cumulative solver
budget, 200,000 compaction threshold and 7,200-second Inspect limit. It is a reduced
budget experiment relative to Epoch's 1M setting. Because budget is checked after
responses, allow for roughly 64k + 32k + 16k output tokens per attempt without
compaction or retries. Check real logs rather than assuming compaction never fires.

The pair runner executes original Inspect first, then Harbor Docker, using one
attempt per selected puzzle and concurrency 1. It records separate phase/round
folders, rejects configuration drift, and requires each preceding pair to finish
before starting the next. `prepare` and `run-pair` use the same `--output-dir`
(default `datasets/chess-puzzles-parity-separate`); existing tasks are checked for
the new manifest, separate mode, answer artifact, default verifier networking, and build definition
before use. The default experiment directory is `jobs/chess-puzzles-separate-parity`.
Five sanity tasks run once per side;
the ten formal tasks run three times per side (10 + 60 attempts). Raw Inspect logs,
Harbor trial logs, usage and per-puzzle scores are retained under `jobs/`.
`report` calculates accuracy and sample SEM across three run accuracies, and lists
each puzzle's scores and the puzzles only one side answered correctly in each round.
It refuses incomplete or simulated results and does not automatically declare parity.
An all-zero result or overlapping ranges alone is not evidence of a faithful adapter.
Usage records retain uncached input, cache reads, cache writes and output separately;
missing prices remain unknown instead of being replaced by a guessed cost.

Inspect owns the per-puzzle time limit on both sides. Harbor's outer limit adds
300 seconds for worker startup and cleanup. An Inspect cutoff is recorded with
`sample.limit`, a null reward and an incomplete round, never counted as a wrong
chess answer. The upstream token-budget fallback to `submit_answer` remains a valid
attempt and is still scored normally.

Empty or cancelled key input creates no attempt directory. If a run fails later,
`failure.json` records its stage and all native logs remain. After diagnosing a
transient infrastructure failure, explicitly repeat that incomplete pair with:

```bash
uv run --locked --extra runtime --no-editable chess-puzzles-parity --settings parity_settings.local.json run-pair \
  --phase formal --round 2 --execute --retry-failed \
  --retry-reason "Confirmed temporary provider outage; retrying both sides"
```

This archives the failed pair under `failed-attempts/`, retains completed earlier
rounds and reruns both sides of the failed round. It can incur additional API cost.
Completed rounds cannot be replaced to improve scores. Code or settings changes
require a new experiment directory; do not mix old and new runs. A forcibly killed
process may leave no `failure.json`; inspect that attempt before any manual recovery.

Coordinate model, settings, task selection and budget with the Harbor team before
paid runs. Follow the symmetric 5–10-task pilot, full-run and repeated-run sequence.
At least two runs per side (three preferred), sample SEM and overlapping run-score
ranges are required. Oracle success does not establish parity.

## Notes & Caveats

Validation on 2026-11-21, using **Harbor 0.27.0**, local Docker Desktop and the
unmodified `python:3.12-slim-bookworm` base image: **100/100 CLI oracle**,
**0 exceptions**, **0 retries**, mean **1.000**. Puzzle `chess-puzzles-004`
also passed six controls across original and CLI variants: gold **1**,
known-wrong **0**, missing answer **0**. Controls check that grader/gold are absent
during the agent phase and that agent-written grading files and an unrelated
workspace file do not carry into the separate verifier. The full run uses
unmodified generated solutions and graders. See the [screenshot](validation/oracle-2026-11-21.jpg),
[oracle evidence](validation/harbor-027-oracle-2026-11-21.json) and
[validation record](validation/harbor-027-review-2026-11-21.json).

**82 unit tests passed**. Harbor lint found no issues in 101 generated tasks.
Six scenarios through the real Anthropic provider against a loopback fake passed:
submission, continuation, forced answer, compaction, API error and timeout.
Requests matched across sides and remote count calls remained zero. These are
offline validations, with no real-model parity claimed. The adapter validator
retains one error and two warnings for the empty parity array and unknown costs.

The earlier separate-verifier run on **Harbor 0.26.0** (2026-11-20) also passed
100/100 oracle; its [historical evidence](validation/separate-verifier-oracle-2026-11-20.json)
is retained separately. The current run uses 0.27.0 and default verifier networking.

Historical shared-verifier oracle on 2026-11-16: **100/100**, **0 exceptions**, **0 retries**, mean
reward **1.000**, approximately **2m47s**, using Harbor 0.25.0 and Docker Desktop
on macOS with the unmodified `python:3.12-slim-bookworm` task image.
See [screenshot](validation/oracle-2026-11-16.png) and
[summary with task checksums](validation/oracle-summary.json).

- The default CLI instruction appends `/app/answer.txt` submission and closed-book constraints.
  These tool restrictions are instructional; no engine-access enforcement is claimed.
- Scoring follows 2.0.1 normalized exact matching, not raw UCI equality or 2.1.0
  SAN parsing. Case, punctuation, whitespace and articles follow pinned Inspect.
- The default 1,800-second Inspect limit is an infrastructure limit, not the
  original token budget or continuation policy. Harbor allows 300 seconds more.
- No upstream LICENSE is present at the selected snapshot. Resolve source/data
  reuse permission before dataset publication. Upstream data is downloaded at
  generation time, not committed in this adapter package.
- No real-model runs, registry publication or completed parity are claimed.
  The full submission validator therefore retains missing-parity findings.
- For Haiku 5.5, the current configuration omits `reasoning_effort`, retaining
  the fixed model's native default thinking. This is not thinking-disabled.
  Inspect 0.3.273 drops forced tool choice when explicit `reasoning_effort` is
  set; the runner rejects that combination until a symmetric provider fix is
  verified. Offline request tests cover the default and forced tool requests.
- Anthropic SDK 1.x is required: SDK 2.x changes `MessageParam` into a union that
  cannot be constructed by this Inspect version. `uv.lock` pins the tested SDK.
- Token limits remain unset pending the actual run configuration. The upstream
  cumulative token budget is checked after responses and permits a final
  16,000-token submission request; it is not a strict billing cap.
- The documented parity endpoint is `https://app.ppapi.ai` (Anthropic, no `/v1`
  suffix), from [Parity API Instructions](../parity_api_instructions.md).
  Minimal real calls confirmed Haiku generation/tool submission, but the separate
  counting endpoint returned 503. These interface probes are not real puzzle parity.
- Haiku 5.5's [official migration guide](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide)
  explicitly supports forced tool calls. Do not change upstream's forced submission
  to `auto` merely by analogy with other Claude models.
- The same guide says Haiku thinking blocks are bound to their conversation prefix.
  Inspect 0.3.273's binding workaround does not cover this Haiku model. Real
  compaction compatibility is still unverified: simulated summaries verify control
  flow, not provider signature validation. Resolve any incompatibility symmetrically
  before formal runs; retain the upstream solver and document provider changes.
- Before sanity runs, the actual proxy needs a compatibility check covering
  `x-api-key` authentication, the selected counting mode, streaming and forced
  submission. A successful Bearer-authenticated model listing is not sufficient.
  A normal single-puzzle run may submit early, so it does not guarantee that forced
  submission or compaction was exercised. Do not describe such a probe as full
  coverage or give it a guaranteed small cost.
- Local counting is an explicit experiment deviation shared by both wrappers.
  The 2.0.1 source snapshot, prompts, scorer and output-budget logic are unchanged.
  A large compaction threshold does not prove compaction cannot occur. Local counts
  and model-reported usage need not agree, especially for opaque thinking content.

## Installation / Prerequisites

Python 3.13+, uv, and Docker Desktop running. The generator has no third-party
runtime dependencies. Install the optional `runtime` extra for custom-agent/parity
evaluation; all versions are recorded in `uv.lock`.
First generation and container-image download require network access. A GPU,
Stockfish and model credentials are unnecessary for oracle.

```bash
# After `chess-puzzles-parity prepare`, run tests using its verified source cache.
# Reinstall after editing source when using --no-editable.
uv sync --locked --extra runtime --no-editable --reinstall-package harbor-chess-puzzles-adapter
# Cache the public vocabulary before tests deliberately block network requests.
uv run --locked --extra runtime --no-editable python -c 'import tiktoken; tiktoken.get_encoding("o200k_base")'
CHESS_PUZZLES_CSV=.cache/chess-puzzles/2c9416aac2a6b0731a3680eadfff3735fdaad396/bench/task/chess_puzzles/puzzles.csv \
  uv run --locked --extra runtime --no-editable pytest -q

# End-to-end original/Harbor simulations; Docker, no API credentials.
# Covers submit, continuation, forced answer, wrong answer, compaction and timeout.
uv run --locked --extra runtime --no-editable python tests/offline_smoke.py

# Real Anthropic provider against a loopback fake + actual Harbor/Docker.
# All count endpoints fail; local mode must send only /v1/messages requests.
uv run --locked --extra runtime --no-editable python tests/offline_local_count_smoke.py

# Separate-verifier Docker controls on puzzle 004, for both variants:
# gold -> 1, wrong -> 0, missing -> 0, with agent-workspace isolation checks.
# --full additionally runs all 100 unmodified generated CLI oracle solutions.
uv run --locked --extra runtime --no-editable python tests/offline_verifier_smoke.py --full
```

## Troubleshooting

- Offline count tests require the tokenizer's public vocabulary to be cached first:
  `uv run --locked --extra runtime --no-editable python -c 'import tiktoken; tiktoken.get_encoding("o200k_base")'`.
  This downloads vocabulary data if missing; it does not call a model API.
- `Task exists`: reuse the generated tasks, or regenerate the same set with
  `--overwrite`. Changing the selection requires a fresh directory.
- Missing task path: use the directory printed by generation; do not mix
  `datasets/chess-smoke` with `datasets/chess-puzzles`.
- Docker connection error: start Docker Desktop and check `docker info`.
- Missing answer: valid zero reward with `missing_answer` status. A verifier
  crash instead removes stale reward and exits nonzero; inspect its trial logs.
- Checksum mismatch: restore the pinned CSV, rather than updating the expected hash.
- macOS editable-import issue: retain `--no-editable` in the uv commands.

## Citation

```bibtex
@misc{epochai_chess_puzzles,
  title={Chess Puzzles},
  author={{Epoch AI}},
  url={https://github.com/epoch-research/chess-puzzles-mirror}
}
```

## Authors & Contributions

Yuxuan Tang (tangalantt@gmail.com): adapter contributor.
Original benchmark: Epoch AI. The Inspect-derived scorer retains its MIT notice.
