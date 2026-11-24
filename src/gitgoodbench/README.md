# GitGoodBench → Harbor Adapter

## Overview

GitGoodBench is a benchmark of Git tasks mined from open-source Python, Java and Kotlin repositories. This adapter converts its three scenarios into Harbor format:

- **Merge conflict resolution**: a real merge was started and stopped on its conflicts. The agent resolves them and concludes the merge. The result must match the merge commit of the original developer exactly.
- **Interactive rebase**: the agent gets the last 3 to 6 commits of a branch, with an interactive rebase of them started and paused, and cleans them up: it can meld, drop, reword and reorder commits.
- **Iterative committing**: the agent gets the changes of such commits uncommitted, as patch files, and splits them into a series of small commits.

The last two have no single right answer. An LLM judge compares the agent's history with the original developer's. It sees the two histories twice, with their positions swapped, and the task is solved only if it prefers the agent's history both times.

GitGoodBench builds the three scenarios from two sample types, in two evaluation sets that do not overlap. A `file_commit_chain` sample is used by both judge-scored scenarios.

| Scenario | Sample type | Scoring | Lite | Lite converted | Full | Full converted |
|----------|-------------|---------|------|----------------|------|----------------|
| Merge conflict resolution | `merge` | Exact match | 60 | 60 | 450 | 445 |
| Interactive rebase | `file_commit_chain` | LLM judge | 60 | 59 | 450 | 449 |
| Iterative committing | `file_commit_chain` | LLM judge | 60 | 59 | 450 | 449 |

The size of the adapted benchmark is 178 tasks: GitGoodBench Lite, the set the paper reports its baseline on, without one `file_commit_chain` sample that the original harness cannot set up. The full dataset can be generated with `--split full`, which gives 1,343 tasks. They pass the oracle, are not registered and have no parity run. The excluded samples are listed under [Notes & Caveats](#notes--caveats).

We follow the original evaluation. The adapter differs from the original benchmark in these points, each described under [Notes & Caveats](#notes--caveats):

- Agents work in a shell instead of the original custom tools.
- The ground truth is not in the task image, and the agent can reach model APIs only.
- The merge verifier also requires both merge parents in the history of the branch.
- For the judge-scored scenarios the oracle is the original history, which the judge can only call a tie. Oracle runs set `ORACLE_MODE=true`, which counts this tie as solved. Agents are graded by the rule of the paper.

## What is GitGoodBench?

GitGoodBench ([paper](https://aclanthology.org/2025.realm-1.19/), [repository](https://github.com/JetBrains-Research/git-good-bench)) is a benchmark by JetBrains Research, presented at REALM 2025 (co-located with ACL 2025). It tests agents on version-control workflows, which benchmarks such as SWE-bench leave out. For a GPT-4o baseline with custom tools the paper reports solve rates on Lite of 13.33% for merge conflict resolution, 26.67% for interactive rebase and 23.33% for iterative committing, 21.11% overall.

- Metric: solve rate (exact match against the ground-truth merge commit, or the LLM judge preferring the agent's history twice)
- Source: https://huggingface.co/datasets/JetBrains/git_good_bench-lite
- License: Apache-2.0 for the dataset; Apache-2.0, MIT or BSD for the source repositories

## Adapter Features

- Converts GitGoodBench Lite into 178 tasks: one per `merge` sample, two per `file_commit_chain` sample
- Rebuilds each scenario like the original harness: the merge stopped on its conflicts, the interactive rebase paused before its first commit, or the changes in `file_changes.patch` and `all_changes.patch`
- Instructions are the original prompts with the scenario context quoted (conflict hunks, commits of the rebase, hunks to commit); the section on the custom tools is replaced by how to work in the checkout
- Ground truth removed from the image, and agent network limited to model APIs
- Verifiers as in the original `Evaluator`, running in their own container: exact match for merges, the original LLM judge prompt for the other two scenarios
- Oracle solution for every task (178/178 on Lite, 1,343/1,343 on the full dataset)

## Generated Task Structure

```
gitgoodbench/
├── spulec-freezegun-merge-0000/               # Merge conflict resolution
│   ├── task.toml                 # Task configuration (separate verifier, `.git` as artifact)
│   ├── instruction.md            # Original merge prompt with the conflict hunks
│   ├── environment/
│   │   ├── Dockerfile            # Python 3.12 slim image with Git
│   │   ├── setup_scenario.py     # Builds the merge scenario at image build time
│   │   └── scenario.json         # Repository and commits of the scenario
│   ├── solution/
│   │   ├── solve.sh              # Oracle solution (commits the ground-truth merge)
│   │   └── ground_truth.bundle   # Ground-truth merge commit as a Git bundle
│   └── tests/
│       ├── Dockerfile            # Verifier image (Python 3.12 slim with Git)
│       ├── test.sh               # Test runner
│       ├── evaluate.py           # Exact-match verifier
│       └── config.json           # Merge parents and ground-truth tree id
├── fepegar-torchio-file-commit-chain-0001-chunk/    # Iterative committing
│   ├── task.toml                 # Task configuration (judge settings in [verifier.env])
│   ├── instruction.md            # Original prompt with the hunks to commit
│   ├── environment/
│   │   ├── Dockerfile
│   │   ├── setup_chain.py        # Builds the scenario at image build time
│   │   ├── setup_scenario.py     # Git helpers shared with the merge setup
│   │   ├── scenario.json
│   │   ├── file_changes.patch    # Changes to the file of the scenario
│   │   └── all_changes.patch     # Changes to the other files
│   ├── solution/
│   │   ├── solve.sh              # Oracle solution (the original commits)
│   │   └── ground_truth.bundle   # The original commits as a Git bundle
│   └── tests/
│       ├── Dockerfile            # Verifier image, fetches the original commits
│       ├── fetch_ground_truth.py
│       ├── test.sh
│       ├── evaluate_history.py   # Renders both histories and asks the judge
│       ├── judge.py              # Original judge prompts, chat completions client
│       ├── evaluate.py           # Helpers shared with the merge verifier
│       └── config.json           # The two ends of the original history
├── fepegar-torchio-file-commit-chain-0001-rebase/   # Interactive rebase
│   ├── instruction.md            # Original prompt with the commits of the rebase
│   ├── solution/solve.sh         # Oracle solution (continues the rebase unchanged)
│   └── ...                       # As above, without patch files and bundle
└── ...
```

Task names follow `jetbrains/gitgoodbench__<task-id>`, for example `jetbrains/gitgoodbench__spulec-freezegun-merge-0000`. The task id is the sample id, followed by `-chunk` (iterative committing) or `-rebase` (interactive rebase) for the two tasks of a `file_commit_chain` sample.

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
│   ├── reference-harness-file-commit-chain.patch   # Its support for the two judge-scored scenarios
│   └── results/                        # Raw parity and oracle results
├── tests/                              # Unit tests for the generator and the verifier
└── src/gitgoodbench/
    ├── adapter.py                      # Main adapter code
    ├── main.py                         # CLI entry point
    ├── task-template/                  # Task template of the merge scenario
    │   ├── task.toml
    │   ├── instruction.md
    │   ├── environment/
    │   │   ├── Dockerfile
    │   │   └── setup_scenario.py
    │   ├── solution/solve.sh
    │   └── tests/
    │       ├── Dockerfile
    │       ├── test.sh
    │       └── evaluate.py
    └── task-template-file-commit-chain/    # Task template of the two judge-scored scenarios
        ├── task.toml
        ├── instruction-rebase.md
        ├── instruction-chunk.md
        ├── environment/
        │   ├── Dockerfile
        │   └── setup_chain.py
        ├── solution/
        │   ├── solve-rebase.sh
        │   └── solve-chunk.sh
        └── tests/
            ├── Dockerfile
            ├── fetch_ground_truth.py
            ├── test.sh
            ├── evaluate_history.py
            └── judge.py
```

## Run Evaluation / Harness

### Using Registry (after publishing)

```bash
# Run on entire dataset with the oracle
ORACLE_MODE=true harbor run -d jetbrains/gitgoodbench

# Run on entire dataset with an agent (OPENAI_API_KEY is for the LLM judge)
export OPENAI_API_KEY="your_api_key"
harbor run -d jetbrains/gitgoodbench -a <agent-name> -m <model-name>

# Run single task
harbor run -t jetbrains/gitgoodbench__spulec-freezegun-merge-0000 -a <agent-name> -m <model-name>
```

### Using Job Configuration

```bash
ORACLE_MODE=true harbor run -c src/gitgoodbench/run_gitgoodbench.yaml
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

The interactive rebase and iterative committing tasks are graded by an LLM judge, which the verifier calls through an OpenAI-compatible chat completions API. Set these in the environment of `harbor run`:

| Variable | Required | Meaning |
|----------|----------|---------|
| `OPENAI_API_KEY` | For agent runs | API key of the judge |
| `OPENAI_BASE_URL` | No | Endpoint of the judge (default `https://api.openai.com/v1`) |
| `JUDGE_MODEL` | No | Judge model (default `gpt-4o`, the model of the paper's baseline) |
| `ORACLE_MODE` | For oracle runs | `true` counts the original history as solved without asking the judge |

The merge tasks need none of them.

## Usage: Create Task Directories

```bash
cd src/gitgoodbench

# Generate all 178 tasks into datasets/gitgoodbench
uv run gitgoodbench

# Generate a subset
uv run gitgoodbench --limit 10

# Generate specific tasks
uv run gitgoodbench --task-ids spulec-freezegun-merge-0000

# Generate one scenario: merge, rebase (interactive rebase) or chunk (iterative committing)
uv run gitgoodbench --scenario-types merge
```

Other flags: `--output-dir`, `--overwrite`, `--dataset-path` (load samples from a local export) and `--split full` (the 1,343 tasks of the full dataset, written to `datasets/gitgoodbench-full`).

## Comparison with Original Benchmark (Parity)

The baseline agent of the paper cannot be run: its LLM client, agent loop and data source were removed from the released code, which the benchmark's first author confirmed. The original side of the parity experiment is therefore a reference harness that adds those pieces back and runs a standard CLI agent in the original scenario container, with the original scenario setup and scoring. [`parity/README.md`](parity/README.md) describes the harness and the differences between the two sides.

The parity runs cover the 60 merge tasks. Both sides ran mini-swe-agent 2.4.6 with `deepseek-v4-1-flash-260910`, 3 runs over these tasks. The reference harness also runs the interactive rebase and iterative committing scenarios, with the same prompts and the same judge module as the Harbor tasks; their parity runs are not done yet.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| mini-swe-agent@2.4.6 | deepseek-v4-1-flash-260910 | Solve rate (%) | 3 | 60 (100%) | 40.56 ± 2.0031 | 41.67 ± 0.9623 |

Per-run solve rates: original 36.67, 41.67, 43.33; Harbor 40.00, 43.33, 41.67. The ranges overlap, and 52 of the 60 tasks have the same outcome in all runs on both sides.

Links:
- Original benchmark: [JetBrains-Research/git-good-bench](https://github.com/JetBrains-Research/git-good-bench) at `b11ae6cd92be2b8b96e237d379427e04ad59c455`
- Reference harness: [YanggWendy/git-good-bench](https://github.com/YanggWendy/git-good-bench/tree/harbor-parity), branch `harbor-parity`. The parity runs used commit [`0375616`](https://github.com/YanggWendy/git-good-bench/tree/0375616a91a58e495b370908918d01991bc6ebf4); the two judge-scored scenarios were added to the harness afterwards
- [Adapter PR](https://github.com/harbor-framework/adapters/pull/78) and [dataset PR](https://github.com/harbor-framework/harbor-datasets/pull/277)
- Parity results: [HuggingFace parity-experiments PR](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/281). The shared repository is over the Hub's file limit and does not accept uploads at the moment, so the files are at [yanggwendy/gitgoodbench-parity](https://huggingface.co/datasets/yanggwendy/gitgoodbench-parity/tree/main/adapters/gitgoodbench) in the same layout.

### Oracle Verification

Run on Daytona with Harbor 0.27.0 and `ORACLE_MODE=true`:

| Split | Merge | Interactive rebase | Iterative committing | Total |
|-------|-------|--------------------|----------------------|-------|
| Lite, the registered dataset | 60/60 | 59/59 | 59/59 | 178/178 (100%) |
| Full, `--split full` | 445/445 | 449/449 | 449/449 | 1,343/1,343 (100%) |

In the run of the full dataset, 21 trials were interrupted while the machine that drove the run was asleep and were run again with `harbor jobs resume`. One task, `mihonapp-mihon-file-commit-chain-0000-rebase`, ran in a second job with `--ek auto_snapshot=true`, because Daytona had cancelled its image build and kept returning that result.

For a merge task the oracle commits the ground-truth merge result. For the other two scenarios the reference is the history the original developer pushed: the oracle of an interactive rebase task executes the todo list as it is, and the oracle of an iterative committing task puts the original commits on the branch. The judge can only call that history a tie, which the rule of the paper scores as unsolved. The benchmark's first author [agreed](https://github.com/harbor-framework/harbor/pull/3327#issuecomment-5905634867) that a tie may count as solved. With `ORACLE_MODE=true` the verifier accepts a history made of exactly the original commits without asking the judge. Without it every history goes to the judge, which is how agents are graded.

The oracle also passes on the original side: 60/60 merge samples and both scenarios of the 59 `file_commit_chain` samples, the latter with the same tie rule (`--oracle-mode`).

Ten negative controls on `spulec-freezegun-merge-0000` all score 0: an untouched merge, a wrong resolution, the ground-truth commit put on the branch without concluding the merge, four kinds of forged Git history, a reward file written by the agent (with and without Git deleted), and `git` and `python3` replaced in the agent's container. The result files are in `parity/results/`. The controls on the repository state also run as unit tests, and so do the controls of the judge-scored verifier, with the judge replaced by fixed answers: `uv run --with pytest pytest tests` in `src/gitgoodbench`.

### Reproduction

```bash
export OPENAI_API_KEY="your_api_key"
export OPENAI_BASE_URL="your_openai_compatible_endpoint"

# Harbor side: generate the merge tasks, then 3 attempts on Daytona
cd src/gitgoodbench && uv run gitgoodbench --scenario-types merge && cd ../..
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

- **Shell instead of custom tools**: The original agent used custom Git tools. Harbor agents work in a shell, so that section of each prompt is replaced by a note on where the checkout is and how to complete the task with Git. The rest of the prompt is unchanged. For interactive rebase the note describes `reword` and `squash` the way the original tool executes them (`pick` or `fixup` followed by `exec git commit --amend -m`), because no editor is available. For iterative committing it names the two patch files and the commands the original tools run.
- **Merge scoring**: Same tree comparison as the original. The original also runs `git status` and fails the scenario when it reports unmerged paths or a conflict; the verifier checks the same state in the index and the merge state files. In addition the adapter requires both merge parents in the branch history, so committing the right files without merging does not count.
- **Judge scoring**: Same prompt and rule as the original `Evaluator`. Both histories are rendered with `git show`, newest commit first; for iterative committing only the changes to the file of the scenario are shown. The agent's history is every commit of `current-scenario-branch` down to the commit the scenario started from. An interactive rebase that is still in progress is unsolved. As in the original, nothing checks that the agent's commits contain all the changes; the judge is the only criterion.
- **Judge model**: The paper does not name a judge model. The released code uses one LLM client for the agent and the judge, and the baseline is GPT-4o, so `JUDGE_MODEL` defaults to `gpt-4o`. The request uses temperature 0 and the response schema of the original. If the judge cannot be reached or gives no verdict, the verifier writes no reward and the trial ends with an error.
- **`ORACLE_MODE`**: Only for oracle runs, see [Oracle Verification](#oracle-verification). In an agent run it would let an interactive rebase that changes nothing pass.
- **Verifier**: Runs in its own container with its own Git and Python (`environment_mode = "separate"`). It receives the `.git` directory the agent left, saved as `artifacts/repo.git` in the trial directory, and reads the commits directly from the object store, so Git configuration, hooks or replacement refs left by the agent do not affect grading. For the judge-scored tasks the verifier image fetches the original commits from GitHub when it is built and shows them to the judge without the agent's objects.
- **No ground truth in the image**: The image holds only the history the scenario needs, and the agent can reach model APIs only. With open internet access an agent could fetch the merge commit or the original commits from GitHub. An iterative committing image never contains the original commits: the two patch files are written when the task is generated. In an interactive rebase task the original commits are the agent's input.
- **Conflicts checked at build time**: The generator replays each merge to quote its conflict hunks in the instruction. The image build runs the merge again and fails if its hunks differ from the quoted ones, so the agent always finds the conflicts its instruction describes.
- **Excluded samples**: Seven samples are not converted (`EXCLUDED_SAMPLES` in `adapter.py`), one of them in Lite. `coil-kt-coil-file-commit-chain-0003` (Lite): the working tree is modified right after a checkout, because the repository asks for a line-ending conversion of binary files, so the original harness cannot start the rebase and its patch files contain unrelated changes. `elastic-elasticsearch-hadoop-file-commit-chain-0001` (full): its changes are not valid UTF-8, which the original harness cannot read. Five `merge` samples of the full dataset: For `alluxio-alluxio-merge-0000`, `pinterest-teletraan-merge-0003` and `spring-projects-spring-security-merge-0036`, Git produces fewer conflict hunks than the dataset records (1 instead of 2, 2 instead of 5, 5 instead of 6, with Git 2.39 and 2.50). `apache-sedona-merge-0000` lists files that are not in conflict. The repository of `microsoft-olive-merge-0000` is no longer on GitHub.
- **Patch files**: The original harness writes `file_changes.patch` and `all_changes.patch` in a checkout. The generator computes the same patches from the commits. For the 508 converted `file_commit_chain` samples, 59 in Lite and 449 in the full dataset, they were compared with what the original commands write on Linux with Git 2.39 in a repository with the same commits, and they are byte for byte identical. The commits quoted in the interactive rebase instructions were compared with `git show` in the same way.
- **Abbreviated ids**: Git chooses the length of abbreviated object ids by the number of objects in the repository. A task image holds only the commits of its scenario, so `index` lines and the rebase todo list show 7 characters where a full clone of a Lite repository shows up to 10.
- **Samples without hunks**: In `montrealcorpustools-montreal-forced-aligner-file-commit-chain-0000` the file of the scenario ends as it started, so its iterative committing task lists 0 hunks, as the original prompt does. The full dataset has two more such samples.
- **Long instructions**: An interactive rebase instruction quotes every commit of the rebase, up to 88 KB in Lite. In the full dataset 4 instructions are longer than 128 KB (`apache-groovy-file-commit-chain-0000`, both tasks, and the rebase tasks of `apache-iceberg-file-commit-chain-0003` and `mekanism-mekanism-file-commit-chain-0005`). That is more than one command line argument can hold on Linux, so agents that receive the instruction as an argument cannot start on them.
- **Repository layout**: The history that exists before the agent starts is kept in `/opt/scenario/history.git`, and the repository borrows it through Git alternates. Its `.git` then holds only what the agent adds, which keeps the artifact small. Git commands behave the same.
- **Changes after the parity runs**: The separate verifier, the `git status` check and the repository layout of the merge tasks were added on 2026-11-22. The parity runs were graded by the earlier verifier inside the task container. [`parity/README.md`](parity/README.md) lists what changed and why the recorded verdicts are unaffected.
- **Unlisted conflicts**: `micrometer-metrics-micrometer-merge-0054` and `mockito-mockito-merge-0002` each have one more conflict that the dataset does not list, a file modified on one side and deleted on the other. It is recorded in `task.toml` under `metadata.unlisted_conflict_files`. In the full split 25 tasks have such an entry.
- **Build time**: Images fetch repository history from GitHub at build time. Large repositories take several minutes and a few GB of disk; the tasks request 10 GB.
- **Git version**: The images use Git 2.39 from Debian bookworm. Other versions can produce slightly different conflict hunks.

## Installation / Prerequisites

- Python 3.13+ and `uv` (dependencies are installed automatically by `uv run`)
- `git`, and access to GitHub and HuggingFace for task generation and image builds
- Docker installed and running, or a cloud environment such as Daytona
- An environment that supports per-phase network policies: Docker on Linux, OrbStack, Daytona, E2B or Modal
- Harbor 0.27.0 or newer. The tasks use a separate verifier and were verified with this release
- API keys for the evaluated agent and model, and `OPENAI_API_KEY` for the LLM judge of the interactive rebase and iterative committing tasks

## Troubleshooting

- **`could not fetch <commit>` during generation or image build**: GitHub is unreachable or rate limiting; re-run. If the commit was removed upstream, the sample cannot be built.
- **`network_mode='allowlist' is not supported by docker environment`**: Docker Desktop for macOS lacks the kernel support Harbor's egress control needs. Use OrbStack, a Linux host or Daytona (`-e daytona`).
- **Image build fails with `The conflict hunks in the image differ`**: The Git in the image cut the conflicts differently from the Git that generated the task. Regenerate the task, and report the sample if the error stays.
- **`OPENAI_API_KEY is not set, the LLM judge cannot be asked`**: An interactive rebase or iterative committing task was graded without a key for the judge. Set `OPENAI_API_KEY` (and `OPENAI_BASE_URL`, `JUDGE_MODEL` for another endpoint or model). For an oracle run set `ORACLE_MODE=true` instead.
- **The oracle scores 0 on the judge-scored tasks**: `ORACLE_MODE=true` is missing, so the original history went to the judge, which calls it a tie.
- **Agent cannot reach its model API**: Only `api.anthropic.com` and `api.openai.com` are allowed during the agent phase; pass `--allow-agent-host <host>` for other providers.
- **A trial scored 0**: `verifier/details.json` in the trial directory records the branch head, an unfinished merge, missing merge parents, the committed tree id and any leftover conflict markers. For the judge-scored tasks it records both answers of the judge with their reasons, and `verifier/agent_history.txt` and `verifier/ground_truth_history.txt` are the two histories the judge compared. `artifacts/repo.git` is the `.git` directory the agent left.

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
