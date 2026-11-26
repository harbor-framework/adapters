# AxionLimitBench → Harbor Adapter

## Overview

AxionLimitBench asks an agent to read a particle-physics paper and extract the experimental exclusion limit it reports, as a curve of (mass, coupling) points in a fixed convention.

- **Task type**: scientific data extraction from a PDF, with unit and convention handling
- **Adapted size**: 289 tasks, one per paper. The original benchmark lists 292 scorable papers; three are excluded because its scorer cannot grade any answer for them (see Notes & Caveats)
- **Provenance**: [paper](https://doi.org/10.5281/zenodo.22880507) | [code and data](https://github.com/FaroutYLq/AxionLimitBench) | [mirror with transcripts](https://huggingface.co/datasets/FaroutYLq/AxionLimitBench)
- **Pins**: benchmark at commit `08e634dacf9e98632b6faa1c21338fb77294b83f` (tag `v0.1.3`). Each paper's PDF is pinned to one arXiv version and one SHA256. All of these are recorded in every generated task
- **License**: MIT for the benchmark. The reference curves come from the AxionLimits compilation (MIT). The papers are not redistributed
- **Modifications**: the scoring code is unchanged. The benchmark's own name is removed from the text the agent sees. Notes & Caveats lists every adaptation

## What is AxionLimitBench?

AxionLimitBench (Yuan, 2026) tests whether an AI system can do the work of a physicist who curates a public compilation of dark-matter limits. For each paper the system must decide whether the paper reports a new measured limit, name the coupling it constrains (13 types, such as the axion-photon coupling or the dark-photon kinetic mixing), and return the boundary of the excluded region in canonical units.

The answer is graded against the curve that the maintainer of the AxionLimits compilation digitised for the same paper. The headline metric is the success rate: an answer succeeds when its median distance from the reference is within 10 percent (0.041 dex). Abstentions, a wrong coupling type and unconvertible units all count as misses.

The reference agent is one headless Claude Code session per paper. On the benchmark's leaderboard it reaches 56% with Claude Fable 5, 47% with Claude Opus 4.8 and 9% with Claude Haiku 4.5.

## Adapter Features

- One Harbor task per gradable paper. Task names come from the arXiv identifier: `2208-07293`, `hep-ph-0307284`
- Grades with the benchmark's own `scorer` package, copied unchanged into each task's verifier
- Grades in a separate verifier container. The agent's container holds the paper and a Python environment, and nothing else from the benchmark
- Fetches each paper at image build time from the public arXiv mirror, at a pinned version, and checks its SHA256. No PDF is stored in the task
- Restricts the agent's network to `arxiv.org`, so it can fetch the paper's own e-print as the task card allows, and cannot reach the compilation that holds the reference curves. The verifier has no network access
- Builds every oracle answer from the reference curve and checks it with the scorer while generating the task
- `--split parity` generates the 30-task parity subset

## Generated Task Structure

```
axionlimitbench/
└── <arxiv-id>/                     # e.g. 2208-07293
    ├── task.toml                   # separate verifier, network policy, artifact path, pins
    ├── instruction.md              # the original user prompt and task card
    ├── environment/
    │   └── Dockerfile              # agent image: Python stack, then the pinned paper.pdf
    ├── solution/
    │   ├── solve.sh                # oracle: copies result.json to /app/result.json
    │   └── result.json             # the reference curve in the canonical plane
    └── tests/
        ├── Dockerfile              # verifier image: numpy and scipy, plus the files below
        ├── test.sh                 # runs score.py and writes the reward
        ├── score.py                # single-paper entry point for the scorer
        ├── scorer/                 # the benchmark's scorer package, unchanged
        ├── task.json               # the arXiv identifier of this task
        └── data/
            ├── papers.json         # the reference entries of this paper only
            └── ground_truth/       # the reference curve files of this paper only
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the dataset is published:

```bash
harbor run -d FaroutYLq/axionlimitbench -a oracle
harbor run -d FaroutYLq/axionlimitbench -a <agent> -m "<model>"
harbor run -d FaroutYLq/axionlimitbench@parity -a <agent> -m "<model>"   # 30-task parity subset
```

### Using Job Configurations

```bash
# From the adapters repository root
harbor run -c src/axionlimitbench/run_axionlimitbench.yaml

# Or point at a generated dataset directory
harbor run -p datasets/axionlimitbench -a oracle
```

### Running Individual Trials

```bash
harbor trial start -p datasets/axionlimitbench/2208-07293 -a oracle
```

## Usage: Create Task Directories

```bash
cd src/axionlimitbench
uv sync
uv run axionlimitbench --output-dir ../../datasets/axionlimitbench
uv run axionlimitbench --split parity --output-dir ../../datasets/axionlimitbench-parity
```

Flags:

- `--output-dir`: destination directory, default `datasets/axionlimitbench`
- `--limit`: generate only the first N tasks
- `--overwrite`: replace existing task directories
- `--task-ids`: generate only the listed tasks. Accepts the task name (`2208-07293`) or the arXiv identifier (`2208.07293`)
- `--split`: `full` (default) or `parity` (30 tasks)
- `--repo-dir`: a checkout of the benchmark at the pinned commit

Without `--repo-dir` the adapter clones the benchmark at the pinned commit into `~/.cache/axionlimitbench-adapter`. Generation needs `git`, and it imports the benchmark's scorer, so `numpy` and `scipy` are dependencies of the adapter.

## Comparison with Original Benchmark (Parity)

### Oracle

The oracle writes the reference curve, in the canonical plane, to `/app/result.json`. Every result below is from Harbor 0.27.0 with the separate verifier, on local Docker (arm64).

| Check | Tasks | Result |
|-------|-------|--------|
| Oracle, full dataset | 289 | 289 with reward 1, 0 exceptions |
| No agent action (`nop`) | 4 | 4 with reward 0: the result file is missing |
| Reference curve scaled by 1.05 (0.021 dex away) | 1 | reward 1 |
| Reference curve scaled by 1.5 (0.176 dex away) | 1 | reward 0 |
| Right curve declared as `chi^2`, with squared values | 1 | reward 1: the scorer converts it |
| Wrong coupling type | 1 | reward 0: `no_comparable_gt` |
| Abstention (`is_new_limit: false`, no points) | 1 | reward 0: `no_prediction` |

The full run took 54 minutes for 288 tasks at four trials at a time, plus 22 minutes for `2503-14582`, whose reference has 224,124 vertices.

### Parity

Parity experiments have not been run yet. The table will be filled in when they are.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| pending | pending | success rate at 10% | 0 | 30 | pending | pending |

Plan:

- **Agent**: Claude Code on both sides. The original benchmark's reference agent already is Claude Code, started by `baselines/agent_claude_code/run_agent.py`
- **Subset**: the 30 tasks in `src/axionlimitbench/parity_task_ids.txt`. They are drawn per coupling type in proportion to the type's share of the dataset, from the sorted task names, with `random.Random(20261125)`
- **Runs**: three per side, reported as mean ± sample SEM
- **Metrics**: success rate at 10% (the reward), plus the median residual of compared papers

Reproduction:

```bash
# Harbor side
cd src/axionlimitbench
uv run axionlimitbench --split parity --output-dir ../../datasets/axionlimitbench-parity
harbor run -p ../../datasets/axionlimitbench-parity -a claude-code -m "<model>"

# Original side, in the original repository at the pinned commit
python3 data/fetch_pdfs.py --out ~/axlb_pdfs
python3 baselines/agent_claude_code/run_agent.py --outdir results/agent_claude_code/<run> --model <model> --workers 3
python3 -m scorer.score --snapshots results/agent_claude_code/<run> --report
```

## Notes & Caveats

- **Three papers are not adapted.** `2312.11608`, `2402.00741` and `2504.16044` are in the benchmark's list of 292 scorable papers, but its scorer returns `excluded_gt` or `gt_unusable` for every answer to them. The benchmark's leaderboard removes papers with these statuses from its denominator. A Harbor task whose reward can never be 1 would be misleading, so the adapter leaves them out, and it stops with an error if this list ever disagrees with what the scorer reports
- **The reward is the benchmark's headline metric for one paper.** It is 1 when the scorer compares the answer and the median residual is at most log10(1.1) dex, and 0 otherwise. The verifier also writes the residual, the comparison status and the coupling-type check to `score.json` in its log directory
- **The benchmark's name is hidden from the agent.** The task card's title line and the first line of the user prompt named the benchmark; both are reworded. The rest of the task card is verbatim. It still names the AxionLimits compilation, because the card defines the goal as the curve that compilation would hold. The network policy keeps the agent from reaching it
- **The task card is part of the instruction.** The original driver appends it to Claude Code's system prompt and sends a short user prompt. Harbor gives every agent one instruction, so the user prompt and the card are joined there
- **Network.** The original driver lets Claude Code use `WebFetch`, denies a list of domains and audits each transcript afterwards. The adapter enforces a narrower rule instead: only `arxiv.org` and `export.arxiv.org` are reachable while the agent runs. Harbor also disables an agent's built-in web tools under a restricted network, so the agent fetches the e-print with `curl` or Python
- **Paper versions.** The original `fetch_pdfs.py` downloads whatever version arXiv serves that day. The adapter pins the latest version present in the public `arxiv-dataset` mirror on 2026-11-25 and records its SHA256. The benchmark notes that some reference curves were digitised from an earlier version of a paper
- **Oracle answers.** The oracle is the reference curve converted to the canonical plane with the scorer's own conversion for reference files. For 284 papers it is the complete reference. For three references with more than 5,000 vertices it is thinned to at most 5,000 points. For `2105.13963`, whose reference is stored as a closed contour, it is the upper branch. For `2503.14582`, a noisy reference with 224,124 vertices, it keeps every vertex, because no reduced curve stays within the tolerance; grading a full-resolution answer for that paper takes about 21 minutes, so its verifier timeout is 3600 seconds, and generating that task takes about as long because the adapter checks the oracle
- **Time limit.** The benchmark sets no cap. The agent timeout is 1800 seconds, the wall clock of the benchmark's reference runs
- **Known limits of the benchmark.** Reference curves are single hand digitisations, so residuals below about 0.1 dex are not meaningful, and a correct extraction can miss the 10 percent tolerance. The reference files are public on GitHub

## Installation / Prerequisites

- Docker
- Harbor CLI (`uv tool install harbor`). The results in this README were produced with Harbor 0.27.0
- Python 3.11 or later, `uv` and `git`:
  ```bash
  cd src/axionlimitbench
  uv sync
  ```

## Troubleshooting

- **The image build fails at the PDF step.** The build downloads the paper from `storage.googleapis.com` and checks its SHA256. Check that the build host can reach that address
- **The agent cannot download the e-print.** The environment must support Harbor's `allowlist` network mode. On local Docker this needs the nftables kernel features that Harbor's egress sidecar uses
- **`A different scorer package is already imported`.** Run the adapter in a fresh process

## Citation

```bibtex
@misc{yuan2026axionlimitbench,
  title  = {AxionLimitBench: can AI curate a dark matter constraint repository?},
  author = {Yuan, Lanqing},
  year   = {2026},
  doi    = {10.5281/zenodo.22880507},
  url    = {https://doi.org/10.5281/zenodo.22880507}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Jianghao Zhang](mailto:jianghz@umich.edu) ([@jianghao-zhang](https://github.com/jianghao-zhang)).

Issues and pull requests are welcome in the adapters repository.
