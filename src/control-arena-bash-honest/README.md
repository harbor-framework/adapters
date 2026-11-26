# ControlArena Bash Honest

## Overview

Generate three standalone Harbor tasks from the Bash setting in ControlArena 20.1.1. They exercise identifier sorting (`256989`), checking Python class names (`409382`), and extracting string components (`604648`). Each case uses its original prompt and public pytest file from the release wheel. [Suite coverage](../../docs/control-arena.md)

## What is ControlArena Bash?

The native setting evaluates shell scripting against tasks derived from Stack Overflow. Its full release catalog has 257 main tasks. This package evaluates the honest main-task outcome for the three listed IDs. [Native setting](https://control-arena.aisi.org.uk/settings/bash.html)

## Adapter Features

The agent starts with the native public tests in `/workspace`. Harbor collects the submitted script from `/workspace/solution.sh`. A separate verifier runs a fresh copy of those tests as an unprivileged user, with a 30-second deadline. Its named binary reward is `main_task_success`. Both runtime containers run without network access.

## Generated Task Structure

`instruction.md` and `task.toml` define the task. The `environment/` image includes Bash, Python and the public tests. The `tests/` image includes the scorer. When given a private oracle directory, the generator also creates `solution/` with the supplied reference program.

## Usage: Create Task Directories

From `src/control-arena-bash-honest`, install the locked project and generate all three tasks.

```bash
uv sync --locked
uv run control-arena-bash-honest --output-dir datasets/control-arena-bash-honest
```

Use `--task-ids bash-604648` to select a particular case, `--limit N` to bound generation, and `--overwrite` to regenerate. The upstream dataset ships tests but provides no reference script for these cases. To enable Harbor's oracle agent, provide a local directory containing a `<source-id>.sh` reference for each selected case.

```bash
uv run control-arena-bash-honest --output-dir datasets/control-arena-bash-honest \
  --oracle-dir /private/bash-oracles --overwrite
```

## Run Evaluation / Harness

After supplying the private scripts, run the oracle job. Run any individual task by passing its directory to Harbor.

```bash
uv run harbor run -c run_control-arena-bash-honest.yaml
uv run harbor run -p datasets/control-arena-bash-honest/bash-604648 -a oracle
```

## Comparison with Original Benchmark (Parity)

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
| --- | --- | --- | ---: | ---: | --- | --- |
| Honest | Pending | Main-task success | 0 live | 3 | Pending | Pending |

Use the same case IDs, agent, model snapshot and budget for native and Harbor runs. Compare the per-case verdicts before aggregating accuracy. The native main scorer runs the release's `task_verifiable` pytest suite and checks its success sentinel. The Harbor verifier runs the same suite and reads pytest's exit status. [Pinned native scorer](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/control_arena/settings/bash/task/scorers.py)

The three private reference scripts each earned 1 in a Harbor Docker oracle run. The original five pytest checks passed in each task. A script that immediately exits with failure earned 0 on each of the three tasks in a separate Harbor job. To reproduce the Harbor check, provide local reference files and run the following commands.

```bash
uv run control-arena-bash-honest --output-dir datasets/control-arena-bash-honest --oracle-dir /private/bash-oracles
uv run harbor run -c run_control-arena-bash-honest.yaml
```

## Notes & Caveats

The native Inspect agent uses a submit tool in an Alpine sandbox. Harbor collects the executable file from a Debian-based workspace. Script permissions are normalized after artifact transfer. A timeout or pytest infrastructure error interrupts verification. Generate references locally and keep them in protected storage. [Upstream data guidance](https://github.com/UKGovernmentBEIS/control-arena/tree/v20.1.1#avoiding-data-contamination)

## Installation / Prerequisites

Install uv and Docker with Linux containers. Task generation reads the pinned ControlArena wheel. Building the images initially requires access to their base image and pytest.

## Troubleshooting

Inspect `verifier/test-stdout.txt` in the trial directory for pytest failures. An oracle job requires a task generated with `--oracle-dir`.

## Citation

See the [ControlArena release citation](https://github.com/UKGovernmentBEIS/control-arena/tree/v20.1.1#citation) and the [Bash setting documentation](https://control-arena.aisi.org.uk/settings/bash.html).

```bibtex
@misc{inglis2025controlarena,
  title = {ControlArena},
  author = {Inglis, Rogan and others},
  year = {2025},
  url = {https://github.com/UKGovernmentBEIS/control-arena}
}
```

## Authors & Contributions

The ControlArena and CTRL-Z contributors developed the benchmark. This Harbor adapter was prepared by lijingxian.
