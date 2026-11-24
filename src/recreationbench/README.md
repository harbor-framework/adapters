## RecreationBench → Harbor Adapter

## Overview

This adapter converts the **Web split of RecreationBench** into Harbor tasks. In each task the agent is given a running reference web application and must rebuild it as a new React/TypeScript project from observation alone: it can browse the reference, but it cannot read the reference's source files.

- **Task type:** software recreation (front-end web apps), long-horizon, multimodal (browser screenshots and accessibility snapshots through Playwright MCP).
- **Size:** 50 tasks, one per reference site in `tasks/web.jsonl` of the upstream repository (16 easy, 17 medium, 17 hard by upstream labels). 44 are synthetic sites (`*.example`); 6 are frozen snapshots derived from public websites (`climatewatch.org`, `detox.github.io`, `keycloak.org`, `postgresql.org`, `rust-lang.org`, `webpack.js.org`).
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
│   │       ├── fetch_reference.py    # downloads web/{id}/reference at the pinned revision
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
- `--rb-repo`: use an existing RecreationWorld checkout at the pinned commit instead of cloning it
- `--dataset-dir`: use an existing copy of `Qwen/RecreationBench` (laid out as `web/<task-id>/...`) instead of downloading
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

## Notes & Caveats

- **Oracle scores are not 1.0, and are not 1.0 upstream either.** The oracle is the reference site scored by its own tests. With the original harness, the two reference sites checked before this adapter was written scored Prog 0.9975 / VLM 0.951 (`corravale.example`) and Prog 0.992 / VLM 0.963 (`ablira.example`): a few validated tests fail on their own reference, and the VLM judge does not pass every assertion on a perfect candidate. The Harbor oracle is expected to reproduce those numbers, so the bar for this adapter is "oracle reward equals the original harness's reference score", not reward 1.0.
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
