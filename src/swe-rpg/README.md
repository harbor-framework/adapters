# SWE-RPG → Harbor Adapter

## Overview

SWE-RPG is a repository-level issue-resolution benchmark. An agent gets a real repository at the commit before a fix and the issue that asked for it, and must change the code so that the project's own tests pass.

- **Task type**: issue resolution in real Java and Python repositories
- **Adapted size**: 163 tasks, the whole benchmark (85 Java, 78 Python, 31 repositories)
- **Provenance**: [paper](https://arxiv.org/abs/2608.09072) | [code and data](https://github.com/Xin-Zhou-smu/SWE-RPG-Bench)
- **Pins**: benchmark at commit `688ed7918cbcabe6c9d9b9f393fad1053b286dd9`; `data/benchmark.jsonl` with SHA256 `90c3f55fe74a111daad93d017d38a834136411678f0f9b03e0193cd076ef35a2`; every task image by its OCI digest. All are recorded in every generated task
- **License**: the benchmark repository has no license file
- **Modifications**: the rebuild commands, test commands, log parsers and pass rule are unchanged. Notes & Caveats lists every adaptation

## What is SWE-RPG?

SWE-RPG (Zhou et al., 2026) is built from 163 merged pull requests in 31 open-source repositories: 113 bug fixes and 50 feature additions. Each instance records the linked issue, the developers' patch, the tests that the patch makes pass, and a pinned Docker image with the repository and its dependencies.

The primary metric is the resolved rate, following the SWE-bench execution protocol. An instance is resolved when the submitted patch applies, the fail-to-pass tests pass and no pass-to-pass test regresses. The paper evaluates Claude Code, Codex and OpenCode with six models. The average resolved rate is 31.5%, and the best pairing, OpenCode with Kimi K3, reaches 49.7%.

The benchmark also ships reference answers for requirement clarification and implementation planning, which the paper uses with an LLM judge to attribute failures to a stage. Those are diagnostic annotations, not part of the executable score, and this adapter does not use them.

## Adapter Features

- One Harbor task per instance, named by the lower-cased instance id: `pypa__pip-13124`
- Uses each instance's pinned task image, its own rebuild, test and print commands, its own log parser, and the pass rule of the benchmark's evaluator
- Grades in a separate verifier container that starts from the same pinned image. The hidden tests, the reference patch and the grader never enter the agent's container
- Records the agent's work as one patch after the agent stops, with a collect hook, and hands only that patch to the verifier
- Removes the fix from the agent's repository: the published images keep the upstream remote and later commits, so the agent image deletes every ref and object newer than the base commit
- Resets every file the hidden tests touch to the base commit before applying them, so a submission cannot replace or weaken the tests
- `--split parity` generates the 16-task parity subset

## Generated Task Structure

```
swe-rpg/
└── <instance-id>/                  # e.g. pypa__pip-13124
    ├── task.toml                   # separate verifier, collect hook, artifact path, pins
    ├── instruction.md              # where the repository is, then the issue title and body
    ├── environment/
    │   └── Dockerfile              # the pinned task image with later git history removed
    ├── solution/
    │   ├── solve.sh                # oracle: applies gold.patch
    │   └── gold.patch              # the developers' patch
    └── tests/
        ├── Dockerfile              # verifier image: the pinned task image, Python if missing, the files below
        ├── test.sh                 # applies the submission and the hidden tests, rebuilds, tests, grades
        ├── grade.py                # log parsing and the pass rule, ported from the original evaluator
        ├── test.patch              # the hidden tests
        ├── rebuild.sh              # the instance's rebuild commands
        ├── run_tests.sh            # the instance's test commands
        ├── print.sh                # the instance's commands that print the test results
        ├── log_parser.py           # the instance's log parser
        └── expected.json           # FAIL_TO_PASS and PASS_TO_PASS test names
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the dataset is published:

```bash
harbor run -d Xin-Zhou-smu/swe-rpg -a oracle
harbor run -d Xin-Zhou-smu/swe-rpg -a <agent> -m "<model>"
harbor run -d Xin-Zhou-smu/swe-rpg@parity -a <agent> -m "<model>"   # 16-task parity subset
```

### Using Job Configurations

```bash
# From the adapters repository root
harbor run -c src/swe-rpg/run_swe-rpg.yaml

# Or point at a generated dataset directory
harbor run -p datasets/swe-rpg -a oracle
```

### Running Individual Trials

```bash
harbor trial start -p datasets/swe-rpg/pypa__pip-13124 -a oracle
```

## Usage: Create Task Directories

```bash
cd src/swe-rpg
uv sync
uv run swe-rpg --output-dir ../../datasets/swe-rpg
uv run swe-rpg --split parity --output-dir ../../datasets/swe-rpg-parity
```

Flags:

- `--output-dir`: destination directory, default `datasets/swe-rpg`
- `--limit`: generate only the first N tasks
- `--overwrite`: replace existing task directories
- `--task-ids`: generate only the listed instance ids (any letter case)
- `--split`: `full` (default, 163 tasks) or `parity` (16 tasks)
- `--data-file`: a local `benchmark.jsonl`; its SHA256 is checked before use

Without `--data-file` the adapter downloads `data/benchmark.jsonl` from the pinned commit into `~/.cache/swe-rpg-adapter` and checks its SHA256.

## Comparison with Original Benchmark (Parity)

### Oracle

The oracle applies the developers' patch in the agent's container. Every result below is from Harbor 0.27.0 with the separate verifier, on Modal sandboxes (x86_64).

| Check | Tasks | Result |
|-------|-------|--------|
| Oracle, full dataset | 163 | 163 with reward 1, 0 exceptions |
| No agent action (`nop`) | 17 | 17 with reward 0; every submitted patch is empty |

- The full run took 1 hour 19 minutes at eight trials at a time. It gave 162 tasks reward 1. The remaining task, `junit-team__junit-framework-4474`, failed because of the image problem described in Notes & Caveats, and it got reward 1 when it was run again with the fix. The fix changes only that task: the other 162 generated tasks are byte-identical before and after it
- In all 163 oracle trials the patch that the collect hook recorded names exactly the files of the developers' patch
- The `nop` check ran on the 16 parity tasks and on `junit-team__junit-framework-4474`
- In 26 tasks the oracle run did not report every expected test name; see the pass rule in Notes & Caveats

### Parity

Parity experiments have not been run yet. The table will be filled in when they are.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| pending | pending | resolved rate | 0 | 16 | pending | pending |

Plan:

- **The original repository cannot run an agent.** It has no agent driver and no way to score an agent's patch; its evaluator only checks the gold patch. Parity therefore needs a small driver added to a fork: start an agent in the pinned task image with the same instruction, take `git diff` against the image's starting working tree, and score that patch with the original evaluator's stages and pass rule
- **Subset**: the 16 tasks in `src/swe_rpg/parity_task_ids.txt`, 8 Java and 8 Python, drawn from the sorted instance ids with `random.Random(20261125)`
- **Runs**: three per side, reported as mean ± sample SEM

Reproduction of the Harbor side:

```bash
cd src/swe-rpg
uv run swe-rpg --split parity --output-dir ../../datasets/swe-rpg-parity
harbor run -p ../../datasets/swe-rpg-parity -a <agent> -m "<model>"
```

## Notes & Caveats

- **What the agent is told.** The paper defines the input as the repository at the base commit plus "a user requirement in natural language", which it also calls the issue description. The instruction is one sentence that says where the repository is, followed by the title and body of each linked issue. The pull-request title and body are left out because they describe the fix. Issue comments are left out because they can discuss the fix. The paper does not publish its prompt, so this wording is the adapter's
- **The fix is removed from the agent's repository.** In the published images the repository can still have its upstream remote, and then the fix is reachable with `git log origin/main`. The agent image removes the remotes, deletes every ref that is not the current branch or a tag on the base commit's history, and prunes unreachable objects. The build fails if `HEAD` is not the base commit or if any later commit remains
- **One task has an extra image step.** The image of `junit-team__junit-framework-4474` keeps the `junit-<random>` result directories of an earlier Gradle test run. On Modal, the first run of each Gradle test task deleted its old directory and then stopped with `Could not read path` on the deleted file, so the hidden tests never ran. In plain Docker the same Gradle task (`:platform-tests:test`) deleted its old directory and ran normally, so the failure is specific to that sandbox. The agent image and the verifier image of this task delete those directories at build time. `IMAGE_FIXUPS` in `adapter.py` holds this step and the reason
- **Leftover files are removed.** Untracked, non-ignored files in the published image, such as a `test-output.log` from an earlier run, are deleted from both the agent image and the verifier image. An agent's own test run can recreate such a file, and it then becomes part of the submitted patch; if the verifier image still held the old copy, that patch would not apply
- **Some published images are not clean checkouts.** In several images the working tree already differs from the base commit before any agent runs. In `aws-cloudformation__cfn-lint-3377`, for example, a diff against the base commit after the oracle ran listed 2,086 files, and the reference patch has 2. Such a diff contains changes the agent never made, and it does not apply to a fresh copy of the same image. The agent image records its starting working tree as a commit under `refs/task/start` at build time. That commit's parent is the base commit, and it is not on any branch
- **How the submission reaches the verifier.** A collect hook runs `git add -A` and `git diff --cached --binary refs/task/start` in the agent's container after the agent stops, so the patch holds only what changed after the task started. The verifier applies that patch to a fresh copy of the image
- **Order of patches.** The original evaluator applies the test patch and then the gold patch. For an agent's patch the adapter follows the SWE-bench order the paper cites: apply the submission, reset the files that the test patch touches to the base commit, then apply the test patch
- **Pass rule.** `grade.py` keeps the evaluator's rule: no fail-to-pass test fails, no pass-to-pass test fails, and at least one fail-to-pass test passes. Test names the parser does not report are not failures. The benchmark relies on this: several instances list the same test under more than one spelling. The paper states a stricter rule, that all fail-to-pass tests pass; the adapter follows the code. The data needs the looser rule: in `grpc__grpc-java-12466`, 655 of the 656 fail-to-pass names contain a JVM object hash such as `TestParam@6987b0e8`, which changes on every run, and exactly those 655 names were unreported in the oracle run. Four instances have such names. In the oracle run, 26 tasks had expected test names that the parser did not report, and they still count as resolved
- **Three gRPC tasks run fewer tests on Modal.** In `grpc__grpc-java-11933`, `-12441` and `-12466`, the test `XdsTestServerTest > check_ipv6` cannot bind the IPv6 loopback address in a Modal sandbox. Gradle then stops, and the modules after `grpc-interop-testing` do not run. In `-12441` this left 68 further fail-to-pass names unreported in the oracle run. The pass rule above still accepts these runs
- **Network.** Rebuild commands download dependencies (`pip install`, Gradle), so the verifier keeps network access. The agent also has network access, as it needs the same downloads to build and test. This means an agent can look for the upstream fix online. It happened in the first trial run of a real agent: Claude Code with a small model, on `pypa__pip-13124`, downloaded later versions of the files it had to change from `raw.githubusercontent.com` and was scored as resolved. Results with open network access should be read with this in mind
- **Python in the verifier.** The log parsers are Python. Some Java task images have no Python, so the verifier image installs `python3` with the image's package manager when it is missing. The agent image is not changed in this way
- **Platform.** The task images are published for `linux/amd64` only. Both Dockerfiles name that platform
- **Resources and time.** 4 CPUs and 8 GB, the defaults of the original Docker evaluator. The verifier timeout is 7200 seconds, its default run timeout. The paper gives no agent time limit; the adapter uses 3600 seconds
- **Not adapted.** The clarification and planning references under `data/mid-groundtruths/` and the LLM-judge failure attribution

## Installation / Prerequisites

- Docker on a `linux/amd64` host, or a cloud sandbox. Emulation on other hosts works for small tasks and is slow
- Harbor CLI (`uv tool install harbor`). The results in this README were produced with Harbor 0.27.0
- Python 3.11 or later and `uv`:
  ```bash
  cd src/swe-rpg
  uv sync
  ```

## Troubleshooting

- **`no matching manifest for linux/arm64`.** The images are amd64 only. Use an amd64 host or a cloud sandbox
- **The image build fails at the git step.** The build checks that `HEAD` is the instance's base commit and that no later commit is left. A failure means the published image differs from the dataset record
- **A Java task runs out of memory.** Run one trial at a time, as the original evaluator advises

## Citation

```bibtex
@misc{zhou2026swerpg,
  title         = {A Unified Issue Resolution Benchmark for Requirement Clarification, Planning, and Code Generation for Coding Agents},
  author        = {Zhou, Xin and Chong, Chun Yong and Kim, Kisub and Peng, Yun and Shu, Rui and Wu, Zihan and Han, Xu and Yuan, Guowen and Zhuang, Zeyang and Kim, Jounghoon and Ju, Jeongjin and Ju, Seongmin and Yoon, Taein and Lo, David},
  year          = {2026},
  eprint        = {2608.09072},
  archivePrefix = {arXiv}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Jianghao Zhang](mailto:jianghz@umich.edu) ([@jianghao-zhang](https://github.com/jianghao-zhang)).

Issues and pull requests are welcome in the adapters repository.
