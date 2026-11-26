# ControlArena BigCodeBench Honest

## Overview

See the [suite coverage](../../docs/control-arena.md) for the other ControlArena settings.

Generate three Python-function tasks from the honest mode of ControlArena 20.1.1. The source is the full BigCodeBench v0.1.4 dataset, complete-prompt variant. This adapter covers 3 of the 1,140 full-set tasks.

| Upstream ID | Function to implement |
| --- | --- |
| BigCodeBench/0 | Average consecutive differences over shuffled permutations |
| BigCodeBench/1 | Count the characters in a randomly generated string |
| BigCodeBench/2 | Sort lists of sampled integers by their means |

## What is ControlArena BigCodeBench?

ControlArena uses BigCodeBench programming problems to study the usefulness and safety of oversight protocols. The main-task scorer runs the source task's Python unit tests. This package exposes that functional-correctness objective for the three listed cases. [ControlArena setting](https://control-arena.aisi.org.uk/settings/bigcodebench.html) · [BigCodeBench dataset](https://huggingface.co/datasets/bigcode/bigcodebench)

## Adapter Features

- The generator checks the upstream Parquet SHA-256, selects the three reviewed row IDs, and calls ControlArena's native honest sample converter. The source commit is `b74c0d0bf70d2c0bc459be537895cca163007f1a`. [Pinned data](https://huggingface.co/datasets/bigcode/bigcodebench/blob/b74c0d0bf70d2c0bc459be537895cca163007f1a/data/v0.1.4-00000-of-00001.parquet)
- The candidate sees the original complete prompt. One delivery instruction asks the candidate to save the code it would submit as `/logs/artifacts/solution.py`. The official signature and indentation contract apply.
- The separate verifier reconstructs `SubmitHonestArgs` and calls the pinned `main_task_success()` scorer. Its Python child runs the source tests under an unprivileged account. The candidate image contains the Python standard library. Private test metadata stays in the verifier and the canonical solution stays in the oracle directory.
- `main_task_success` is a binary reward. A correct solution passes every upstream unit test. Native scorer logs are retained in `verifier/inspect/`.

## Generated Task Structure

```text
bigcodebench-honest-1/
  instruction.md
  task.toml
  environment/Dockerfile
  solution/solve.sh
  solution/solution.py
  tests/Dockerfile
  tests/requirements.txt
  tests/grade.py
  tests/sample.json
  tests/source.json
  tests/test.sh
```

## Run Evaluation / Harness

Run from this adapter directory after generating the tasks. The default configuration runs Harbor's oracle through Docker.

```bash
uv run harbor run -c run_control-arena-bigcodebench-honest.yaml
uv run harbor run -p datasets/control-arena-bigcodebench-honest -a nop
```

For a candidate agent, pass its Harbor agent and model IDs in place of `-a nop`. The candidate and verifier sandboxes both disable network access at runtime. A model-backed agent must support a compatible inference connection.

## Usage: Create Task Directories

```bash
uv run control-arena-bigcodebench-honest --output-dir datasets/control-arena-bigcodebench-honest
uv run control-arena-bigcodebench-honest --task-ids BigCodeBench/1 --limit 1 --overwrite
```

The generator can also read a local copy of the pinned Parquet through `--source-parquet FILE`. Both the download and the local path undergo the same digest check. Short Harbor names and org-qualified IDs are accepted by `--task-ids`.

## Comparison with Original Benchmark (Parity)

The native fixture harness exercises ControlArena's honest policy, typed submit tool, and combined BigCodeBench scorer in a network-disabled Linux container. The model emits fixed answers. Both native ControlArena and six real Harbor Docker trials accepted all three canonical solutions and rejected all three fixed incorrect submissions. This check measures scorer agreement on known inputs. Live model parity is pending.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
| --- | --- | --- | ---: | ---: | --- | --- |
| Honest policy and matched Harbor agent | Pending live comparison | Main-task success | 0 | 3 | Pending | Pending |

To reproduce the native check from this package directory, supply a downloaded copy of the pinned Parquet at `$PARQUET` (absolute path). These instructions use Bash.

```bash
docker build -t bcb-honest-verifier datasets/control-arena-bigcodebench-honest/bigcodebench-honest-0/tests
mkdir -p native-logs
docker run --rm --network none \
  -v "$PWD:/adapter:ro" -v "$PARQUET:/source.parquet:ro" -v "$PWD/native-logs:/out" \
  -e PYTHONPATH=/adapter/src -e PYTHONDONTWRITEBYTECODE=1 bcb-honest-verifier \
  python /adapter/tests/native_fixtures.py --source-parquet /source.parquet --log-dir /out
```

## Notes & Caveats

The scope is honest main-task correctness for three standard-library problems. ControlArena's paired protocol safety, thresholds, and audit-budget metrics require a different experiment. The slim Python verifier image replaces BigCodeBench's full evaluation image for these three tasks. Broader task coverage would require reviewing dependencies, prompts, and execution behavior for each new task.

The public package contains generator code. Generate protected solutions, private tests, and Inspect logs locally. [ControlArena contamination guidance](https://github.com/UKGovernmentBEIS/control-arena#avoiding-data-contamination)

## Installation / Prerequisites

Install Docker and uv, then run `uv sync --locked` inside `src/control-arena-bigcodebench-honest`. The first build needs package-index access. A pre-downloaded Parquet allows offline task generation once the project dependencies are installed.

## Troubleshooting

A Parquet digest mismatch indicates a different file or revision. Retrieve the pinned v0.1.4 file linked above. For a failed submission, see the verifier's Inspect log and compare the `code` argument with the function signature in the prompt.

## Citation

Cite Zhuo et al. for BigCodeBench and Inglis et al. for ControlArena. BigCodeBench data is licensed under Apache-2.0. ControlArena is licensed under MIT. [BigCodeBench paper](https://arxiv.org/abs/2406.15877) · [ControlArena repository](https://github.com/UKGovernmentBEIS/control-arena)

```bibtex
@article{zhuo2024bigcodebench,
  title = {BigCodeBench: Benchmarking Code Generation with Diverse Function Calls and Complex Instructions},
  author = {Zhuo, Terry Yue and others},
  journal = {arXiv preprint arXiv:2406.15877},
  year = {2024}
}
```

## Authors & Contributions

Upstream benchmark by the BigCodeBench authors. ControlArena setting by the ControlArena contributors. Harbor adaptation by lijingxian.
