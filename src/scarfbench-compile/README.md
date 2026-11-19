# ScarfBench-Compile Harbor Adapter

Converts the [ScarfBench](https://github.com/scarfbench/benchmark) benchmark into Harbor task directories that verify **compile + deploy + health check**.

## Overview

ScarfBench-Compile evaluates whether a migrated Java application compiles, deploys, and responds to HTTP requests — without running the functional smoke tests of the full benchmark.

Each task is a single framework-to-framework migration of one application (e.g. Jakarta EE → Quarkus). The adapter enumerates every ordered pair of frameworks available for each app across the benchmark's layers, producing **204 tasks** from the source benchmark. Frameworks covered: **Jakarta EE (Open Liberty)**, **Quarkus**, and **Spring Boot**.

The agent must:

1. Modify the source application code to use the target framework's APIs and patterns
2. Build the migrated application with Maven/Gradle (**compile**)
3. Boot the app until its framework startup message appears (**deploy**)
4. Serve a real endpoint over HTTP (**health**)

Main adaptation vs. the original benchmark: the functional `smoke.py` tests are removed in favor of a lightweight HTTP health check, so the reward is a three-key dict (`compile`/`deploy`/`health`) rather than a single functional pass/fail. This isolates compile/deploy failures from functional failures and speeds up agent-development iteration.

## What is ScarfBench?

[ScarfBench](https://github.com/scarfbench/benchmark) is a benchmark for evaluating automated framework migration of Java web applications. It ships real applications implemented in multiple frameworks (Jakarta EE, Quarkus, Spring Boot), enabling each (source → target) pair to be used as a migration task. The original harness compiles, deploys, and runs functional smoke tests against the migrated app. ScarfBench-Compile reuses the compile/deploy machinery and substitutes a generic reachability check for the functional tests.

## Adapter Features

- **Automatic repo management** — clones `https://github.com/scarfbench/benchmark` at generation time (or reuses a local clone via `--repo-dir`).
- **Comprehensive task generation** — discovers all apps across all layers and emits every valid ordered framework pair as a task.
- **Docker-free, separate verifier** — grading runs in a dedicated verifier container (`environment_mode = "separate"`, built from `tests/Dockerfile`) with the agent's `/app` copied in as an artifact. It runs Maven/Gradle and boots the app natively (no Docker daemon), using per-target-framework `framework.sh` logic.
- **Prebuilt images** — `--docker-image` / `--task-image-repo` point tasks at a prebuilt toolchain image (an image built from the generated `environment/Dockerfile`) and, optionally, thin per-task images (`FROM <toolchain>` + `COPY app/ /app/` from each task's `environment/`, tagged `<repo>:<task_id>`), so the toolchain isn't rebuilt for every trial.
- **Endpoint-aware health check** — runs the upstream `health_check.sh` when present, then sweeps candidate ports × context roots × source-declared routes for an HTTP 200 (or a 405 on a declared route / WebSocket handshake on a declared endpoint).
- **Oracle solution** — each task ships a reference migration (the benchmark's target-framework code) plus a `solve.sh`, so the `oracle` agent reproduces a known-good migration.
- **Optional skill guidance** — if a `SKILL.md` is present in the agent's skills directory, the instruction tells the agent to follow it; it is not required.

## Generated Task Structure

```
datasets/scarfbench-compile/
├── <task_id>/                  # e.g. cart-jakarta-to-quarkus
│   ├── task.toml               # Task configuration
│   ├── instruction.md          # Migration instructions for the agent
│   ├── environment/
│   │   ├── Dockerfile          # Agent environment (Maven + JDK + toolchain)
│   │   ├── docker-compose.yaml # Compose file for cloud providers (e.g. Daytona)
│   │   ├── settings.xml        # Maven mirror configuration
│   │   └── app/                # Source framework code to migrate
│   ├── solution/
│   │   ├── solve.sh            # Oracle: applies the reference migration to /app
│   │   └── app/                # Target framework reference code
│   └── tests/
│       ├── Dockerfile          # Verifier image (toolchain + /tests)
│       ├── framework.sh        # Docker-free build/run logic (target framework)
│       ├── test.sh             # Verification script (compile + deploy + health)
│       ├── health_check.sh     # Upstream health check (app-specific URL/path/port), if available
│       └── settings.xml        # Maven mirror configuration
```

## Run Evaluation / Harness

```bash
# From the repository root

# Run the oracle (reference solution) on a single task
uv run harbor run -p datasets/scarfbench-compile/<task-id> -a oracle

# Run a specific agent/model on the whole local dataset
uv run harbor run -p datasets/scarfbench-compile \
  -a claude-code -m anthropic/claude-sonnet-4-5-20250929

# Run with the bundled job configuration
uv run harbor run -c src/scarfbench-compile/run_scarfbench-compile.yaml
```

Trial/job outputs are written under `jobs/` (configurable via `jobs_dir` in the YAML config).

## Usage: Create Task Directories

```bash
cd src/scarfbench-compile

# Generate all tasks (clones the ScarfBench repo automatically)
uv run scarfbench-compile

# Generate specific tasks
uv run scarfbench-compile \
  --task-ids cart-jakarta-to-quarkus converter-spring-to-jakarta

# Filter by layer, app, or framework
uv run scarfbench-compile \
  --layer whole_applications --from-framework jakarta --to-framework quarkus

# Limit the number of tasks
uv run scarfbench-compile --limit 10

# Overwrite existing tasks
uv run scarfbench-compile --overwrite

# Use an already-cloned repo (skips the network download)
uv run scarfbench-compile --repo-dir /path/to/scarfbench-benchmark
```


### CLI Options

| Option | Description |
|--------|-------------|
| `--output-dir` | Directory to write generated tasks (default: `datasets/scarfbench-compile`) |
| `--repo-dir` | Path to an already-cloned ScarfBench repo (skips git clone if provided) |
| `--docker-image` | Prebuilt toolchain image for `task.toml` (overrides `SCARFBENCH_DOCKER_IMAGE`) |
| `--task-image-repo` | Per-task image repo; tasks use `<repo>:<task_id>` (overrides `SCARFBENCH_TASK_IMAGE_REPO`) |
| `--task-ids` | Generate only specific task IDs |
| `--layer` | Filter to a specific layer (e.g., `business_domain`, `whole_applications`) |
| `--app` | Filter to a specific application name (e.g., `cart`, `cargotracker`) |
| `--from-framework` | Filter to a source framework (`jakarta`, `quarkus`, `spring`) |
| `--to-framework` | Filter to a target framework (`jakarta`, `quarkus`, `spring`) |
| `--limit` | Generate only the first N tasks |
| `--overwrite` | Overwrite existing task directories |

## Reward Format

The verifier writes a three-key reward to `/logs/verifier/reward.json`:

```json
{
  "compile": 0,
  "deploy": 0,
  "health": 0
}
```

- `compile` — 1 if the Maven/Gradle build succeeds (Jakarta also requires `liberty-maven-plugin` or Cargo)
- `deploy` — 1 if the framework's startup message appears in the launch log
- `health` — 1 if a real endpoint returns HTTP 200 (or 405 on a declared route / a WebSocket handshake on a declared endpoint)

## Comparison with Original Benchmark (Parity)

> **Status: parity pending.** Numbers below are placeholders until the parity run is executed; see `parity_experiment.json` for the authoritative state and the deferred fields (`metrics`, `dataset_pr`, `parity_pr`).

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| _TBD_ | _TBD_ | compile / deploy / health | _TBD_ | 204 | _TBD_ | _TBD_ |

Because ScarfBench-Compile drops the functional smoke tests, the headline metric is the per-stage pass-rate (`compile`, `deploy`, `health`) rather than the original functional pass/fail. Parity is therefore established in two steps:

1. **Oracle sanity** — the reference migration should pass all three stages at ~100%:
   ```bash
   uv run harbor run -p datasets/scarfbench-compile -a oracle
   ```
2. **Agent parity** — run an agent over the parity subset and compare the compile/deploy/health rates to the original benchmark's compile/deploy outcomes:
   ```bash
   uv run harbor run -c src/scarfbench-compile/run_scarfbench-compile.yaml \
     -a claude-code -m anthropic/claude-sonnet-4-5-20250929
   ```

Report each score as **mean ± sample SEM** across runs once available, and record the dataset/parity PR links in `parity_experiment.json`.

## Notes & Caveats

- **Build cost.** Each verification runs a full Maven build and downloads dependencies; first runs are network- and time-heavy. A Maven mirror (`settings.xml`) is injected and transient resolution failures are retried with `mvn -U`. Use a prebuilt `--docker-image` to avoid rebuilding the toolchain per task.
- **Version spread.** Framework versions vary across apps in the upstream benchmark; the instruction's framework-specific guidance reflects the dominant versions and tells the agent to check each reference app.
- **Health check is reachability, not correctness.** A passing `health` only means one real endpoint answered, not that the app is functionally correct (the functional smoke tests from the original harness are not run).

## Installation / Prerequisites

Adapters are standalone `uv` Python packages.

```bash
cd src/scarfbench-compile
uv sync
```

Requirements:
- Docker installed and running (local runs), or a cloud environment such as Daytona
- Harbor installed and working (see the main repository README)
- `git` available for cloning the ScarfBench benchmark
- API keys for any agents/models you evaluate (exported as environment variables, e.g. `ANTHROPIC_API_KEY`)

## Troubleshooting

- **Clone fails / offline** — pass `--repo-dir` pointing at a local checkout of `scarfbench/benchmark` to skip the network download.
- **Empty `/app` for the agent** — `--docker-image` without `--task-image-repo` makes hosts that skip `environment/Dockerfile` start with no source; pass both, or neither.
- **Deploy times out** — large apps can exceed the watcher window; the verifier prints the last 60 lines of the launch log on failure.
- **Health check fails but app seems up** — on failure the verifier prints the discovered routes and the HTTP code each one returned.

## Citation

```bibtex
@misc{scarfbench,
  title  = {ScarfBench: A Benchmark for Automated Java Framework Migration},
  author = {Krishna, Rahul and McGinn, Bridget},
  url    = {https://github.com/scarfbench/benchmark}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Bridget McGinn](mailto:bridget.mcginn@ibm.com).

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main Harbor repository
- Follow the project's coding style and commit guidelines
