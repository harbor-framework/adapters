# BizAgentBench → Harbor (WIP)

## Overview

This adapter generates all 50 BizAgentBench tasks and runs the **unmodified native
business environment and evaluator** behind an isolated public turn interface.
The grader runs in a fresh, separate container after the agent container stops.

Status: all **50 public-tool reference workflows are constructed and pass isolated
G/P/F/Strict checks**. All 50 also pass the full native runner and Harbor's separate
grader with identical complete verdicts, using a scripted customer. These results
are recorded separately from live-LLM validation. **Not ready for benchmark acceptance:** independent LLM
customer verification and coordinated real-model parity remain unrun. No registry
publication or PR is claimed. See `validation/summary.json` for execution coverage.

## What is BizAgentBench?

[BizAgentBench](https://github.com/ant-intl/BizAgentBench) evaluates long-horizon
payment-service work through multi-turn customer conversations and business tools.
Its frozen release contains 50 tasks, 789 knowledge documents and 601 discoverable
business capabilities. A separate LLM customer supplies information, uploads real
portal files and approves proposals. Deterministic native checks calculate Goal
(G), Process (P), Protection (F), and Strict success from business state and ordered
execution history; no model judge is involved.

The exact source is commit `670ec25cd934ae8c18e18f5c8f91fdfa0bb571d4`.
Generation requires that clean Git checkout and embeds `git archive` output with
its SHA-256. Source code, task data, user policy and vendored Tau2 stay together.

## Adapter Features

- Canonical `bizagentbench` CLI with `--output-dir`, `--limit`, `--task-ids`,
  `--overwrite`, `--source-dir`, `--model-config`, and `--oracle-dir`.
- Registry-safe stable names: `ant-intl/bizagentbench-case-001` through `-050`.
- Native `tools.evaluate.run_case` owns both roles, tool execution, environment
  initialization, replay evaluation, budgets, context compaction and errors.
- `business` sidecar holds the hidden user scenario, task contract, initial world,
  native program, credentials and live history. None is copied into the main image.
- Public `/turn` and `/respond` expose only the assistant's native model boundary.
  Business tools are the original tool schemas; receipts and dialogue are returned
  through the native orchestrator. There is no public state import or score API.
- Native provider and collection listeners bind only to sidecar loopback. The
  agent cannot call customer tools, replace the authoritative world, grant its own
  consent, or submit an execution history for grading.
- Harbor stops `main`, runs the collect hook in `business`, and copies artifacts
  **from that service**. A fresh verifier image recomputes the native full verdict
  from this evidence and its own frozen source, then checks it against the native
  runner's verdict and reward. It clears both reward file formats before grading.
- `BizAgentBenchAgent` forwards exact native assistant SSE requests to the configured
  provider, including tool schemas and sampling/output parameters. Native code still
  handles response assembly, model identity checks, retries and context overflow.
  The host relay cancels an in-flight provider call when the native episode ends.
  Raw provider statuses/SSE are delivered via trusted Harbor `service_exec` to a
  sidecar loopback endpoint; the agent-visible API cannot invent provider failures.
  CLI agents can use `python /app/biz.py turn/respond` for a separate generalization
  experiment; their shell interaction is not claimed as native-agent parity.

## Generated Task Structure

```text
bizagentbench-case-001/
├── task.toml                    # separate verifier + trusted service artifacts
├── source.json                  # source/data commit, archive/config hashes
├── instruction.md               # public interaction protocol
├── environment/
│   ├── Dockerfile               # main image: Python + public client only
│   ├── biz.py
│   ├── docker-compose.yaml
│   └── runtime/                 # private sidecar build context
│       ├── upstream.tar         # pinned complete native release
│       ├── requirements.txt     # hashed locked dependencies
│       ├── private.json         # task/config; no embedded API keys
│       ├── runtime.py
│       ├── collect.py
│       └── Dockerfile
├── tests/                       # fresh verifier build context, not agent assets
│   ├── Dockerfile
│   ├── upstream.tar
│   ├── requirements.txt
│   ├── source.json
│   ├── grade.py
│   └── test.sh
└── solution/
    ├── solve.sh                 # explicit error until a reference is supplied
    └── replay.py                # public assistant-only replay
```

## Run Evaluation / Harness

Registry evaluation is **not available yet**; no dataset has been published.
After publication the intended command is `harbor run -d ant-intl/bizagentbench`.

For local development, from the adapters repository root:

```bash
harbor run -p datasets/bizagentbench/bizagentbench-case-031 -a oracle
harbor run -c src/bizagentbench/run_bizagentbench.yaml
```

Default generated oracle commands intentionally fail until reference trajectories
are provided. The separate scripted datasets described below contain all 50
candidate references; their fixture-dependent results do not establish live-LLM
oracle success.
The reference YAML defaults to oracle and includes commented native-model and
standard CLI-agent alternatives. Docker Compose and separate verifier support
are required. Actual integration validation used Harbor **0.26.0**; older Harbor
versions without `verifier.collect`, service artifacts and separate environments
are unsupported. The installed Harbor distribution did not include a Git SHA.

For the custom model agent, make this adapter importable in the Harbor interpreter
(e.g. run Harbor with `uv run --with harbor==0.26.0` from this adapter directory),
set `BIZ_MODEL_CONFIG` to the exact generation config, and use
`-a bizagentbench.agent:BizAgentBenchAgent`. The config's agent model ID controls
the native request; it must match the intended dated provider model. Supply the
agent credential on the host and the user credential to Docker Compose via the
variable names in `api_key_env`. Keys are never written into generated configs.

## Usage: Create Task Directories

From `src/bizagentbench/`:

```bash
uv sync --frozen
# Clone once if the pinned research checkout is not already available.
git clone https://github.com/ant-intl/BizAgentBench.git /path/to/BizAgentBench
git -C /path/to/BizAgentBench checkout 670ec25cd934ae8c18e18f5c8f91fdfa0bb571d4
uv run bizagentbench --source-dir /path/to/BizAgentBench \
  --output-dir ../../datasets/bizagentbench --model-config /path/to/model.json
uv run bizagentbench --source-dir /path/to/BizAgentBench \
  --output-dir /tmp/biz-smoke --task-ids case_001 case_031
uv run bizagentbench --source-dir /path/to/BizAgentBench \
  --output-dir /tmp/biz-smoke --limit 1 --overwrite
```

Without `--model-config`, upstream's example is copied; its invalid placeholder
endpoints must be replaced before real evaluation. Use the upstream config schema
and environment-variable credentials. Every generated task retains its config
hash, and repeated generation is deterministic. Overwrite only replaces recognized
generated task directories; unrelated directories and symlinks are rejected.

`--oracle-dir /path/to/references` accepts `case_NNN.json` files containing assistant
Chat Completions messages. Replay submits them only through the public API; it
cannot choose customer actions or write business state. Linear scripts may depend
on a particular independent customer's tool sequence, so a passing offline fixture
is not a substitute for validating a live-customer oracle. The public-tool planners
for all 50 cases are included in `scripts/reference_plans.py`; raw local traces and
private construction evidence stay under ignored `validation/` paths.

## Comparison with Original Benchmark (Parity)

**Real-model parity has not run.** There is no `parity_experiment.json` because no
paired model runs, SEM or range-overlap result exists. Metadata records zero parity
and registry coverage. No experiment URLs or scores are fabricated.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|---|---|---|---|---|---|---|
| bizagentbench-llm-agent@0.1.0 | Not run | Strict / G / P / F | 0 | 0 / 50 | Not available | Not available |

The offline equivalence probe covers case 001 (Operations Desk/formal verifier)
and case 031 (PSP/expansion verifier). Each makes one real `get_clock` call and
concludes via the native customer stop rule. Their complete native verdicts,
termination, tool counts, classifications and Harbor rewards agree. Both are
legitimate unsuccessful business attempts (Strict=0), **not successful oracles**.
The scripted provider has zero token use and does not establish model parity.

To reproduce that probe, from this adapter directory (Harbor must be available):

```bash
uv run python scripts/prepare_offline.py --source-dir /path/to/BizAgentBench \
  --output-dir /path/to/offline-tasks
# Set PYTHONPATH to this adapter's src/ and tests/ directories for Harbor.
harbor run -p /path/to/offline-tasks -a smoke_agent:OfflineSmokeAgent \
  --jobs-dir validation/harbor --job-name offline-equivalence -n 1
# Build business with the generated Compose file first.
docker compose -p bizagentbench-build -f /path/to/offline-tasks/bizagentbench-case-001/environment/docker-compose.yaml build business
# Mount this adapter at /adapter and validation/ at /validation, using --network none.
docker run --rm --network none -v /absolute/adapter:/adapter:ro \
  -v /absolute/validation:/validation bizagentbench-build-business \
  python /adapter/scripts/native_offline.py --output /validation/native
uv run python scripts/compare_offline.py --native validation/native \
  --harbor validation/harbor/offline-equivalence --output validation/offline-equivalence.json --forgery-probe
```

The smoke agent deliberately forges main-container evidence and both reward formats,
and attempts the private collection route. The separate grader must ignore these
forgeries and produce the native zero reward without the alternate forged file.
`OfflineRelayAgent` also exercises the production model relay against a local SSE
fixture. User protocol/HTTP failure probes use `prepare_offline.py --user-mode
{offline-bad-user,offline-http-error}` and the same native script option; these
must retain the original classifications with **no reward file**, not a numeric zero.

The **50-case scripted reference suite** constructs business success exclusively
through native public tools. Approval-required writes go through proposal,
customer-portal inspection and approval, then assistant execution. Customer files,
bank updates, signatures, recipient reads and final outcomes use the native tools;
no world/history assignment constructs a successful state. Plans read public
responses and authored customer facts from the customer instructions. They do not
import contracts, hidden acceptance predicates or graders. A separate trusted
process owns the world and saves construction evidence only for later checking.

Final offline coverage is **50/50 native successes, 50/50 Harbor successes and
50/50 complete verdict matches**, with 61 adapter regression tests passing. This
coverage uses the explicit corrected selection, including two retained initial
adapter verifier failures and their successful retries; it is not a model pass rate.

Construction checks run in a separate network-disabled container and return a
nonzero exit status for empty inputs or any failed Strict verdict. The full native
runner and Harbor then replay each workflow against a local scripted SSE customer.
Harbor still stops the agent, collects the business service's authoritative
evidence and recomputes the full verdict in its fresh verifier. The report checks
all verdict fields, reward, classification, termination, tool count, task identity,
trace hash and the actual Harbor verifier mode. The explicit selection records the
two named retries (021 and 030); failed runs remain in the attempt ledger.

The fixture controls customer replies and decisions, including exact approval
payloads and actual tool receipts. This tests public-tool feasibility and harness
equivalence; **it does not test an independent LLM customer's policy compliance,
planning ability or generalization**. Earlier batches 01–03 used shorter scripted
customer receipts; later batches return the actual receipt JSON. Packaged fixture
hashes are recorded per task. Native and Harbor comparisons use the same fixture
within each pair. A script-dependent linear trajectory may fail with another
customer's event order, so these are candidate oracles for future live validation.

Reproduce a subset with a fresh output directory (extend `--task-ids` to all 50):

```bash
uv run python scripts/build_references.py --source-dir /path/to/BizAgentBench \
  --task-ids case_001 case_031 case_040 --output validation/references/new-attempt
# A distinct grader container; never run this in the planner or main container.
docker run --rm --network none -v /absolute/adapter:/adapter:ro \
  -v /absolute/validation:/validation bizagentbench-build-business \
  python /adapter/scripts/check_references.py \
  --references /validation/references/new-attempt --output /validation/check-new-attempt
docker run --rm --network none -v /absolute/adapter:/adapter:ro \
  -v /absolute/validation:/validation bizagentbench-build-business \
  python /adapter/scripts/reference_batch.py native \
  --references /validation/references/new-attempt --output /validation/native-new-attempt
uv run python scripts/reference_batch.py prepare --source-dir /path/to/BizAgentBench \
  --references validation/references/new-attempt --output /path/to/scripted-tasks
harbor run -p /path/to/scripted-tasks -a oracle \
  --jobs-dir validation/harbor --job-name scripted-new-attempt -n 1
uv run python scripts/compare_offline.py --native validation/native-new-attempt \
  --harbor validation/harbor/scripted-new-attempt --output validation/new-equivalence.json \
  --expected-task-ids case_001 case_031 case_040
```

The full local selection is `validation/scripted-reference-selection.json`.
After every selected run completes, audit all 50 without invoking a grader:

```bash
uv run python scripts/report_references.py \
  --selection validation/scripted-reference-selection.json \
  --output validation/scripted-reference-equivalence.json
uv run python scripts/reference_ledger.py --output validation/scripted-attempt-ledger.json
```

`validation/live-llm-validation.json` records the separate, currently unrun model
track. There are no live model scores or SEM inferred from these scripted runs.

For future coordinated model parity use the same pinned release and config:

```bash
# Original side, in the pinned upstream checkout:
python -X utf8 tools/evaluate.py --config /path/to/model.json \
  --output /path/to/original/run-1 --numbers 1 2 3 4 5 --workers 1
# Harbor side, after generating the identical selection/config:
harbor run -p /path/to/matching-tasks -a bizagentbench.agent:BizAgentBenchAgent \
  --jobs-dir /path/to/harbor --job-name run-1 -n 1
```

Agree exact models, customer, seeds, dates, budgets, agent/runtime versions,
selection, repetition count and key provisioning first. Follow the required
symmetric ramp-up: 5–10 tasks on both sides, one full run on both, then repeated
runs (at least two per side). Record raw run arrays, mean ± sample SEM, and
range overlap only after actual execution. The custom relay uses native HTTPAgent
on both sides. Standard CLI-agent generalization remains a separate validation.
No upstream fork is needed for this transport-only native runner reuse.

## Notes & Caveats

- **Acceptance blockers:** all-task oracle verification with an independent LLM
  customer, an agreed
  provider experiment plan/configuration, real-model paired parity, standard CLI
  generalization, evidence publication and dataset registration remain unfinished.
- No upstream benchmark defects are claimed. Complete upstream runtime, scoring,
  evaluation and transport tests pass in the Linux image. The Windows sandbox
  transport run stalled; it was stopped and the intended Linux tests were used.
- The native 5,400-second episode timer and max_errors=16 are defaults from upstream
  config, not new limits. There is no imposed tool-call or dialogue-step cap.
  Harbor allows another 120 seconds for native finalization; the native runner
  rejects queued business actions after its own deadline. A custom config changes
  the generated wrapper timeout and public budget description accordingly.
- `###STOP###` is the native **customer** stop signal for the HTTPAgent path;
  assistant text containing it does not by itself terminate this upstream agent.
  Early diagnostic smoke attempts exposed this fixture assumption; the fixture was
  corrected, and final evidence uses native customer termination. Original attempt
  logs remain locally available in `validation/harbor/offline-smoke`.
- Simulator/provider/verifier failures retain upstream classifications. Missing
  reward, invalid native verification and replay mismatches make the verifier exit
  nonzero with an error report, leaving neither reward file. Genuine agent protocol
  failures and wall-clock limits are scored exactly as upstream decides.
- The adapter compares the full recomputed verdict in JSON transport form. Native
  expense evidence contains tuples, which JSON serializes as lists; cases 021 and
  030 exposed an adapter-only false mismatch. JSON normalization fixes this
  representation issue without dropping fields or changing native checks. Original
  failed verifier runs and successful retries are retained. A regression test also
  confirms that changing one payment amount still fails verification.
- Main contains no grader/private assets, mounts no business state, and receives no
  user credential. Trusted evidence is collected only from `business` after main
  stops. This requires Harbor's service-artifact isolation; no shared-volume grading
  fallback is provided. Raw native traces become reviewer artifacts after execution.
- Dependency versions and hashes are locked in `uv.lock` and exported
  `src/bizagentbench/requirements.txt`. Python 3.12 base image digest is
  `sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df`.
- Streaming is buffered by the host relay before delivery to the native parser.
  Message contents and SSE errors are preserved, but latency and stream-arrival
  timing differ; real-provider deadline and context-overflow validation is pending.
- Full source archives are duplicated into each sidecar/verifier build context.
  A 50-task generated dataset uses several GB on disk; generated datasets and raw
  execution artifacts are intentionally outside the adapter source submission.

## Installation / Prerequisites

Python 3.12, Git, uv, Docker with Linux containers/Compose, and Harbor 0.26.0 with
separate verifier/service-artifact support. Use this adapter's isolated `uv sync`
environment; do not install native runtime dependencies into another adapter's or
Harbor's existing environment. On Windows set `PYTHONUTF8=1` or use `-X utf8`.

```bash
uv sync --frozen
uv run pytest -q
# Reproduce all adapter tests on Linux (mount the clean pinned Git checkout):
docker build -t bizagentbench-offline-tests -f tests/Dockerfile .
docker run --rm --network none -v /absolute/adapter:/adapter:ro \
  -v /path/to/BizAgentBench:/upstream:ro bizagentbench-offline-tests
# In the built Linux business image, no provider/network access required:
docker run --rm --network none -w /opt/bizagentbench \
  -e PYTHONPATH=/opt/bizagentbench:/opt/bizagentbench/third_party/tau2-bench/src \
  bizagentbench-build-business python -m unittest discover -s tests -v
```

## Troubleshooting

- Generator rejects a checkout: verify exact HEAD and `git status --porcelain`,
  including untracked files. A different release must be explicitly reviewed.
- GBK decode errors: enable UTF-8; the source release reads some files with the
  platform default encoding.
- Windows reports passed tests but the interpreter does not exit: use the Linux
  test image above. Native participant-stack imports can leave shutdown work pending
  in the restricted Windows environment; a printed test summary alone does not prove
  that the process finished. The Linux suite is the completed validation evidence.
- Docker permission denied in a sandbox: test daemon access in an authorized
  environment. This is independent of benchmark correctness.
- Empty/missing reward: inspect the separate verifier's `error.json` and the
  trusted native `result.json`, not an agent-written file. Simulator/provider errors
  deliberately remain unscored. Do not convert them to zero for aggregation.
- Reference unavailable: `solution/solve.sh` fails explicitly. Build and validate
  a genuine tool-driven solution; never write a success world or score as a shortcut.

## Citation

```bibtex
@misc{zhao2026bizagentbench,
  title = {BizAgentBench: Unveiling Hidden Challenges in Deploying Long-Horizon Agents for Real-World Business},
  author = {Enhan Zhao and Yongqi Tong and Xuejun Yu and Hang Wang and Pan Wang and Yichao Wang and Di He and Jianshe Li and Jiang-Ming Yang and Wei Wu},
  year = {2026},
  eprint = {2610.20424},
  archivePrefix = {arXiv}
}
```

## Authors & Contributions

BizAgentBench: Enhan Zhao, Yongqi Tong and the original benchmark authors.
Harbor adapter implementation: QYechang. Upstream code and vendored Tau2 retain
their MIT licenses, included in each pinned source archive.
