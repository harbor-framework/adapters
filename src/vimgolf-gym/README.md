## VimGolf-Gym → Harbor Adapter

## Overview

VimGolf-Gym evaluates whether an agent can transform an input text file into an output file with a short sequence of Vim keystrokes. It packages the **612 public challenges of [vimgolf.com](https://www.vimgolf.com)** (code refactoring, text reformatting, data munging, puzzles; 30+ file types).

- **Dataset size:** 470 Harbor tasks, one per vimgolf.com challenge: the **oracle-covered subset** of the 612 challenges, i.e. those for which a replay-verified oracle solution within the keystroke budget exists (see Notes & Caveats). Pass rates on it are not comparable with pass rates on all 612. `--include-unverified` emits all 612.
- **Provenance:** [james4ever0/vimgolf-gym](https://github.com/james4ever0/vimgolf-gym) (Unlicense), data from [James4Ever0/vimgolf_challenges_and_solutions](https://huggingface.co/datasets/James4Ever0/vimgolf_challenges_and_solutions) at revision `5263d1e9`.
- **Main modifications for adaptation:** the single-shot LLM prompt is turned into an agent instruction that asks for the answer in `/app/solution.txt`; grading runs in a separate, network-less verifier sandbox built from the upstream verifier image.

## What is VimGolf-Gym?

VimGolf is a game where players transform a file using as few Vim keystrokes as possible. VimGolf-Gym ([repo](https://github.com/james4ever0/vimgolf-gym), [site](https://vimgolf.netlify.app)) wraps the public challenges as an OpenAI-gym-like environment and benchmark for LLMs. Its benchmark (`vimgolf-benchmark.py` + `vimgolf-evaluate.py`) asks a model for a one-line keystroke solution, replays it in Vim inside the `agile4im/vimgolf-verifier` container (no network, no output file), and counts it as solved when the sha256 of the edited file equals that of the expected output and the solution has no more keystrokes than the output has characters. The metric is the **pass rate (%)**.

## Adapter Features

- Pinned data download (`challenges.zip`, sha256-checked) or `--zip-path` for an offline copy.
- Stable, registry-safe task names `vimgolf-gym/<filetype>-<title>-<challenge id>` (the Terminal-Bench adapter's scheme, lowercased).
- Agent sandbox = the published upstream verifier image (`agile4im/vimgolf-verifier:v0.0.3`, pinned by digest), so `vimgolf local` self-checks use the same Vim build as grading; `/app/input.txt`, `/app/output.txt` and `/app/challenge.json` are provided. The image's `/app/vimgolf-verifier.py`, which embeds a demo challenge with its solution, is removed from the agent sandbox.
- **Agent network: LLM API hosts only** (`[agent] network_mode = "allowlist"`, `api.openai.com`, `api.anthropic.com`; add others with `harbor run --allow-agent-host`, e.g. `app-us.ppapi.ai` for the parity API). The pinned dataset and vimgolf.com publish solutions, and upstream's single LLM call has no way to look them up. Agent installation still runs on the public baseline network. Harbor restores the baseline network right after `agent.run()` returns, before it collects the artifacts and stops the sandbox, so a background process left by the agent has a short public-network window; closing it would need a Harbor-side change (or a non-public baseline with the agent preinstalled).
- **Separate verifier sandbox** (`[verifier] environment_mode = "separate"`, `network_mode = "no-network"`): the declared artifact `/app/solution.txt` and Harbor's implicit `/logs/artifacts` dir cross over. The verifier holds the input and the **sha256** of the expected output, never the output text. Before the replay, the grader makes `/app/solution.txt` (root, 0600) and `/logs/artifacts` (root, 0700) unreadable to the replay user, so keystrokes such as `:r /app/solution.txt` cannot read in an output the agent shipped alongside (only the file's first non-empty line is the solution; upstream hands its verifier only that line and deletes it before Vim starts). The replay runs as `nobody` and the reward is written afterwards by the root grader, so keystrokes cannot write the reward file.
- `tests/grade.py` is a line-by-line port of `vimgolf-evaluate.py --solution-format vimgolf-benchmark --validator vimgolf-validator --solution-not-longer-than-output`; the replay itself is the unmodified `/app/vimgolf-verifier.py single_shot` from the image.
- Real oracle solutions (no hash bypass): every `solve.sh` writes a keystroke solution that was replay-verified (public solution, key-name repair, diff-based edit script, or delta-debugging minimization; see `oracle/`).
- Parity agent `vimgolf_gym.single_shot_agent:VimGolfSingleShotAgent` reproducing `vimgolf-benchmark.py --runner single_shot`.

## Generated Task Structure

```
vimgolf-gym/
├── {task_id}/
│   ├── task.toml                 # schema 1.3, separate verifier, artifact /app/solution.txt
│   ├── instruction.md            # upstream single-shot prompt adapted to /app/solution.txt
│   ├── environment/
│   │   ├── Dockerfile            # FROM agile4im/vimgolf-verifier:v0.0.3@sha256:...
│   │   ├── input.txt
│   │   ├── output.txt
│   │   └── challenge.json        # title, detail, input, output (used by the parity agent)
│   ├── solution/
│   │   └── solve.sh              # writes the verified oracle keystrokes
│   └── tests/
│       ├── Dockerfile            # verifier image: upstream image + grader
│       ├── test.sh
│       ├── grade.py              # port of vimgolf-evaluate.py
│       └── grading.json          # input, sha256(format_(output)), len(output)
```

Adapter code:

```
src/vimgolf-gym/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_vimgolf-gym.yaml
├── oracle/                       # oracle construction tools (not needed to generate tasks)
│   ├── build_oracles.py
│   ├── diff_solver.py
│   └── excluded.txt              # the 142 challenges without a verified oracle
├── parity/
│   ├── make_subset_dir.py        # original-side dataset dir with exactly the 470 tasks
│   └── grader_agreement.py       # upstream evaluator vs Harbor verifier on the same solutions
└── src/vimgolf_gym/
    ├── __init__.py
    ├── adapter.py
    ├── main.py
    ├── single_shot_agent.py
    ├── oracle_solutions.json
    └── task-template/
```

## Run Evaluation / Harness

### Running with Datasets Registry

```bash
# Use oracle agent (reference solution)
uv run harbor run -d vimgolf-gym/vimgolf-gym

# Use your specified agent and model
uv run harbor run -d vimgolf-gym/vimgolf-gym -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

```bash
# From src/vimgolf-gym, after generating ../../datasets/vimgolf-gym
uv run harbor run -c run_vimgolf-gym.yaml                      # oracle
uv run harbor run -p ../../datasets/vimgolf-gym -a terminus-2 -m "openai/gpt-5-mini"
uv run harbor run -p ../../datasets/vimgolf-gym \
  -a vimgolf_gym.single_shot_agent:VimGolfSingleShotAgent -m "openai/gpt-5-mini"
uv run harbor job resume -p /path/to/jobs/directory
```

### Running Individual Trial

```bash
uv run harbor trial start -p ../../datasets/vimgolf-gym/<task_id>
uv run harbor trial start -p ../../datasets/vimgolf-gym/<task_id> -a <agent_name> -m "<model_name>"
```

## Usage: Create Task Directories

```bash
cd src/vimgolf-gym
uv sync
uv run vimgolf-gym --output-dir ../../datasets/vimgolf-gym
```

Available flags:
- `--output-dir` — directory to write generated tasks (defaults to `datasets/vimgolf-gym` at the repo root)
- `--limit` — generate only the first N tasks
- `--overwrite` — overwrite existing tasks
- `--task-ids` — only generate these Harbor task ids or vimgolf challenge ids
- `--zip-path` — use a local `challenges.zip` (sha256-checked) instead of downloading
- `--include-unverified` — also emit challenges without a verified oracle

## Comparison with Original Benchmark (Parity)

Parity has not been run yet; the plan below needs sign-off from the adapters team.

**Oracle and grader checks (done, no LLM involved).**

- Oracle: `harbor run -c run_vimgolf-gym.yaml` (Docker 29.1.3, Harbor 0.24.0) gives 470/470 reward 1, 0 exceptions.
- Grader agreement: `parity/grader_agreement.py` grades the same 319 solutions (40 seeded tasks, 8 variants each) with the upstream evaluator (`vimgolf-evaluate.py --solution-format vimgolf-benchmark --validator vimgolf-validator --solution-not-longer-than-output`, vimgolf-gym@5c29ac2) and with the Harbor verifier. Every verdict agrees (319/319):

| Variant | n | Harbor pass | Upstream pass |
|---|---|---|---|
| oracle | 40 | 40 | 40 |
| oracle padded with `<Esc>` to exactly the keystroke budget | 39 | 39 | 39 |
| one keystroke over the budget | 40 | 0 | 0 |
| oracle without its last key | 40 | 1 | 1 |
| wrong keys / empty | 80 | 0 | 0 |
| read the output from `/app/solution.txt` lines 2+ | 40 | 0 | 0 |
| read the output from a file left in `/logs/artifacts` | 40 | 0 | 0 |

The budget counts the raw output's characters, including the `\r` of CRLF files (4 of the 40 tasks), as upstream does.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| vimgolf-single-shot@1.0.0 | TBD | pass rate (%), oracle-covered 470/612 subset | 3 | 470 | TBD | TBD |

Plan: the original side runs a fork of vimgolf-gym (`vimgolf-benchmark.py --runner single_shot`, then `vimgolf-evaluate.py --solution-format vimgolf-benchmark --validator vimgolf-validator --solution-not-longer-than-output`) and the Harbor side runs `VimGolfSingleShotAgent`, same model, same litellm version, same task subset, 3 runs each. The fork applies the two symmetric fixes listed in Notes & Caveats. A standard terminal agent (terminus-2 / codex) is also run on Harbor to show the adapter works for agents.

```bash
# Original side. First, from src/vimgolf-gym, write the 470 shipped challenges (and
# <dir>.ids.json) in the layout vimgolf-benchmark.py reads:
uv run python parity/make_subset_dir.py /path/to/challenges.zip /path/to/vimgolf-subset
# then, in the fork:
python3 vimgolf-benchmark.py --dataset-name vimgolf-public --dataset-format vimgolf_public \
  --dataset-dir /path/to/vimgolf-subset --model <model> --runner single_shot --output-jsonl run1.jsonl
python3 -u vimgolf-evaluate.py --solution-format vimgolf-benchmark --jsonl-file run1.jsonl \
  --validator vimgolf-validator --solution-not-longer-than-output --result-savepath eval1.json
# Harbor side
uv run harbor run -p ../../datasets/vimgolf-gym \
  -a vimgolf_gym.single_shot_agent:VimGolfSingleShotAgent -m <model>
```

## Notes & Caveats

- **Task subset.** 470 of the 612 challenges are included. A challenge is included only if a replay-verified solution with `keystrokes <= len(output)` was found. Some excluded challenges are likely impossible under that rule. For example, "Overall Vimgolf Rank" has the 4-character output `794\n`. Others simply lack a known short solution. Exclusions are oracle-coverage limits, not proof of unsolvability; the list is in `oracle/excluded.txt`. The selection shifts the task distribution: the median output length (= keystroke budget) is 244.5 characters for included and 87.5 for excluded challenges (206.5 over all 612), so tight-budget challenges are under-represented. `oracle/build_oracles.py` screens candidates with the grader's replay env (no `TERM`). With `TERM` set, Vim decodes termcodes such as `<Esc>[201~` in the keys, so a solution can pass in an interactive shell and fail the grader. All 470 included oracles reach reward 1 under `harbor run -a oracle` (Docker 29.1.3, Harbor 0.24.0; 470/470, 0 exceptions).
- **Image entrypoint.** `agile4im/vimgolf-verifier:v0.0.3` sets `ENTRYPOINT ["sh"]`, which turns Harbor's container command `sh -c "sleep infinity"` into `sh sh -c ...` and exits at start. Both Dockerfiles reset it with `ENTRYPOINT []`; the upstream evaluator overrides the entrypoint the same way (`docker run --entrypoint python`).
- **Verifier script version.** The published image `agile4im/vimgolf-verifier:v0.0.3` contains a `vimgolf-verifier.py` that differs from the repo HEAD. The repo HEAD version prints `Output content:` before its JSON, which would make `vimgolf-evaluate.py`'s `json.loads` fail on every solution. We pin and use the image, which is what the upstream evaluator runs.
- **Interaction setting.** Upstream's single-shot run is one LLM call with no tools. Terminal agents on Harbor can read the files and test candidates with `vimgolf local` before answering, a stronger setting; parity uses the single-shot agent, which sends the upstream prompt unchanged.
- **Length rule.** The prompt says "less than the length of output file", but the upstream evaluator only rejects solutions with *more* keystrokes than `len(output)` (raw, before newline normalization). We grade with the evaluator's rule.
- **Upstream bug (stream parsing), fixed symmetrically.** `vimgolf-benchmark.py` does not reset `chunk_content` per streamed chunk. A final chunk with an empty delta therefore re-appends the previous chunk, which can corrupt the extracted solution line. The parity agent and the parity fork both use the corrected logic.
- **litellm version.** Harbor 0.24.0 requires `litellm>=1.92`, while upstream pins 1.76.2; the parity fork is run with the same litellm version as the adapter (1.105.0).
- **Terminal-Bench adapter differences.** [TB PR #990](https://github.com/harbor-framework/terminal-bench-1/pull/990) by the benchmark author used a hash-bypass oracle, a compose verifier sidecar, a test venv inside the agent container, and strict `<` with whole-file token counting. This adapter replaces all of these with the upstream evaluator semantics and a real oracle.
- The images are `linux/amd64` only; on Apple Silicon they run under emulation.

## Installation / Prerequisites

- Docker installed and running (x86_64 host recommended; images are amd64-only).
- Harbor installed and working (see main repository README).
- Python environment with dependencies:
  ```bash
  cd src/vimgolf-gym
  uv sync
  ```
- API keys for the agents/models you run (e.g. `OPENAI_API_KEY`).
- Regenerating oracles (optional): `uv sync --extra oracle`, a local `vim`, then `uv run python oracle/build_oracles.py <challenges.zip> src/vimgolf_gym/oracle_solutions.json --minimize`.

## Troubleshooting

- `pull access denied` / slow builds on ARM: the upstream image is amd64-only; enable emulation or use an x86_64 host.
- A trial with reward 0 and `reason: solution_longer_than_output` in `/logs/verifier/grading_details.json` means the replay was skipped by the length rule; `output_mismatch` means the replayed file differed.
- Network-policy errors on the verifier: your environment provider must support `no-network`.

## Citation

```bibtex
@misc{vimgolfgym2025,
  title        = {vimgolf-gym: OpenAI gym like, customizable environment and benchmark for VimGolf},
  author       = {Brown, James},
  year         = {2025},
  howpublished = {\url{https://github.com/james4ever0/vimgolf-gym}}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Zineng Tang](mailto:terran@berkeley.edu).

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines

## Acknowledgement

> API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
