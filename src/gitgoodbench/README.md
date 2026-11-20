# GitGoodBench → Harbor Adapter

## Overview

GitGoodBench is a benchmark of Git tasks mined from open-source Python, Java and Kotlin repositories. This adapter converts its merge conflict resolution scenario into Harbor format: a real merge was started and stopped on its conflicts, and the agent must resolve them and conclude the merge.

The size of the adapted benchmark is 60 tasks: the `merge` samples of GitGoodBench Lite, 20 each for Python, Java and Kotlin. The benchmark's `file_commit_chain` samples are not converted.

We follow the original evaluation: exact match against the ground-truth merge commit.

## What is GitGoodBench?

GitGoodBench ([paper](https://aclanthology.org/2025.realm-1.19/), [repository](https://github.com/JetBrains-Research/git-good-bench)) is a benchmark by JetBrains Research, presented at REALM 2025 (co-located with ACL 2025). It tests agents on version-control workflows, which benchmarks such as SWE-bench leave out. The paper reports a 13.33% solve rate on the 60 Lite merge scenarios for a GPT-4o baseline with custom tools.

- Metric: solve rate (exact match against the ground-truth merge commit)
- Source: https://huggingface.co/datasets/JetBrains/git_good_bench-lite
- License: Apache-2.0 for the dataset; Apache-2.0, MIT or BSD for the source repositories

## Adapter Features

- Converts the 60 `merge` samples of GitGoodBench Lite, one task per sample
- Rebuilds each scenario like the original harness: first parent checked out on `current-scenario-branch`, second parent merged, stopped on the recorded conflicts
- Instruction is the original merge prompt with every conflict hunk quoted
- Ground-truth merge commit removed from the image, and agent network limited to model APIs
- Offline exact-match verifier, as in the original `Evaluator`
- Oracle solution for validation (60/60 pass rate)

## Generated Task Structure

```
gitgoodbench/
├── spulec-freezegun-merge-0000/
│   ├── task.toml                 # Task configuration
│   ├── instruction.md            # Original merge prompt with the conflict hunks
│   ├── environment/
│   │   ├── Dockerfile            # Python 3.12 slim image with Git
│   │   ├── setup_scenario.py     # Builds the merge scenario at image build time
│   │   └── scenario.json         # Repository and commits of the scenario
│   ├── solution/
│   │   ├── solve.sh              # Oracle solution (commits the ground-truth merge)
│   │   └── ground_truth.bundle   # Ground-truth merge commit as a Git bundle
│   └── tests/
│       ├── test.sh               # Test runner
│       ├── evaluate.py           # Exact-match verifier
│       └── config.json           # Merge parents and ground-truth tree id
├── mockito-mockito-merge-0002/
│   └── ...
└── ...
```

Task names follow `jetbrains/gitgoodbench__<task-id>`, for example `jetbrains/gitgoodbench__spulec-freezegun-merge-0000`.

Adapter code structure:
```
src/gitgoodbench/
├── README.md
├── adapter_metadata.json               # Adapter metadata
├── parity_experiment.json              # Parity experiment results
├── pyproject.toml
├── run_gitgoodbench.yaml               # Oracle job configuration
├── parity/
│   ├── README.md                       # Parity setup and results in detail
│   ├── run_gitgoodbench_parity.yaml    # Parity job configuration
│   ├── reference-harness.patch         # Original-side harness
│   └── results/                        # Raw parity and oracle results
├── tests/                              # Unit tests for the generator and the verifier
└── src/gitgoodbench/
    ├── adapter.py                      # Main adapter code
    ├── main.py                         # CLI entry point
    └── task-template/                  # Task templates
        ├── task.toml
        ├── instruction.md
        ├── environment/
        │   ├── Dockerfile
        │   └── setup_scenario.py
        ├── solution/solve.sh
        └── tests/
            ├── test.sh
            └── evaluate.py
```

## Run Evaluation / Harness

### Using Registry (after publishing)

```bash
# Run on entire dataset with the oracle
harbor run -d jetbrains/gitgoodbench

# Run on entire dataset with an agent
harbor run -d jetbrains/gitgoodbench -a <agent-name> -m <model-name>

# Run single task
harbor run -t jetbrains/gitgoodbench__spulec-freezegun-merge-0000 -a <agent-name> -m <model-name>
```

### Using Job Configuration

```bash
harbor run -c src/gitgoodbench/run_gitgoodbench.yaml
```

### Using Local Dataset Path

```bash
harbor run -p datasets/gitgoodbench -a <agent-name> -m <model-name>
```

### Individual Trial

```bash
harbor trial start -p datasets/gitgoodbench/spulec-freezegun-merge-0000 -a <agent-name> -m <model-name>
```

The tasks let the agent reach `api.anthropic.com` and `api.openai.com` only. For another provider, add its host with `--allow-agent-host <host>`.

## Usage: Create Task Directories

```bash
cd src/gitgoodbench

# Generate all 60 tasks into datasets/gitgoodbench
uv run gitgoodbench

# Generate a subset
uv run gitgoodbench --limit 10

# Generate specific tasks
uv run gitgoodbench --task-ids spulec-freezegun-merge-0000
```

Other flags: `--output-dir`, `--overwrite`, `--dataset-path` (load samples from a local export) and `--split full` (the 450 merge samples of the full dataset, which are not registered).

## Comparison with Original Benchmark (Parity)

The baseline agent of the paper cannot be run: its LLM client, agent loop and data source were removed from the released code, which the benchmark's first author confirmed. The original side of the parity experiment is therefore a reference harness that adds those pieces back and runs a standard CLI agent in the original scenario container, with the original scenario setup and scoring. [`parity/README.md`](parity/README.md) describes the harness and the differences between the two sides.

Both sides ran mini-swe-agent 2.4.6 with `deepseek-v4-1-flash-260910`, 3 runs over all 60 tasks.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| mini-swe-agent@2.4.6 | deepseek-v4-1-flash-260910 | Solve rate (%) | 3 | 60 (100%) | 40.56 ± 2.0031 | 41.67 ± 0.9623 |

Per-run solve rates: original 36.67, 41.67, 43.33; Harbor 40.00, 43.33, 41.67. The ranges overlap, and 52 of the 60 tasks have the same outcome in all runs on both sides.

Links:
- Original benchmark: [JetBrains-Research/git-good-bench](https://github.com/JetBrains-Research/git-good-bench) at `b11ae6cd92be2b8b96e237d379427e04ad59c455`
- Reference harness: [YanggWendy/git-good-bench](https://github.com/YanggWendy/git-good-bench/tree/0375616a91a58e495b370908918d01991bc6ebf4), branch `harbor-parity`
- [Adapter PR](https://github.com/harbor-framework/adapters/pull/78) and [dataset PR](https://github.com/harbor-framework/harbor-datasets/pull/277)
- Parity results: [HuggingFace parity-experiments PR](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/281). The shared repository is over the Hub's file limit and does not accept uploads at the moment, so the files are at [yanggwendy/gitgoodbench-parity](https://huggingface.co/datasets/yanggwendy/gitgoodbench-parity/tree/main/adapters/gitgoodbench) in the same layout.

### Oracle Verification

Oracle agent passes 60/60 tasks (100%) on Daytona, and 60/60 on the original side. Negative controls all score 0: no-op agent, leftover conflict markers, correct files committed without merging, forged Git history and a reward file planted before grading. The same controls run as unit tests: `uv run --with pytest pytest tests` in `src/gitgoodbench`.

### Reproduction

```bash
export OPENAI_API_KEY="your_api_key"
export OPENAI_BASE_URL="your_openai_compatible_endpoint"

# Harbor side: generate tasks, then 3 attempts on Daytona
cd src/gitgoodbench && uv run gitgoodbench && cd ../..
harbor run -c src/gitgoodbench/parity/run_gitgoodbench_parity.yaml

# Original side: reference harness
git clone https://github.com/YanggWendy/git-good-bench.git && cd git-good-bench
git checkout 0375616a91a58e495b370908918d01991bc6ebf4  # branch harbor-parity
docker build -f docker/cli-agent.Dockerfile -t gitgoodbench-cli-agent .
pip install docker datasets "mini-swe-agent==2.4.6" "litellm==1.91.1"
python -m src.agent_client.run_cli_agent_benchmark --agent mini-swe-agent \
    --model openai/deepseek-v4.1-flash --image gitgoodbench-cli-agent \
    --hide-ground-truth --runs 3 --run-name mswea-deepseek-v4.1-flash-aligned
python -m src.agent_client.summarize_cli_agent_results results/mswea-deepseek-v4.1-flash-aligned/results.jsonl
```

The parity job file allows the endpoint's host during the agent phase (`extra_allowed_hosts`); change it for another endpoint.

## Notes & Caveats

- **Shell instead of custom tools**: The original agent used custom Git tools. Harbor agents work in a shell, so that section of the prompt is replaced by a note on where the checkout is and how to conclude the merge. The rest of the prompt is unchanged.
- **Scoring**: Same tree comparison as the original. The adapter also requires both merge parents in the branch history, so committing the right files without merging does not count.
- **Verifier**: Reads the commits directly from the object store, so Git configuration, hooks or replacement refs left by the agent do not affect grading. It runs in the task container, where the agent has root, so it does not protect against a replaced `git` or `python3` binary.
- **No ground truth in the image**: The image holds only the history the scenario needs, and the agent can reach model APIs only. With open internet access an agent could fetch the merge commit from GitHub.
- **Unlisted conflicts**: `micrometer-metrics-micrometer-merge-0054` and `mockito-mockito-merge-0002` each have one more conflict that the dataset does not list, a file modified on one side and deleted on the other. It is recorded in `task.toml` under `metadata.unlisted_conflict_files`.
- **Build time**: Images fetch repository history from GitHub at build time. Large repositories take several minutes and a few GB of disk; the tasks request 10 GB.
- **Git version**: The image uses Git 2.39 from Debian bookworm. Other versions can produce slightly different conflict hunks.

## Installation / Prerequisites

- Python 3.13+ and `uv` (dependencies are installed automatically by `uv run`)
- `git`, and access to GitHub and HuggingFace for task generation and image builds
- Docker installed and running, or a cloud environment such as Daytona
- An environment that supports per-phase network policies: Docker on Linux, OrbStack, Daytona, E2B or Modal
- Harbor 0.21.0 or newer; 0.26.0 or newer to run mini-swe-agent
- API keys for the evaluated agent and model

## Troubleshooting

- **`could not fetch <commit>` during generation or image build**: GitHub is unreachable or rate limiting; re-run. If the commit was removed upstream, the sample cannot be built.
- **`network_mode='allowlist' is not supported by docker environment`**: Docker Desktop for macOS lacks the kernel support Harbor's egress control needs. Use OrbStack, a Linux host or Daytona (`-e daytona`).
- **Agent cannot reach its model API**: Only `api.anthropic.com` and `api.openai.com` are allowed during the agent phase; pass `--allow-agent-host <host>` for other providers.
- **A trial scored 0**: `verifier/details.json` in the trial directory records the branch head, missing merge parents, the committed tree id and any leftover conflict markers.

## Citation

```bibtex
@inproceedings{lindenbauer-etal-2025-gitgoodbench,
    title = "{G}it{G}ood{B}ench: A Novel Benchmark For Evaluating Agentic Performance On Git",
    author = "Lindenbauer, Tobias  and
      Bogomolov, Egor  and
      Zharov, Yaroslav",
    booktitle = "Proceedings of the 1st Workshop for Research on Agent Language Models (REALM 2025)",
    month = jul,
    year = "2025",
    address = "Vienna, Austria",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2025.realm-1.19/",
    doi = "10.18653/v1/2025.realm-1.19",
    pages = "272--288"
}
```

## Authors & Contributions

This adapter is developed and maintained by [Wenting Yang](mailto:yanggwendy0213@gmail.com).

**Issues and Contributions:**

- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines

## Acknowledgement

API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
