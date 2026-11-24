## RecreationBench → Harbor Adapter

## Overview

This adapter converts the **Web split of RecreationBench** into Harbor tasks. In each task the agent is given a running reference web application and must rebuild it as a new React/TypeScript project from observation alone: it can browse the reference, but it cannot read the reference's source files.

- **Task type:** software recreation (front-end web apps), long-horizon, multimodal (browser screenshots and accessibility snapshots through Playwright MCP).
- **Size:** 50 tasks, one per row of the upstream task list [`tasks/web.jsonl`](https://github.com/QwenLM/RecreationWorld/blob/ee01f2bd014a56f7e17850a5d42002c807b96beb/tasks/web.jsonl), which the adapter reads from the pinned checkout at generation time and does not copy into this repository (16 easy, 17 medium, 17 hard by upstream labels). 44 are synthetic sites (`*.example`); 6 are frozen snapshots derived from public websites (`climatewatch.org`, `detox.github.io`, `keycloak.org`, `postgresql.org`, `rust-lang.org`, `webpack.js.org`).
- **Provenance:** [RecreationWorld](https://github.com/QwenLM/RecreationWorld) (Qwen, [arXiv 2609.22000](https://arxiv.org/abs/2609.22000)) and the [`Qwen/RecreationBench`](https://huggingface.co/datasets/Qwen/RecreationBench) dataset. Both are pinned: framework commit `ee01f2bd014a56f7e17850a5d42002c807b96beb`, dataset revision `284341f8fc3d6680dd57ca5414fed92a0fe33b95`.
- **Licensing:** the framework is MIT. The dataset is a multi-license collection: benchmark-authored code is MIT, benchmark-authored dataset content is CC BY 4.0, and third-party assets keep their own terms. Each generated task carries the upstream per-task `LICENSE`.
- **Scope:** RecreationBench has 250 tasks on five platforms (Ubuntu, macOS, Windows, Android, Web; 50 each). Only the Web split is adapted. The other four need OS virtual machines or an Android emulator with GUI automation, which do not fit a Harbor container task.
- **Main adaptation choices:** the prompt, the task environment and the scorer are the upstream ones, run unmodified from the pinned commit. The adapter splits the upstream single orchestrator process into Harbor's phases (environment, agent, verifier) at the same boundary the upstream worker already uses (`run_agent.py --skip-eval`, then `run_agent.py --skip-agent`).

## What is RecreationBench?

RecreationBench measures whether a hybrid computer-use agent can turn interactive access to a running application into a working reimplementation. The agent decides when to explore the reference, write code, build and launch its candidate, compare the two, and revise. The final candidate is evaluated on observable behaviour, not source similarity, so any implementation that behaves and looks like the reference can score.

A Web task is scored by two numbers, each in [0, 1]:

- **Prog:** tier-weighted pass rate of hidden Playwright tests that were validated against the reference (content, navigation, interactive widgets).
- **VLM:** pass rate of per-page binary visual assertions, judged by a VLM (Qwen3.7-Plus at temperature 0 in the paper) on desktop (1920x1080) and mobile (375x812) screenshots of the candidate.

The task score is the unweighted mean of the two. The paper reports Prog, VLM and their average, macro-averaged over the 50 Web tasks. Integrity gates (screenshot pasting, reading the answers, verbatim scraping, external egress) cap a violating submission at 0.10.

## Adapter Features

- **Upstream code does the work.** The image installs the RecreationWorld runtime at the pinned commit. The instruction is rendered by upstream `core.recreation_prompt.render`, the workspace by upstream `prepare_workspace`, the served dataset by upstream `materialize_web_dataset`, the reference by the upstream static handler, and the score by upstream `run_agent.py --skip-agent`.
- **Same environment as the benchmark.** The Dockerfile mirrors `providers/web/Dockerfile`: Ubuntu 24.04, Node 22.18.0, Playwright 1.60.0, Playwright MCP 0.0.79, Claude Code 2.1.177, Codex 0.145.0, and the same apt and Python packages (fonts and Chromium build affect both the hidden layout tests and the judged screenshots).
- **Reference isolation as upstream does it.** The agent runs as the non-root `agent` user (`[agent].user`). The reference site, the dataset input and the scorer are root-only inside the image, and the hidden tests are not in the image at all: Harbor uploads them for the verifier. The agent reaches the reference only over `http://localhost:8100`.
- **Network confinement.** The upstream rollout runs in a network namespace with routes only to the reference and the model endpoint. The tasks declare `network_mode = "allowlist"` for the agent phase, so Harbor admits the agent's model host and nothing else. The verifier phase is confined to judge endpoints because it builds agent-authored code.
- **Browser tools through Harbor.** Playwright MCP is declared in `task.toml` with the upstream arguments, so any Harbor agent with MCP support gets the same browser tools. No custom agent is added.
- **Small task directories.** Each image downloads only its own reference site from the pinned dataset revision at build time (21.6 GB across the 50 tasks, 17 MB to 4.1 GB each). The generated task directories hold the hidden tests and are 2.1 GB in total.
- **Oracle.** RecreationBench has no reference recreation; its oracle is the reference site itself, scored against its own hidden tests through the upstream `--reference-candidate` lane. See Notes & Caveats for the expected oracle scores.

## Generated Task Structure

```
recreationbench/
├── {task-slug}/                      # e.g. rust-lang-org (upstream id rust-lang.org)
│   ├── task.toml                     # name qwen/recreationbench__{task-slug}, limits, network policy, MCP server
│   ├── instruction.md                # upstream prompt, rendered for http://localhost:8100
│   ├── LICENSE                       # upstream per-task notice
│   ├── environment/
│   │   ├── Dockerfile                # upstream Web image + pinned runtime + this task's reference
│   │   └── rb-harbor/
│   │       ├── fetch_reference.py    # downloads web/{id}/reference at the pinned revision, repairs blank frames
│   │       ├── prepare_task.py       # upstream materialise + prepare_workspace, then seals inputs
│   │       ├── ensure-reference.sh   # starts the upstream static handler on port 8100
│   │       └── entrypoint.sh
│   ├── solution/
│   │   ├── solve.sh                  # requests the reference-candidate lane
│   │   └── oracle_token
│   └── tests/
│       ├── test.sh
│       ├── run_verifier.py           # stages the hidden tests, runs upstream run_agent.py --skip-agent
│       ├── oracle_token.sha256
│       └── task/
│           ├── tests/                # upstream hidden tests and ground truth (static/, interactive/, gt/)
│           └── vlm_assertions.json
```

The adapter code follows the standard layout:

```
src/recreationbench/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_recreationbench.yaml
└── src/recreationbench/
    ├── __init__.py
    ├── adapter.py
    ├── main.py
    ├── reference_sizes.json          # per-task reference size at the pinned revision (sets storage_mb)
    └── task-template/
```

## Run Evaluation / Harness

Every run, including the oracle, needs a VLM judge for the visual score. Export an OpenAI-compatible endpoint before starting Harbor:

```bash
export RB_VLM_KEY=...            # judge API key
export RB_VLM_BASE_URL=...       # e.g. https://ai-gateway.vercel.sh/v1
export RB_VLM_MODEL=...          # e.g. alibaba/qwen3.7-plus (the paper's judge)
```

The verifier may reach `dashscope.aliyuncs.com`, `dashscope-intl.aliyuncs.com`, `ai-gateway.vercel.sh` and `openrouter.ai`. For any other judge host add `--allow-verifier-host <host>`.

### Running with Datasets Registry

```bash
# Oracle
harbor run -d qwen/recreationbench

# A specific agent and model
harbor run -d qwen/recreationbench -a claude-code -m "anthropic/claude-opus-5" --ak version=2.1.177
```

### Using Job Configurations

```bash
# From the adapters repository root, after generating tasks into datasets/recreationbench
harbor run -c src/recreationbench/run_recreationbench.yaml

# Or point at the generated tasks directly
harbor run -p datasets/recreationbench -a claude-code -m "anthropic/claude-opus-5" --ak version=2.1.177
```

Results are written to `jobs/` by default.

### Running Individual Trials

```bash
harbor trial start -p datasets/recreationbench/corravale-example
harbor trial start -p datasets/recreationbench/corravale-example -a claude-code -m "anthropic/claude-opus-5"
```

Each trial writes `verifier/metrics.json` (reward, Prog, VLM, status, integrity reasons) and `verifier/eval_results/` (upstream `scores.json`, `score_report.txt`, `test_details.json`).

### Running Claude Code through the upstream proxy

When it is given a model endpoint (`RB_MODEL_BASE_URL`), the released upstream runner does not point Claude Code at it directly. It starts a local proxy ([`claude-code-proxy`](https://github.com/seanbabalala/claude-code-proxy), pinned in the image, wrapped by upstream `rb-claude-code-proxy`) that translates Claude Code's requests for an OpenAI-compatible endpoint. The tasks can do the same. Export the endpoint before starting Harbor and the container starts the proxy on `127.0.0.1:8000` with the upstream settings:

```bash
export RB_MODEL_BASE_URL=https://ai-gateway.vercel.sh/v1   # OpenAI-compatible endpoint
export RB_MODEL_API_KEY=...
export RB_MODEL=alibaba/qwen3.7-plus                       # the proxy sends every request to this model
export RB_PROXY_TOKEN=local-dev-token                      # placeholder credential, as upstream
```

and point the agent at the proxy in the job configuration (the gateway host has to be allowed for the agent phase, because the proxy runs inside the task container):

```yaml
agents:
  - name: claude-code
    model_name: alibaba/qwen3.7-plus
    skip_model_parsing: true
    base_url: http://127.0.0.1:8000
    model_api_key_name: RB_PROXY_TOKEN
    extra_allowed_hosts: [ai-gateway.vercel.sh]
    kwargs: {version: "2.1.177"}
    env:   # the stream timeouts the upstream runner exports for the CLI
      API_TIMEOUT_MS: "1800000"
      CLAUDE_ENABLE_BYTE_WATCHDOG: "0"
      CLAUDE_ENABLE_STREAM_WATCHDOG: "0"
      CLAUDE_SLOW_FIRST_BYTE_MS: "600000"
      CLAUDE_BYTE_STREAM_IDLE_TIMEOUT_MS: "600000"
      CLAUDE_STREAM_IDLE_TIMEOUT_MS: "600000"
```

Without `RB_MODEL_BASE_URL` no proxy is started and agents use their model endpoint as in any other Harbor task.

## Usage: Create Task Directories

```bash
cd src/recreationbench
uv sync
uv run recreationbench --output-dir ../../datasets/recreationbench
```

Available flags:
- `--output-dir`: directory to write generated tasks (defaults to `datasets/recreationbench`)
- `--limit`: generate only the first N tasks
- `--overwrite`: overwrite existing tasks
- `--task-ids`: only generate these tasks (upstream ids such as `rust-lang.org`, or slugs such as `rust-lang-org`)
- `--split`: `full` (default, all 50 tasks) or `parity` (a seeded, difficulty-stratified subset of 10: 3 easy, 3 medium, 4 hard)
- `--rb-repo`: use an existing RecreationWorld checkout at the pinned commit instead of cloning it
- `--dataset-dir`: use an existing copy of `Qwen/RecreationBench` (laid out as `web/<task-id>/...`) instead of downloading
- `--allow-agent-host`: extra host the agent phase may reach (repeatable)
- `--allow-verifier-host`: extra host the verifier may reach (repeatable), for a judge endpoint that is not on the default list
- `--open-network`: generate tasks without the network allowlist, for engines that cannot enforce one (see Notes & Caveats); not the benchmark's protocol

Generation clones RecreationWorld at the pinned commit and downloads each task's hidden tests (2.0 GB for all 50) into `~/.cache/harbor-recreationbench`. It does not download the reference sites; the task images do.

## Comparison with Original Benchmark (Parity)

Parity experiments have not been run yet. The plan is to be agreed with the Harbor team before any run.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| TBD | TBD | Task score (mean of Prog and VLM) | TBD | TBD | TBD | TBD |

Links:
- Original benchmark: https://github.com/QwenLM/RecreationWorld
- Dataset: https://huggingface.co/datasets/Qwen/RecreationBench
- Adapter PR: TBD
- Dataset PR: TBD
- Parity results PR: TBD

Reproduction, original side: build `providers/web/Dockerfile` at the pinned commit and run `rb-web-sandbox-run` per task with `RB_AGENT_CLI`, `RB_MODEL`, `USE_VLM_JUDGE=true`, the judge settings and `TIMEOUT_MULTIPLIER=10`. The fixes that the released entrypoint needs are listed under Notes & Caveats.

Reproduction, Harbor side:

```bash
harbor run -p datasets/recreationbench -a <agent> -m <model> --ak version=<pinned version>
```

### Oracle verification

All 50 tasks were run with the oracle agent through Harbor 0.25.0 on Modal (allowlist network policy, 4 vCPU / 8 GiB per trial, judge `alibaba/qwen3.7-plus` at temperature 0), one scored trial per task. Reward is the task score, the mean of Prog and VLM. 49 tasks score between 0.938 and 0.987 (mean 0.972, Prog 0.991, VLM 0.953); `climatewatch-org` scores 0.763 for the reason given under Notes & Caveats. An oracle reward of 1.0 is not reachable on this benchmark: see the first note below.

<details>
<summary>Per-task oracle results</summary>

| Task | Reward | Prog | VLM | Minutes |
|------|--------|------|-----|---------|
| `ablira-example` | 0.9740 | 0.9920 | 0.9561 | 52 |
| `aperlio-example` | 0.9512 | 0.9810 | 0.9214 | 203 |
| `astrovia-example` | 0.9725 | 0.9920 | 0.9531 | 54 |
| `borvia-example` | 0.9660 | 0.9877 | 0.9442 | 110 |
| `bramble-example` | 0.9549 | 0.9355 | 0.9743 | 35 |
| `breezel-example` | 0.9792 | 1.0000 | 0.9583 | 140 |
| `buildara-example` | 0.9675 | 0.9817 | 0.9532 | 68 |
| `cascora-example` | 0.9653 | 0.9750 | 0.9557 | 109 |
| `climatewatch-org` | 0.7631 | 0.9921 | 0.5341 | 65 |
| `corravale-example` | 0.9769 | 0.9975 | 0.9563 | 24 |
| `cresvia-example` | 0.9739 | 0.9897 | 0.9581 | 54 |
| `detox-github-io` | 0.9718 | 1.0000 | 0.9436 | 154 |
| `fluvica-example` | 0.9752 | 0.9976 | 0.9528 | 77 |
| `formora-example` | 0.9787 | 0.9992 | 0.9583 | 145 |
| `fynora-example` | 0.9837 | 0.9951 | 0.9723 | 85 |
| `glyphel-example` | 0.9773 | 0.9952 | 0.9593 | 139 |
| `gradyn-example` | 0.9839 | 1.0000 | 0.9678 | 91 |
| `haulvio-example` | 0.9595 | 0.9809 | 0.9382 | 93 |
| `inclura-example` | 0.9435 | 0.9360 | 0.9510 | 166 |
| `kartova-example` | 0.9852 | 0.9975 | 0.9728 | 85 |
| `keycloak-org` | 0.9710 | 1.0000 | 0.9421 | 105 |
| `klaravo-example` | 0.9809 | 0.9984 | 0.9634 | 95 |
| `klavrium-example` | 0.9819 | 1.0000 | 0.9637 | 121 |
| `mendova-example` | 0.9775 | 0.9971 | 0.9578 | 111 |
| `nimbric-example` | 0.9616 | 0.9889 | 0.9342 | 44 |
| `obseron-example` | 0.9383 | 0.9496 | 0.9269 | 299 |
| `postgresql-org` | 0.9730 | 1.0000 | 0.9460 | 93 |
| `praxide-example` | 0.9715 | 0.9992 | 0.9438 | 135 |
| `praxora-example` | 0.9786 | 0.9955 | 0.9617 | 99 |
| `quorvex-example` | 0.9761 | 0.9943 | 0.9578 | 50 |
| `rankspire-example` | 0.9715 | 0.9982 | 0.9447 | 156 |
| `relvyn-example` | 0.9768 | 0.9961 | 0.9575 | 100 |
| `rituvia-example` | 0.9735 | 0.9979 | 0.9491 | 200 |
| `rust-lang-org` | 0.9873 | 1.0000 | 0.9746 | 92 |
| `sentorra-example` | 0.9739 | 0.9984 | 0.9495 | 179 |
| `sonelio-example` | 0.9745 | 0.9929 | 0.9560 | 66 |
| `sonivex-example` | 0.9826 | 1.0000 | 0.9653 | 90 |
| `streamora-example` | 0.9760 | 0.9939 | 0.9580 | 142 |
| `talvio-example` | 0.9546 | 0.9751 | 0.9341 | 175 |
| `terravyn-example` | 0.9771 | 0.9946 | 0.9596 | 82 |
| `vaultera-example` | 0.9483 | 0.9867 | 0.9099 | 161 |
| `vellora-example` | 0.9755 | 0.9977 | 0.9532 | 113 |
| `veranthe-example` | 0.9737 | 0.9961 | 0.9514 | 32 |
| `verendale-example` | 0.9806 | 0.9940 | 0.9673 | 67 |
| `verentia-example` | 0.9774 | 0.9931 | 0.9617 | 80 |
| `veridara-example` | 0.9707 | 1.0000 | 0.9413 | 101 |
| `verrindale-example` | 0.9839 | 0.9899 | 0.9778 | 110 |
| `vizmara-example` | 0.9732 | 0.9880 | 0.9584 | 210 |
| `weavora-example` | 0.9793 | 0.9991 | 0.9595 | 68 |
| `webpack-js-org` | 0.9531 | 1.0000 | 0.9062 | 122 |
| **Mean (50)** | **0.9675** | **0.9908** | **0.9443** | 109 |

</details>

## Notes & Caveats

- **Oracle scores are not 1.0, and are not 1.0 upstream either.** The oracle is the reference site scored by its own tests. With the original harness, the two reference sites checked before this adapter was written scored Prog 0.9975 / VLM 0.951 (`corravale.example`) and Prog 0.992 / VLM 0.963 (`ablira.example`): a few validated tests fail on their own reference, and the VLM judge does not pass every assertion on a perfect candidate. The Harbor oracle reproduces those numbers to within judge noise (`corravale-example` 0.9769 = Prog 0.9975 / VLM 0.9563; `ablira-example` 0.9740 = Prog 0.9920 / VLM 0.9561), so the bar for this adapter is "oracle reward equals the original harness's reference score", not reward 1.0.
- **How the oracle is selected.** `solve.sh` copies a token from `solution/` into the workspace. The verifier compares its hash with `tests/oracle_token.sha256` and, on a match, runs the upstream `--reference-candidate` lane, which skips the template build and the copy-detection gates (a verbatim copy of the reference would otherwise be capped at 0.10 by design). Agents never see `solution/`.
- **Subset.** Only the 50 Web tasks of 250 are adapted (see Overview).
- **The rollout budget is 20 hours per task** (`time_limit_seconds` 7200 x the runner's default multiplier 10), which is the paper's protocol. Use `--agent-timeout-multiplier` to shorten it for smoke runs; scores are then not comparable with the paper.
- **Deviations from the upstream image.** The runtime is cloned at the pinned commit instead of copied from a build context; the noVNC shim, the passwordless-sudo entry for the unused `user` account and the empty `PLAYWRIGHT_DOWNLOAD_HOST` override are dropped; the scaffold's `node_modules` are installed at build time with the same `npm ci` the upstream worker runs at start-up, with the agent's npm cache warmed from it.
- **Network confinement differs in mechanism.** Upstream uses a network namespace with loopback relays; here Harbor's allowlist policy does the job, and the verifier records the rollout as confined so the upstream egress gate behaves as it does upstream. If you run with the allowlist disabled, set `RB_AGENT_NETWORK_CONFINED=0` so that gate penalises external fetches as upstream does for unisolated runs. Environments without allowlist support cannot run these tasks as written: Docker needs a Linux kernel with nftables `fib` support, which Docker Desktop's VM lacks, and Harbor then refuses to start the trial. For local development on such an engine, generate with `--open-network`; those tasks default `RB_AGENT_NETWORK_CONFINED` to 0.
- **Trajectory-based gates.** The upstream scorer scans the CLI transcript for leaked answers, external egress and a terminal API failure. The verifier feeds it Harbor's recorded transcript for Claude Code and Codex. For other agents those three checks see no transcript; the DOM-based gates (screenshot paste, verbatim scrape) still apply.
- **A rollout that ends on an API error is not scored.** Upstream exits with its infrastructure code in that case; the verifier does the same and writes no reward, so Harbor reports the trial as errored.
- **Upstream issues found while adapting** (all handled outside the pinned checkout, none changes scoring):
  - The released `rb-web-sandbox-run` puts the workspace at `$RB_OUTPUT_DIR/workspace` while the prompt tells the agent to deliver in `/workspace/recreation`. The upstream worker (`scripts/platforms/web/worker.sh`) uses `/workspace/recreation`, and so does this adapter.
  - The dataset ships `reference/site/` unpacked, but the runner at this commit reads `reference/reference.tar.gz`. The image packs the directory.
  - The released Dockerfile does not install the scaffold's dependencies; without them every post-rollout build fails offline.
- **One reference snapshot is repaired at build time (`climatewatch.org`).** 56 of its pages carry hidden analytics frames whose `src` was frozen as a site path (`<iframe src="/countries/BRA/about:blank">`) instead of `about:blank`. The upstream static handler answers an unknown path with the root `index.html`, which holds the same frame, so each page loads the whole application inside itself; on this site that never settles, `load` does not fire and Chromium ends with `Page crashed`. With the pinned commit and dataset revision, unmodified, the reference then scores 0.35 against its own tests (Prog 0.18: all 232 scripted functional tests time out and no mobile screenshot can be taken), and an agent browsing the reference sees pages that hang. `fetch_reference.py` rewrites those `src` values to `about:blank` (60 attributes, nothing visible changes); after that Prog is 0.992 (232 of 232 scripted tests) and the oracle reward is 0.763. The rest of the gap is a second upstream defect that only affects the oracle: at the mobile viewport this snapshot scrolls inside `<body>` (it was frozen with `ReactModal__Body--open`), the upstream screenshot code excludes `<body>` when it looks for the scrolling element, and every mobile capture of the reference then aborts with `mobile page height changed while capturing`, so its mobile views are scored 0 (VLM 0.534). The scorer is run unmodified, so this is left as it is; a recreation that scrolls the document itself does not take that path. Eleven other snapshots carry the same kind of frame (for example `praxide.example` and `verrindale.example`) but load and pass their tests as shipped, so the repair is applied to `climatewatch.org` only and the other 49 references are byte-identical to upstream. An original-side run that includes this task needs the same repair to be comparable; the parity subset does not include it.
- **Third-party content.** Six tasks are derived from public websites. Their assets are downloaded from the upstream dataset at build time and are not redistributed in the generated task directories; the hidden tests and ground-truth DOM snapshots for those tasks are.

## Installation / Prerequisites

- A Harbor environment that can enforce a network allowlist: Docker on a Linux host, Daytona, Modal or E2B (Docker Desktop cannot; see `--open-network`)
- Harbor installed (`uv tool install harbor`); developed against Harbor 0.25.0
- For task generation: `git`, and from `src/recreationbench`: `uv sync`
- A VLM judge endpoint and key (`RB_VLM_KEY`, `RB_VLM_BASE_URL`, `RB_VLM_MODEL`)
- A model API key for the agent you run
- Each trial needs 4 vCPU, 8 GiB memory and 20 to 27 GiB of disk; the first image build takes several minutes and later tasks reuse its layers

## Troubleshooting

- **Verifier fails with "the visual score needs a VLM judge":** export `RB_VLM_KEY`, `RB_VLM_BASE_URL` and `RB_VLM_MODEL` in the shell that runs Harbor.
- **`ValueError: ... this environment cannot change network policy after start`:** the container engine cannot enforce the allowlist (Docker Desktop). Run on Linux Docker or a cloud environment, or generate with `--open-network` for local development.
- **Judge calls time out or are refused:** the judge host is not on the verifier allowlist; pass `--allow-verifier-host <host>`.
- **Image build fails while downloading the reference:** Hugging Face throttles anonymous clients on many small files. The download retries and resumes; lower `n_concurrent_trials` if several large tasks build at once.
- **Healthcheck fails:** the reference server did not start; `/var/log/rb-reference.log` in the container has the reason.
- **An agent's `npm install <package>` fails:** expected. The rollout has no route to the npm registry, as upstream; the scaffold's declared dependencies are already installed.

## Citation

```bibtex
@misc{qwen2026recreationworld,
      title={RecreationWorld: Scalable and Verifiable Environments for Hybrid Computer-Use Agents},
      author={Shuai Bai and Jiayong Deng and Sicheng Fan and Yikun Fu and Chang Gao and Xuhao Hu and Mianqiu Huang and Yizhen Jiang and Yuheng Jing and Dehui Kong and Keliang Li and Ning Li and Wanli Li and Dayiheng Liu and Dunjie Lu and Changwei Luo and Que Shen and Zheyuan Wang and Zijian Wang and Jie Wu and Gao Wu and Zhihui Xie and Rui Xie and Haiyang Xu and An Yang and Jiakang Yuan and Yanming Zhang and Jiajun Zhang and Xi Zhang and Zhenru Zhang and Zhuo Zhen and Mingkang Zhu and Bowen Zhou},
      year={2026},
      eprint={2609.22000},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2609.22000},
}
```

## Authors & Contributions

This adapter is developed and maintained by Christian Iacullo (Alloy).

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines
