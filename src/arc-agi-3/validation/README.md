# Validation evidence

These are implementation and oracle checks, not matched model parity. The original
25-game snapshot is pinned by `source-manifest.json`; the engine's original upstream
commit remains unknown. The adapter contract reviewed is v1 at adapters repository
base `7b4df9deb2381ae32f26e6cebec06aaa2975dc56`.

## Reproduce

From `src/arc-agi-3`, with Docker Compose v2 available:

```bash
uv sync --locked
uv run pytest tests -q
uv run arc-agi-3 --output-dir datasets/oracle9 --task-ids \
  ar25-0c556536 cd82-fb555c5d cn04-2fe56bfb ft09-0d8bbf25 \
  lp85-305b61c3 m0r0-492f87ba sb26-7fbdac44 sc25-635fd71a tu93-0768757b
harbor run -c validation/oracle9.yaml
uv run arc-agi-3 --output-dir datasets/all25
harbor run -c validation/nop25.yaml
(cd ../.. && python3 scripts/validate_adapter.py arc-agi-3)
```

Use a clean output directory for each reproduction. No model/API credential is needed.
The recorded Docker runs use Harbor `b7e015809847d109dddadefc9cd824124cff3e15`.
The later ACP guard in core PR #3959 does not affect oracle/nop execution.
The execution sources/templates/oracle trajectories match adapter commit `77cae6a`;
subsequent commits add evidence and documentation. Transfer hashes were verified before
execution; all 107 committed package source/assets match the transferred snapshot. The source snapshot excludes private model reasoning and credentials.

## Evidence boundaries

| Dimension | Assessment | Remaining gap |
| --- | --- | --- |
| Harbor structure | 27 structural checks pass; required files and 12 README sections inspected | Missing measured `parity_experiment.json`; registry not published |
| Generation | All 25 pinned tasks generated; wheel assets checked; isolated wheel install generated a complete task | No external registry execution |
| Runtime and grading | 45 local tests pass, including all 25 HTTP runtimes/verifiers, baseline filtering and error handling | Inherited reset/high-water-mark semantics and official evaluator fidelity need reference review |
| Oracle | Nine action-only winning replays through the public interface, also 9/9 in Harbor/Docker | 16 games lack reference solutions; oracle acceptance criterion awaits agreement |
| Empty agent | All 25 Harbor/Docker nop trials completed with zero rewards and zero errors | No evidence of solving capability |
| Model parity | Not run | Agree reference runner, agent/model, coverage, budgets and credentials first |

The structural checker also warns about unknown parity cost and `test.sh` reward output.
The latter script delegates to `verify.py`, which writes Harbor-supported `reward.json`
with three numeric metrics. A failed verifier removes stale rewards and raises an error.
No placeholder parity results or fabricated cost are supplied to suppress checks.

The nine trajectories were selected from historical successful runs and are **not** an
unbiased parity sample. Their source-log SHA-256 values are stored with each action file;
only legal game actions and coordinates are included. Replays preserve the original
formula and may have `efficiency < 1` despite winning. Do not normalize all wins to 1.
Full raw model transcripts are not part of this validation artifact.

A representative game container reported Python 3.12.13, NumPy 2.5.4, and
Pydantic 2.14.1 (see `docker-results.json` for its image ID). This is a sampled
image record, not a claim that every image digest was captured.

Runtime images retain inherited floating base/dependency inputs. Record exact versions
and freeze them before agreed model parity; these smoke results alone do not certify
future builds or official leaderboard equivalence.

## Docker oracle results

Nine completed Harbor oracle trials, nine wins and zero infrastructure/verifier errors.

| Game | Actions | Levels | Win | Efficiency |
| --- | ---: | ---: | ---: | ---: |
| ar25-0c556536 | 455 | 8 | 1 | 0.9375 |
| cd82-fb555c5d | 177 | 6 | 1 | 0.7723 |
| cn04-2fe56bfb | 2651 | 6 | 1 | 0.6567 |
| ft09-0d8bbf25 | 216 | 6 | 1 | 0.6658 |
| lp85-305b61c3 | 348 | 8 | 1 | 0.7996 |
| m0r0-492f87ba | 438 | 6 | 1 | 1.0000 |
| sb26-7fbdac44 | 1056 | 8 | 1 | 0.4100 |
| sc25-635fd71a | 836 | 6 | 1 | 0.2446 |
| tu93-0768757b | 449 | 9 | 1 | 0.6292 |

These are all nine available trajectories, not nine randomly sampled games.
The remaining 16 games have no bundled reference trajectory.

## Docker no-op results

All 25 pinned games completed with `score=0`, `is_win=0`, `efficiency=0`,
zero actions and no execution/verifier errors. This negative control validates startup
and empty-action grading, not game solvability. Neither job used model API calls.

[Sanitized per-trial results](docker-results.json) retain timestamps, task checksums,
raw reward components, progress metrics and source result SHA-256 values. Absolute
host paths and full execution transcripts are excluded. Every trial was run once;
no successful retry was substituted for a failure.
