# ScarfBench toolchain image

## Why

Without a pre-built image, every Harbor run rebuilds the same ~1–2 GB
toolchain from scratch for all 200+ tasks (Maven + JDK 21 + JDK 11 + Python +
uv + Playwright + Chromium + ActiveMQ Artemis). That means:

- 200× redundant Docker builds per experiment run
- ~1–2 GB of network + disk I/O per task
- Most of the per-run variance comes from this build, not from the agent

Building the image once and pushing it to a registry eliminates all of that.
Harbor 0.22+ picks it up via `docker_image = "..."` in `[environment]` inside
`task.toml`.

## What is in the image

The image contains **only the build toolchain** — no smoke tests, no verifier
scripts, no secrets. Those stay private inside each task's `tests/` bundle.
The image is safe to host publicly.

| Layer | Purpose |
|---|---|
| `maven:3.9.12-ibm-semeru-21-noble` | Java 21, Maven |
| `eclipse-temurin:11-jdk` | Java 11 for legacy Gradle wrappers (petclinic/realworld Spring source only) |
| apt packages | curl, jq, git, Python, Playwright system deps, PostgreSQL client |
| uv | Fast Python package manager for smoke-suite deps |
| Playwright 1.58.0 + Chromium | Pre-baked browser for smoke tests |
| ActiveMQ Artemis 2.31.2 | JMS broker (cargotracker/quarkus only; no-op for all other tasks) |

## Registry

The image is published to GitHub Container Registry under the `scarfbench`
org, so it is not tied to any individual's account:

```
ghcr.io/scarfbench/scarfbench-base:<TAG>
```

## One-time setup

### 1. Log in to GHCR

Create a GitHub personal access token (classic) with the `write:packages`
scope, from an account that can publish packages in the `scarfbench` org, then:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u <github-username> --password-stdin
```

### 2. Build and push

```bash
cd src/scarfbench-compile/docker
./build-and-push.sh 2026-10-09
```

The first argument is the tag (defaults to `latest`). To push somewhere else
(e.g. a fork), set `SCARFBENCH_IMAGE_REPO=ghcr.io/<owner>/scarfbench-base`.

### 3. Make the package public (first push only)

New GHCR packages are private by default. In the `scarfbench` org on GitHub,
go to **Packages → scarfbench-base → Package settings**, set visibility to
**Public**, and grant the maintainers' team admin access so ownership is not
held by a single person.

## Generating tasks with the pre-built image

```bash
# Via CLI flag
uv run scarfbench-compile \
    --output-dir ../../datasets/scarfbench-compile \
    --docker-image "ghcr.io/scarfbench/scarfbench-base:2026-10-09"

# Via environment variable
export SCARFBENCH_DOCKER_IMAGE="ghcr.io/scarfbench/scarfbench-base:2026-10-09"
uv run scarfbench-compile
```

Each generated `task.toml` will contain:

```toml
[environment]
docker_image = "ghcr.io/scarfbench/scarfbench-base:2026-10-09"
```

Harbor will pull the image once per execution environment instead of building
it for every task.

## Keeping the image up to date

Re-run `build-and-push.sh` whenever `Dockerfile` changes (e.g. after updating
Playwright or Artemis). Tag releases with a date or semantic version and pin
tasks to it rather than `latest`, so results stay comparable across runs:

```bash
./build-and-push.sh 2026-10-09
# then regenerate:
uv run scarfbench-compile --docker-image "ghcr.io/scarfbench/scarfbench-base:2026-10-09" ...
```
