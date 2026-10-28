# ARC-AGI-3 adapter

## Overview

Draft migration of [harbor#2728](https://github.com/harbor-framework/harbor/pull/2728).
Generates one task for each of the 25 pinned public games in `games.json`.
Model parity and full oracle coverage are pending. This dataset is not published.

## What is ARC-AGI-3?

[ARC-AGI-3](https://arcprize.org/) evaluates agents exploring unfamiliar interactive
games, inferring their rules and clearing successive levels through actions.
The engine and game snapshot is inherited from the original PR at
`61ed7bd8606976e256ffcf8b509a58f789cde56e`. Game IDs pin the game versions.
The original engine's upstream commit was not recorded; upstream revision traceability
remains incomplete. `validation/source-manifest.json` records the vendored file hashes.

## Adapter Features

- Separate agent and game containers; the agent image contains no game sources.
- Public `/action_log` excludes `baseline_actions`. Harbor uploads pinned scoring
  metadata in `/tests/scoring.json` after agent execution, only for the verifier.
- Preserves `score` (levels cleared), `is_win` (0/1), and RHAE-style `efficiency` ([0,1]).
- Transport/malformed-runtime failures are verifier errors without reward files;
  a valid game with no actions still receives zero.
- Oracles replay legal actions through the public API and require `win`; missing
  trajectories fail explicitly rather than setting game state or silently passing.

## Generated Task Structure

```text
<game-id>/
├── task.toml
├── instruction.md
├── environment/
│   ├── Dockerfile
│   ├── Dockerfile.game
│   ├── docker-compose.yaml
│   ├── harness-assets/
│   └── arc-runtime-env/  # copied only into the game image
├── solution/
│   ├── solve.sh
│   ├── replay.py
│   └── actions.json     # only when a reference trajectory is available
└── tests/
    ├── test.sh
    ├── verify.py
    └── scoring.json     # verifier-only baseline metadata
```

## Run Evaluation / Harness

Registry execution is unavailable until the Harbor team publishes the dataset.
For local development, generate tasks first, then run from this adapter directory:

```bash
harbor run -c run_arc-agi-3.yaml
```

The default agent is `oracle`. Generate only games with available trajectories for
replay validation; the full 25-game set has incomplete oracle coverage. A passing
subset is not 25/25. `claude-code.yaml` preserves the original agent prompt/tool
configuration but is not an approved parity protocol. It requires Harbor's `tools` option
([core PR #3959](https://github.com/harbor-framework/harbor/pull/3959)).

## Usage: Create Task Directories

```bash
cd src/arc-agi-3
uv sync --locked
uv run arc-agi-3 --output-dir datasets/arc-agi-3
uv run arc-agi-3 --output-dir datasets/smoke --limit 1
uv run arc-agi-3 --output-dir datasets/replay --task-ids cd82-fb555c5d --overwrite
```

Unknown game IDs are rejected. Task names retain the original stable
`arcprize/arc-agi-3__<game-id>` form.

## Comparison with Original Benchmark (Parity)

**No matched model parity is claimed.** `parity_experiment.json` is absent until actual
matched results exist. Historical smoke tests and action replays are separate evidence.
See [the proposed protocol](validation/parity-plan.md) and
[maintainer coordination](https://github.com/harbor-framework/harbor/pull/2728#issuecomment-6463998953).
The reference runner, model/agent, coverage, budgets and oracle criterion need agreement.
Reproduction commands for both model runners will be added once the reference is selected.
The planned sequence is 5–10 tasks on both sides, one full run per side, then three runs
per side, recording raw arrays and mean ± sample SEM.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| Pending agreement | Pending agreement | Pending agreement | 0 | Not selected | Not run | Not run |

Local validation without model API calls:

```bash
uv run pytest tests -q
(cd ../.. && python3 scripts/validate_adapter.py arc-agi-3)
```

Latest local validation: **45 tests passed** (Python 3.12.12), covering task generation,
all 25 runtime APIs/verifiers, nine winning trajectory replays, scoring edge cases and
error handling. See [sanitized JUnit results](validation/local-tests.xml). The wheel
was built, installed in an isolated environment and used to generate a complete task.
Separate [Harbor/Docker evidence and reproduction commands](validation/README.md)
record all nine available oracle trajectories winning and all 25 no-op trials scoring
zero, with zero execution/verifier errors.
Neither local tests nor Docker replays establish model parity.

## Notes & Caveats

- **Incomplete oracle coverage:** action-only traces come from historical successful
  runs and record their source-log SHA-256. No private model reasoning, credentials,
  endpoint configuration or session prompts are bundled. Replays establish solvability
  for the particular versions/seeds, not fresh model performance.
- **Oracle acceptance is proposed:** `is_win=1` for every included game, with efficiency
  reported separately. Maintainer agreement is pending; full-oracle acceptance is not claimed.
- **Inherited scoring is not certified official leaderboard scoring:** efficiency is
  `sum(i * min(baseline_i / max(actions_i, 1), 1)^2) / sum(i)` with one-based weights and
  a denominator spanning `max(total_levels, completed_level_spans)`. Missing baselines
  for extra spans use 1, as in the original PR. Uncompleted levels stay in the denominator.
  Agree on the primary metric and upstream evaluator before parity.
- **Inherited reset differences:** fresh-level resets are ignored and completed-level
  progress uses first-reach high-water marks across resets. These require fidelity
  review against the reference runner rather than an assumption of equivalence.
- **Security scope:** containers protect local game sources; HTTP filtering protects
  baselines during agent execution. Harbor owns the agent/verifier phase boundary.
  This adapter does not block internet access to public sources; agree network policy.
- **Core prerequisite:** current Claude Code option rendering already quotes normal
  arguments. The old global quoting patch is not carried here. Missing `--tools` support
  is [Harbor core PR #3959](https://github.com/harbor-framework/harbor/pull/3959).
  Record the exact Harbor revision used for runs.
- Original PR tests are historical author-reported evidence, not reclassified as newly
  reproduced results or matched model parity.

## Installation / Prerequisites

Python 3.12+, uv, and Docker with Compose v2 for Harbor trials. Install Harbor separately.
Use a Harbor revision with Claude Code `tools` support for `claude-code.yaml` and pin it.
No API credentials are needed for unit/runtime checks or oracle replays. Model credentials
are needed only for the agreed model experiments.

## Troubleshooting

- Missing `actions.json`: the game lacks a reference solution; this is not a passing oracle.
- Verifier failure: inspect `/logs/verifier/metrics.json` and game logs. Keep infrastructure
  errors outside the valid-score denominator.
- Unknown `tools`: install the separate Harbor core prerequisite before model runs.
- OOM/slow builds: lower concurrency. Each game service is capped at four CPUs and 4 GiB.
- Keep game logs in a sibling of the agent log directory, not under its visible mount.

## Citation

Credit the [ARC Prize Foundation](https://arcprize.org/) and
[ARCEngine](https://github.com/arcprize/ARCEngine). Vendored MIT licenses and game headers
are preserved.

```bibtex
@misc{arcengine,
  author = {{ARC Prize Foundation}},
  title = {ARCEngine},
  howpublished = {\url{https://github.com/arcprize/ARCEngine}}
}
```

## Authors & Contributions

Adapter: [GhostofAdam](https://github.com/GhostofAdam). Games/engine: ARC Prize Foundation.
Migration, tests and documentation were prepared with Codex assistance.
