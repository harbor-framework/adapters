## SREGym → Harbor Adapter

**Status: work in progress.** SREGym-Lite oracle: 17/17 pass on both stages (diagnosis through SREGym's LLM judge, and mitigation). The full-split oracle and parity are pending. See Notes & Caveats.

## Overview

[SREGym](https://github.com/SREGym/SREGym) is a live benchmark for AI SRE agents. Each problem deploys a real microservice application on a Kubernetes cluster, injects a fault (misconfiguration, network policy, admission webhook, Kafka poison pill, retry storm, …), and asks the agent to **diagnose** the incident and then **mitigate** it on the live cluster.

- **Source benchmark**: SREGym ([SREGym/SREGym](https://github.com/SREGym/SREGym)), pinned at commit `ac60c642`
- **Domains**: site reliability engineering, Kubernetes incident response, cloud system failures
- **Datasets / splits**:
  - `sregym/sregym-lite`: **17 tasks**, upstream **SREGym-Lite** (`--suite sregym-lite`). This is the default split.
  - `sregym/sregym`: **216 tasks**, the full upstream campaign (all 222 registered problems at the pinned commit, which upstream runs when no `--suite`/`tasklist.yml` is given) minus 6 exclusions.
  - `lite-ia` (17): SREGym-Lite's faults on the Incident Arena apps, available with `--split lite-ia`.
- **Excluded tasks** (6, full split only; reasons from upstream's `environment_ports.NOT_PORTED`, `ProblemRegistry.non_emulated_cluster_problems` and Lite's selection):
  - `node_clock_drift_hotel_reservation`: shifts the host-kernel-global clock. Upstream rejects it on emulated clusters.
  - `kubelet_crash`: stops worker kubelets, which cannot be repaired through the Kubernetes API.
  - `latent_sector_error`, `latent_sector_error_saleor`, `silent_data_corruption`, `silent_data_corruption_frappe`: khaos storage faults that need real block devices.
- **Task naming**: `sregym/<problem-id>`, with the upstream ID lowercased and `_` → `-` (for example `sregym/network-policy-block`).

## What is SREGym?

SREGym (Clark et al., arXiv:2605.07161) creates live system environments for SRE agents. It builds on AIOpsLab and ITBench, adds OS-level, metastable, and concurrent failures, and simulates real public postmortems. A *conductor* runs each problem through two agent stages. **Diagnosis**: the agent submits a natural-language root-cause description, which an LLM judge compares with the ground-truth root cause. **Mitigation**: the agent fixes the live system and submits, and the problem's programmatic mitigation oracle checks the result.

## Adapter Features

- **Upstream runtime, unmodified**: each task runs SREGym's own `main.py` campaign for one problem, in its default *filtered* mode, inside SREGym's upstream Docker-in-Docker image (private dockerd + 4-node KIND/Calico cluster).
- **Agent isolation**: the Harbor agent runs as an unprivileged user in a `main` container with no SREGym code. Its interfaces are the ones an upstream SREGym agent has: a kubeconfig for SREGym's filtering Kubernetes API proxy (chaos namespaces hidden, workload creation blocked) and the conductor API. Agent-phase egress is allowlisted to the SREGym backend and model provider APIs (`--network allowlist`, the default), mirroring upstream's filtered internet mode.
- **Grading integrity**: all grading happens in the sidecar. The sidecar's oracle endpoints are disabled unless an oracle run sets `SREGYM_ENABLE_ORACLE=1`, and they also require a per-task HMAC token derived from a private, random generation secret. The verifier runs as root from `/` with `python3 -I`, first kills leftover agent processes, and scores only a result it fetched from the sidecar in this run.
- **Same prompt**: `instruction.md` is produced by SREGym's own Claude Code driver (`clients.claudecode.driver.build_instruction`) for each problem.
- **Same grading**: diagnosis (LLM judge) and mitigation (programmatic oracle) are evaluated by the SREGym conductor when the agent submits, exactly as upstream. The verifier only collects the conductor's result row.
- **Oracle**: submits the problem's ground-truth root cause, then applies SREGym's `recover_fault()`, waits until the application's pods are running and ready (up to 600 s) plus a 180 s stabilization period (480 s for `consul_stale_snapshot_restore_hotel_reservation` and `profile_mongodb_eviction_unit_mismatch_hotel_reservation`, whose requests keep failing for several minutes after recovery; see `ORACLE_SETTLE_OVERRIDES` in `adapter.py`), and submits the mitigation. The wait changes only when the reference solution submits. Without it, oracles that check pod state or traffic at submission time grade a rollout that is still in progress (for example a pod still in `CrashLoopBackOff` one second after the fix).
- **Rewards**: `reward.json` with `mitigation`, `diagnosis`, `overall` (both passed), and `reward` (= mitigation).

## Generated Task Structure

```
sregym/
├── network-policy-block/
│   ├── task.toml                 # name sregym/network-policy-block, timeouts, metadata
│   ├── instruction.md            # SREGym's Claude Code prompt for this problem
│   ├── environment/
│   │   ├── Dockerfile            # agent container: kubectl, helm, curl, jq, python3
│   │   └── docker-compose.yaml   # main + privileged `sregym` sidecar (SREGym backend)
│   ├── solution/
│   │   └── solve.sh              # oracle: ground-truth diagnosis + recover_fault()
│   └── tests/
│       ├── test.sh               # signal agent finished, collect conductor result
│       └── score.py              # map SREGym result row → reward.json
```

Adapter code:

```
src/sregym/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── sregym.yaml                   # reference run config
├── sidecar/                      # sidecar image: SREGym DinD + Harbor bridge
│   ├── Dockerfile
│   ├── bridge.py
│   └── healthcheck.sh
└── src/sregym/
    ├── adapter.py
    ├── main.py
    ├── extract_metadata.py       # runs inside an SREGym checkout
    ├── problems_metadata.json    # snapshot for the pinned commit
    └── task-template/
```

## Run Evaluation / Harness

### Running with Datasets Registry

Not registered yet.

```bash
# Use oracle agent (reference solution)
harbor run -d sregym/sregym

# Use your specified agent and model
harbor run -d sregym/sregym -a claude-code -m "<model>"
```

### Using Job Configurations

```bash
# From the repository root
# Run a job with the default adapter configuration
harbor run -c src/sregym/sregym.yaml

# Or run a job without configuration yaml but instead with locally prepared dataset path
harbor run -p datasets/sregym -a oracle -n 1

# Resume a previously started job
harbor job resume -p jobs/<job-id>
```

### Running Individual Trial

```bash
# Run a single task with oracle (pre-written solution)
harbor trial start -p datasets/sregym/network-policy-block

# Run a single task with a specific agent and model
harbor trial start -p datasets/sregym/network-policy-block -a claude-code -m "<model>"
```

## Usage: Create Task Directories

```bash
cd src/sregym
uv run sregym                                    # SREGym-Lite (17)  -> datasets/sregym-lite
uv run sregym --split full                       # full SREGym (216) -> datasets/sregym
uv run sregym --task-ids network_policy_block --overwrite --output-dir /tmp/sregym
uv run sregym --clone                            # clone SREGym @ ac60c642 to a temp dir and re-extract
uv run sregym --sregym-root /path/to/SREGym      # re-extract from an existing checkout
```

Build the sidecar image once per host (requires Linux, Docker with Buildx, and privileged containers):

```bash
git clone --recurse-submodules https://github.com/SREGym/SREGym && cd SREGym && git checkout ac60c642
git submodule update --init --recursive
docker buildx build --load -t sregym-dind:ac60c642 -f docker/dind/Dockerfile .
docker build --build-arg SREGYM_DIND_IMAGE=sregym-dind:ac60c642 \
    -t sregym-harbor-sidecar:ac60c642 /path/to/adapters/src/sregym/sidecar
```

## Comparison with Original Benchmark (Parity)

Parity has not been run yet. The plan is to be agreed with the Harbor team.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| TBD | TBD | Mitigation success rate | TBD | 17 (SREGym-Lite) | TBD | TBD |

Reproduction requirements and steps (planned):

- **Original benchmark**: SREGym @ `ac60c642`, in its DinD runtime, with the `claudecode` agent.
- **Harbor adapter**: the `claude-code` agent on `datasets/sregym-lite`, with the same dated model and the same pinned diagnosis judge.
- **Metric**: per-run mitigation success rate (and diagnosis success rate) over the 17 problems, reported as mean ± sample SEM over runs.

```bash
# Original side (SREGym checkout @ ac60c642, Linux host)
python3 docker/dind/run.py build
python3 docker/dind/run.py run -- uv run --frozen main.py --suite sregym-lite \
    --agent claudecode --model <dated-model> --judge-model <dated-judge> --agent-timeout 1800

# Harbor side
cd src/sregym && uv run sregym && cd ../..
export SREGYM_JUDGE_MODEL=<dated-judge> OPENAI_API_KEY=...   # judge key, read by the sidecar only
harbor run -c src/sregym/sregym-lite.yaml -a claude-code -m <dated-model>
```

## Notes & Caveats

- **Oracle verification** (Harbor 0.26.0, local Docker, Ubuntu 24.04 x86_64 host, SREGym `ac60c642`, 3 concurrent trials, judge `gpt-5-2025-08-07`):
  - **SREGym-Lite, both stages: 17/17, reward 1.000** (diagnosis 1.000, mitigation 1.000, overall 1.000).
    - In the first pass 16 trials scored 1.0. The sidecar of `valkey-auth-disruption` exited during environment start, which Harbor recorded as an environment error, not a score.
    - A retry of that task scored 1.0 (it had also passed in an earlier mitigation-only run). The run took 1 h 54 min; each trial took 15–25 min (median about 18 min of environment start: cluster bring-up, app deployment, fault injection).
  - An earlier mitigation-only run (`SREGYM_STAGES=mitigation`) was also 17/17.
  - Every trial's oracle also checked the agent interfaces: `kubectl` through the filtering proxy succeeded, and a non-allowlisted host (`example.com`) was blocked during the agent phase.
  - The full split (216) oracle is in progress with the patches and settle overrides above (2 concurrent trials per host, at most one large app per host). Results will be added here.
- **Sidecar logs**: each trial collects the sidecar's `/opt/sregym/results` as the artifact `artifacts/sregym-sidecar/`. It includes the conductor output (`harbor/sidecar.log`), SREGym's run directory, and DinD/KIND logs. Harbor collects it also when the environment fails to start, so infrastructure failures can be diagnosed.
- **Privileged sidecar**: the `sregym` service needs `privileged: true` and a private cgroup namespace to run its own Docker daemon and KIND cluster (`harbor lint` reports `compose-privileged`). The agent container is not privileged. This follows the merged `frontier-cs-algorithm` adapter's privileged judge sidecar. Environments must support privileged nested Docker (local Docker on Linux).
- **Resources**: the sidecar gets 8 vCPU / 16 GB, or 16 vCPU / 32 GB for the larger Incident Arena and multi-tier apps (Saleor, Slack Spine, Frappe, Workspace, Gitea, GitLab, Train Ticket, Blueprint Hotel Reservation). Upstream recommends 8 CPUs / 16 GiB and "more for larger problems" (`docker/dind/README.md`). At 8 CPUs, several of these apps failed their own latency checks even with SREGym's recovery applied and passed at 16, and Train Ticket's deploy timed out the KIND API server. Override with `--sidecar-cpus` / `--sidecar-memory`. Also budget disk for each sidecar's private image cache. Environment start (cluster + app deploy + fault injection) takes 10–25 minutes. Use low concurrency.
- **Image pulls**: every trial has a private Docker daemon, so images are pulled again for each trial. Set `SREGYM_REGISTRY_MIRRORS` (for example a host pull-through cache) to avoid Docker Hub rate limits.
- **AMD64 only**: some application images (for example HotelReservation) are AMD64-only.
- **Diagnosis judge**: SREGym defaults the judge to the agent model. Here the judge is pinned per run with `SREGYM_JUDGE_MODEL` (default `gpt-5-2025-08-07`). Use the same judge on both sides of a comparison. The judge key is read by the sidecar from the shell running `harbor run`. Do not put it in the job config's `environment.env`, which reaches the agent's container.
- **Prompt**: `instruction.md` is SREGym's Claude Code driver prompt. Upstream's Codex driver words its prompt slightly differently, so parity should use claude-code (or Codex parity would need the Codex prompt on both sides).
- **Timeouts**: the agent budget defaults to upstream's 1800 s (`--agent-timeout`). Regenerate tasks with a larger value instead of using Harbor's agent-timeout multiplier, because the conductor's own deadline is fixed when the tasks are generated.
- **Oracle runs**: `SREGYM_ENABLE_ORACLE=1 harbor run -c src/sregym/sregym-lite.yaml`. Without the variable the oracle endpoints are disabled.
- **Metadata extraction**: four problems (`kubelet_eviction_threshold_misconfig*`, `taint_no_toleration_*`) query the cluster in their constructors. Their metadata was extracted against a live KIND cluster (`extract_metadata.py --live`).
- **Portability**: runs on a local Linux Docker host only (privileged nested Docker, `cgroup: private`, locally built sidecar image with `pull_policy: never`). Cloud environments are not supported yet.
- **Primary reward** is mitigation success, pending confirmation with the Harbor team. Diagnosis and overall are also reported.
- **Agent-finished signal**: SREGym ends an attempt when its agent process exits. The verifier tells the sidecar that the Harbor agent has finished, and the conductor then records any unsubmitted stage as failed, as upstream does.
- **Network**: with `--network allowlist` the agent can reach only the SREGym backend and model APIs. Upstream's filtered mode also removes Claude Code's `WebSearch`/`WebFetch` tools (WebSearch runs on the model provider's side, so a network allowlist alone would not stop it). Harbor does the same: for any non-public network policy it sets `disable_web_search` on `claude-code`, which denies `WebSearch` and `WebFetch` (Harbor `trial.py` `_configure_web_tools`). Both sides therefore run without web tools, with no adapter-specific agent settings.

- **Upstream fixes**: the sidecar applies the patches in `sidecar/patches/` to the pinned SREGym checkout. Each fixes an upstream bug that made a problem unsolvable even with its own `recover_fault()`. 0001 was reported upstream (link below); the others are carried here. Each patch will be dropped when the pinned commit includes a fix. The original side of a parity comparison must use the same patches.
  - `0001-exclude-accounting-from-high-request-latency.patch`: since SREGym #1176 added the namespace label to span metrics, `HighRequestLatency` fires permanently in a healthy astronomy-shop. The cause is `accounting`'s Kafka-consumer spans, which exceed 5 s. Every AlertOracle problem on astronomy-shop then fails with `alerts_still_firing`. An A/B run that changes only the collector config confirmed the cause. The patch excludes `accounting` from that rule, as is already done for `kafka`. Reported at https://github.com/SREGym/SREGym/pull/1176#issuecomment-7081818803.
  - `0002-fix-calico-slack-cleanup-recursion.patch`: `CalicoRouteReflectorLabelDriftSlack.__init__` wraps `app.cleanup` a second time after its parent already did, so `_app_cleanup` points at `_cleanup` itself. Every cleanup, including the conductor's pre-deploy "undeploy leftovers", then fails with `RecursionError` and the problem never starts. The patch drops the duplicate wrapping.
  - `0003-retry-kind-cluster-create.patch`: environment robustness only, no change to any problem or oracle. When several trials start KIND clusters on one host and the disk is saturated, a node can miss kind's readiness log line (`could not find a log line that matches "Reached target .*Multi-User System.*"`). The sidecar then exits before the problem is deployed. The patch retries `kind create cluster` up to three times from a clean cluster.
  - `0004-fix-kafka-queue-problems-restart-targets.patch`: `OtelFaultInjector` restarts the deployments that read a feature flag after changing it. It lists `kafka` (the broker) for `kafkaQueueProblems`, but the flag is read by `checkout` and `fraud-detection` (OTel demo docs and source). The broker has no persistent storage, so the restart on injection and again on recovery deletes the `orders` topic. `accounting`'s consumer then stays on the deleted topic, and `MessageConsumerLag` (or the error-rate and latency alerts) keeps firing after `recover_fault()`. The patch restarts `checkout` and `fraud-detection` instead.

## Installation / Prerequisites

- Linux host with Docker (Buildx), privileged containers, and cgroup v2. Raise inotify limits as in SREGym's [KIND guide](https://github.com/SREGym/SREGym/blob/main/kind/README.md) (`fs.inotify.max_user_instances=1024`, `fs.inotify.max_user_watches=1048576`).
- Harbor (`uv tool install harbor`), Python 3.12+, `uv`.
- The sidecar image (see above).
- API keys: the agent's model provider, plus the diagnosis judge provider.

## Troubleshooting

- **Sidecar exits during environment start** (`dependency failed to start ... sregym-1 exited (1)`): usually KIND failing to boot on an overloaded host. Lower `-n`, avoid running several large apps (Train Ticket, Blueprint, Saleor) at once on a disk-backed `/var/lib/docker`, and check `/opt/sregym/results/dind/kind-logs` in the trial artifacts.
- **Environment start timed out**: increase `--build-timeout` (default 5400 s), set registry mirrors, check `docker logs` of the `sregym` service. SREGym's DinD diagnostics are under `/opt/sregym/results/dind/` in the sidecar.
- **Verifier exits with code 2**: SREGym did not produce a result row (deployment or injection failure). The trial is an infrastructure error, not a score of 0.

## Citation

```bibtex
@article{clark:arxiv:2026,
  author = {Jackson Clark and Yiming Su and Saad Mohammad Rafid Pial and Yifang Tian and Lily Gniedziejko and Hans-Arno Jacobsen and Yinfang Chen and Tianyin Xu},
  title = "{SREGym: A Live Benchmark for AI SRE Agents with High-Fidelity Failure Scenarios}",
  journal = {arXiv:2605.07161},
  year = 2026,
  month = MAY,
}
```

## Authors & Contributions

This adapter is developed and maintained by [Yuan Gao](mailto:ygao31@uw.edu) for the Harbor team.

**Issues and Contributions:**

- Submit issues and pull requests to the main repository.
- Follow the project's coding style and commit guidelines.

## Acknowledgement

Builds on SREGym's Docker-in-Docker runtime and the earlier Harbor integration attempts by the SREGym team (harbor PR #301, SREGym/harbor `harbor-adapter-k3s`).
