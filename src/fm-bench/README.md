## Overview

This adapter ports the Solo track of FM-Bench to Harbor. The dataset is one task: a single agent manages a football club for 20 in-game seasons against 15 scripted clubs, in one fixed world (seed 1). Repeated attempts (`harbor run -k N`) measure a model's spread.

- Tasks: 1, named `fm-bench/fm-bench-solo-20y`.
- Metrics: two. `s_final` is the original composite score, uncapped. `reward` is a float in [0, 1], `clip(S_final / reference, 0, 1)`, where `reference` is the oracle's `S_final` in the same world. The three score channels are saved to `/logs/verifier/result.json`.
- Status: the oracle passes at 100% reward in Harbor (see Notes & Caveats). Parity experiments have not been run yet.

## What is FM-Bench?

FM-Bench ([paper](https://arxiv.org/abs/2608.18423)) is a benchmark for long-horizon decision making. An agent runs a football club through 26 tools: transfers, contracts, lineups, tactics, finances, a youth academy, and a notebook that is its only memory across decision stops. A 20-year run has roughly 340 to 420 decision stops. True player ability is hidden; the agent sees only noisy scout ranges. The engine is a deterministic Python simulation: a seed plus an action log replays to an identical final state.

The original metric is the composite `S_final`: three log-compressed channels (honors, net-worth value added, squad value), uncapped, with a discount for runs that end early.

## Adapter Features

- **Game sidecar.** The engine and the world run in a separate `game` container. The agent container holds the rulebook, the tool schemas and an HTTP client (`fm`), and nothing else from the benchmark. The sidecar forwards each call to the original `Game.call_tool`, so the per-stop query and offer budgets and the observation filter are the original code.
- **Server-side scoring.** `tests/test.sh` asks the sidecar for the settled result with a token passed through `[verifier.env]`, then writes `reward.txt` (the reward) and `reward.json` (`reward` and `s_final`). A run that is not played to the end is settled as abandoned, as the original scorer does. It also saves the run's action log to `/logs/verifier/actions.jsonl`; with the seed, that log replays to the same final state in the FM-Bench engine, so a trial's score can be checked afterwards.
- **Oracle by replay.** `solution/solve.sh` replays a recorded action log through the same tool endpoint an agent uses. No endpoint exposes hidden state, and the policy that produced the log (`harbor_adapter/oracle_v4.py` in the FM-Bench repository) reads none.
- **Parity agent.** `fm_bench.parity_agent:FMBenchParityAgent` runs the original harness class `runner.llm_agent.LLMAgent`, unmodified, against the sidecar. The only substitution is the game object (`fm_bench/remote_game.py`), which forwards tool calls to `fm rpc` in the agent container. Defaults are the paper's harness settings: `max_tokens` 8000, soft and hard turn limits 40 and 60, flat memory, temperature 0. It needs an FM-Bench checkout on the host (`FMBENCH_ROOT`) and the provider API key in the environment.

## Generated Task Structure

```
fm-bench-solo-20y/
├── task.toml
├── instruction.md
├── environment/
│   ├── Dockerfile              # agent container: fm client, rules.md, tools.json
│   ├── docker-compose.yaml     # adds the game sidecar; seed and reference live here
│   ├── fm.py
│   ├── rules.md
│   ├── tools.json
│   └── game/
│       ├── Dockerfile          # sidecar: engine + game_server.py
│       ├── game_server.py
│       └── fmbench/            # engine/, score/, params.yaml from the FM-Bench checkout
├── solution/
│   ├── solve.sh
│   └── actions.jsonl.gz        # recorded oracle action log
└── tests/
    └── test.sh
```

## Run Evaluation / Harness

```bash
# from the registry (after publishing); -k sets the number of attempts
harbor run -d fm-bench/fm-bench -a <agent> -m <model> -k 3

# from a local dataset directory
harbor run -p datasets/fm-bench -a <agent> -m <model> -k 3

# oracle verification with the reference config
harbor run -c src/fm-bench/run_fm-bench.yaml
```

A model run takes hours; `[agent].timeout_sec` is set to 12 hours. The job's `result.json` reports the mean of each metric over the attempts.

## Usage: Create Task Directories

```bash
cd src/fm-bench
uv run fm-bench --output-dir ../../datasets/fm-bench
```

The adapter copies the engine (`engine/`, `score/`, `params.yaml`) and `rules.md` from the FM-Bench source into the task. It takes the source from the first of these that applies:

1. `--fmbench-root <checkout>` (or `FMBENCH_ROOT`): a local FM-Bench checkout.
2. `--fmbench-repo <git url>` (or `FMBENCH_REPO`): cloned, then checked out at `--fmbench-ref <commit>` (or `FMBENCH_REF`) if one is given.
3. An FM-Bench checkout that contains the working directory or the adapter.
4. The upstream repository and commit pinned in `adapter.py` (`UPSTREAM_REPO`, `UPSTREAM_REF`).

`UPSTREAM_REPO` is empty until the FM-Bench repository is public, so outside a checkout the command needs option 1 or 2 today.

Other flags: `--limit`, `--overwrite`, `--task-ids`, `--split {full,parity}` (both splits are the one task).

## Comparison with Original Benchmark (Parity)

Parity has not been run yet. The table will be filled from `parity_experiment.json`.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| fm-bench-parity-agent@1.0.0 | TBD | s_final | TBD | 1 (100%) | TBD | TBD |
| fm-bench-parity-agent@1.0.0 | TBD | reward | TBD | 1 (100%) | TBD | TBD |

One parity run is one game of the task: one Harbor trial, or one original-harness run on seed 1 with the same settings. `s_final` is the metric the paper reports.

Links: original benchmark repository, adapter PR, dataset PR and parity PR are TBD.

Reproduction, original side (from an FM-Bench checkout; run it once per parity run):

```bash
python run_benchmark.py --agent claude --model <model> --seeds 1 --years 20 \
    --draft --sealed --revival --tier-mix 555 \
    --max-tokens 8000 --soft-turn-limit 40 --hard-turn-limit 60 \
    --spend-cap-usd 400 --cap-mode settle
python harbor_adapter/score_original_runs.py --model <model>
```

The second command takes every finished run of the model in `results/runs` that matches the task (seed 1, 20 years, official configuration) and the parity agent's harness settings, and prints the per-run scores and mean ± sample SEM of both metrics. It lists and leaves out runs that do not match.

Reproduction, Harbor side (`-k` is the number of runs):

```bash
export FMBENCH_ROOT=/path/to/FM-Bench
PYTHONPATH=src/fm-bench/src uvx --from harbor \
    --with-requirements $FMBENCH_ROOT/requirements.txt \
    harbor run -p datasets/fm-bench -k 3 \
    --agent-import-path fm_bench.parity_agent:FMBenchParityAgent -m <model>
```

The parity agent imports the original runner into Harbor's Python process, so that process needs the runner's packages (`requirements.txt`: `pyyaml`, `anthropic`, `openai`). Harbor's own environment does not include `anthropic`. Run the original side in the same environment (`uvx --from harbor --with-requirements requirements.txt python run_benchmark.py ...`) so both sides use the same SDK versions.

Transport check without a model, in the FM-Bench repository: `python harbor_adapter/parity_transport_check.py` drives the original harness with one scripted stand-in for the model, once on an in-process engine and once through the sidecar, and compares the score, the final state hash, and a hash over every observation. In the task's world over 5 years (92 stops, 550 engine calls) the two sides are identical.

## Notes & Caveats

- **One world instead of the paper's three seeds.** The paper averages over seeds 1, 1024 and 2026. The adapter keeps one world, seed 1, FM-Bench's public reference world, and replaces the other seeds with repeated attempts. The score subtracts each world's starting endowment, and in the original runs the spread between repeats on one seed is as large as the spread between seeds: five runs of claude-opus-4-8 on seed 1 range from 69.7 to 87.4, while the median model's range across the three seeds is 10.0. The seed is fixed, not drawn per trial, because the oracle log and the reference score belong to one world.
- **`reward` is a deviation from the original; `s_final` is not.** FM-Bench reports the uncapped `S_final`, and the adapter reports it unchanged as the `s_final` metric. Harbor also needs a reward in [0, 1] and an oracle at 1.0, so `reward` divides `S_final` by the oracle's score in the same world and clips. The reference is 108.51 (the oracle's 108.5141, rounded down to two decimals). A negative `S_final` maps to reward 0. A model that beats the oracle is clipped to reward 1; its `s_final` is not clipped.
- **Expected difficulty.** Rescoring the 32 original-harness runs on seed 1 that match the task (19 models) with this reward gives per-model means from 0.53 to 0.85 and a best single run of 0.872. These are original-harness numbers, not Harbor runs. FM-Bench's scripted baselines in the same world: `idle` (only advances), `random`, `greedy` and `slim_squad` are sacked and score reward 0, `heuristic` scores 0.13, and the paper's `oracle_v2`, which reads hidden state, scores 0.92. The top of the reward scale is compressed because `S_final` is log-compressed: the best run (claude-fable-5, `S_final` 94.60, reward 0.872) has 1400 honors points and 633M of net-worth value added, against the oracle's 2000 and 1166M. No matching run reaches `S_final` 95 (reward 0.875).
- **Oracle verification.** `harbor run -p datasets/fm-bench -a oracle` with Harbor 0.26.0 and Docker on Linux: 1 of 1 trial at reward 1.0, `s_final` 108.5141, no exceptions, 1m 20s. The action log and reference score were recorded on Linux with Python 3.13.9; inside the task's containers (Python 3.11.7) the replay reaches the same `S_final` and the same final state hash. `python harbor_adapter/record_oracle.py`, in the FM-Bench repository, regenerates them if the engine or the oracle changes. The parity agent has been run in Harbor once end to end as a sanity check (gpt-5.6-terra, Harbor 0.27.0): no exceptions, 377 stops, `s_final` 92.14. That is one run, not a parity result.
- **Long sessions.** Standard CLI agents must keep one session alive for several hundred stops. This has not been tested.

## Installation / Prerequisites

- Docker and Harbor.
- The FM-Bench source to generate tasks: a checkout or a git URL (see Usage). The parity agent needs a full checkout and the packages in its `requirements.txt` in Harbor's Python environment (see the Harbor-side command under Parity).
- For model runs, the provider API key in the environment.

## Troubleshooting

- `fm-bench` reports "no FM-Bench source found": pass `--fmbench-root` or `--fmbench-repo` (see Usage).
- `solve.sh` reports "replay diverged": the sidecar's engine, parameters or Python version differ from the ones the log was recorded with. Regenerate the log and reference score with `record_oracle.py` in the task image.
- Reward 0 with settle reason `abandoned`: the agent stopped before `game_over`.
- The parity agent raises "set FMBENCH_ROOT": point it at a checkout that contains `runner/` and `engine/`.
- The parity agent fails with `ModuleNotFoundError: No module named 'anthropic'`: start Harbor with `--with-requirements $FMBENCH_ROOT/requirements.txt` (see Parity).

## Citation

```bibtex
@article{wang2026fmbench,
  title  = {FM-Bench: A Benchmark for Long-Horizon Management with Competing Agents},
  author = {Wang, Tianyou and Gao, Chongyang and Chen, Kezhen and Chen, Dong and He, Yinghao and Li, Donghan and Xu, Wangcheng and Zhang, Hongjiu and Li, Chi},
  journal = {arXiv preprint arXiv:2608.18423},
  year   = {2026}
}
```

## Authors & Contributions

This adapter is developed and maintained by Chongyang Gao (chongyanggao2026@u.northwestern.edu).
