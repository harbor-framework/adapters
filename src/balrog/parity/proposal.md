# BALROG parity proposal

**Proposed for maintainer approval; no model parity has run.** This plan covers all six environments in PR #117. The [machine-readable plan](plan.proposed.json) fixes task IDs, source hashes and proposed settings. `parity_experiment.json` remains `[]` until real results exist.

## Proposed comparison

We will test whether Harbor reproduces the native progression measured by the pinned original BALROG evaluator with the same agent and model. The privileged Crafter controller and AutoAscend are reference-policy research, not the agents in this comparison.

| Item | Proposal |
|---|---|
| Original agent | BALROG `naive` at `b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5`, through `Evaluator.run_episode` |
| Harbor agent | `balrog-native`, reusing the same upstream agent through public observations/actions |
| Model | `gpt-4o-mini-2024-07-18` on both sides through 2077ai; exact snapshot availability and endpoint need confirmation |
| Settings | Temperature 1, maximum output tokens 8,192, text history 16, no images; [proposed settings](settings.proposed.json) |
| Scope | All 255 fixed cases, 58 task types, six environments; no filtering by oracle or model success |
| Platform | Daytona on both sides after preflight; completed reference validation currently uses local Docker/Compose |
| Repetitions | Three complete runs per side, reached through the staged schedule below |
| Metric | Native progression, per environment and with equal weights for the six-environment aggregate |

This dated model appears in the pinned upstream README example and fits its Chat Completions client. Its availability through 2077ai and the usefulness of its results in each game remain unverified. If it is unavailable, agree an exact dated replacement before execution.

| Environment | Fixed cases | Seeds | Native action limit |
|---|---:|---|---:|
| BabyAI | 50 | 0–9 | 64 or 128 by task type |
| Baba Is AI | 120 | 0–2 | 100 |
| TextWorld | 30 | 0–9 | 80 |
| Crafter | 10 | 0–9 | 2,000 |
| NLE | 5 | 0–4 | 100,000 |
| MiniHack | 40 | 0–4 | 100 |

NLE retains its native timeout of 150 calls without a game-clock advance, not a reward-progress timeout. Environment seeds are fixed inputs within each run; the three repetitions measure model variability on those inputs. The upstream client does not supply a model-sampling seed.

## Oracle limitations and proposed treatment

Our preferred comparison preserves the **current published BALROG pin, task selection, budgets and scorer**. We request explicit acceptance of the following reference limitations before paid experiments. If maintainers require corrected benchmark rules, agree a new shared source pin, regenerate both sides and revise this experiment first.

| Environment | Evidence and reason | Proposed treatment |
|---|---|---|
| MiniHack | Hard Boxoban seed 0 needs **104 legal moves**, independently established by A* and exhaustive single-action BFS; the original **100-action** game truncates at zero. This is an upstream-budget constraint, not adapter-induced failure. | Retain the case and real score with an approved oracle exception. The alternative [upstream budget PR #70](https://github.com/balrog-ai/BALROG/pull/70) would change all ten Boxoban cases symmetrically. Its separate 40/40 result is not evidence for the original limit. |
| Crafter | V45 completes **40/40 native games**, **10/10 fresh Harbor games**, and **10/10 saved-result regrades** at full score. It uses privileged reference access; all ten fresh-game replays diverged and grading used protected native state. | Accept the V45 oracle-only approach, then package/integrate it reproducibly. Separately approve native-state scoring when replay diverges. Both model agents retain the original public text interface. |
| NLE | The scorer ignores native ascension and its implemented keys have a ceiling of about **0.8068**. Separately, none of our five AutoAscend v2 runs descended or ascended. | Preserve fractional progression and request acceptance of partial references. A scorer correction must be shared between sides; it would not supply the missing winning trajectories. |

Detailed evidence: [MiniHack](../docs/minihack_seed_and_budget_review.md), [Crafter V45](../docs/crafter_v45_validation.md), [Crafter scoring](../docs/crafter_scoring_review.md), [NLE scoring](../docs/nle_scoring_review.md), [NLE controller](../docs/nle_autoascend_v2_validation.md). The [canonical migrated run](../docs/separate_verifier_full_validation.md) remains 239 full-score references plus 16 diagnostics; newer V45 evidence does not rewrite that completed run.

## Staged primary experiment

| Stage | Original | Harbor | Purpose |
|---|---:|---:|---|
| Sanity | 10 tasks × 1 | Same 10 × 1 | Check resets, prompts, actions, grading, provider behavior and usage |
| First full pair | 255 × 1 | Same 255 × 1 | Inspect complete per-environment results before increasing spend |
| Two additional pairs | 255 × 2 | Same 255 × 2 | Reach three complete formal runs per side |

Primary total: **20 sanity + 1,530 formal = 1,550 episodes**, excluding retained failed attempts or separately approved diagnostics. Sanity records never enter formal arrays. Finish each paired stage before advancing, as required by the [adapter guide](../../../docs/adapters.mdx).

The ten predeclared sanity cases are seed 0 of BabyAI `goto` and `putnext`; Baba Is AI `make-win` and `two-room-make-you-make-win`; TextWorld treasure hunter and cooking; Crafter; NLE; and MiniHack MazeWalk 9×9 and Quest Easy. Exact IDs are in the JSON. Both launchers now select this scope with `--selection-plan`; `prepare_parity.py` generates the ten tasks grouped by environment. Without an explicit selector, the legacy `sanity` split remains all 58 seed-0 families.

Start at concurrency 1 with no automatic job retries. Request a finite sanity budget first, then estimate later stages from observed calls, latency and token usage. Native allowances sum to 543,520 actions per full side and 3,466,624 across the primary schedule; these are worst-case logical-action allowances, not cost predictions. Confirm pricing, quotas and per-stage limits before spending.

**NLE needs explicit timeout planning.** Live launchers require an explicit timeout; the proposed diagnostic limit of 1,800 seconds is not an agreed formal deadline. Exhausting 100,000 model actions in that window would require an average below 18 ms per action. A bounded diagnostic that hits its wall-clock limit is incomplete infrastructure execution, never a scored zero. Agree and freeze per-environment execution deadlines, identical between sides, using measured latency and native budgets before the first full pair. Harbor's outer agent deadline includes a separate 120-second artifact-collection allowance. If the approved resources cannot support the original scope, agree a new declared experiment rather than silently shortening NLE or excluding failed cases.

## Supplementary standard-agent experiment

To address the guide's custom-agent scenario, propose **Claude Code 2.1.322 + `claude-haiku-4-5-20251001`**, using Harbor's standard-agent integration and the public `balrog observe` / `balrog act` commands. Run the same ten smoke tasks, then the **58 seed-0 task families × three fresh runs**: **10 + 174 = 184 Harbor-only episodes**. This predetermined subset spans all six environments and is selected by task family, not success. Report subset progression as mean ± sample SEM across its three complete runs; smoke results are excluded. This tests the standard interface and is not a second matched upstream parity claim.

The [CLI release exists](https://github.com/anthropics/claude-code/releases/tag/v2.1.322) and the [dated model is listed as active](https://platform.claude.com/docs/en/about-claude/model-deprecations) when checked on 2026-11-21. **2077ai availability, Anthropic Messages/tool-use compatibility and the effective CLI configuration are unverified.** Confirm these, freeze the configuration and approve its separate budget before execution. No CLI-agent experiment has run. The primary and supplementary proposals together total **1,734 scheduled episodes** if both are approved; their results remain separate.

## Preflight, reporting and retained evidence

Explicit task-ID selection, current Harbor configuration with top-level `n_concurrent_trials` and zero job retries, and complete game dependency locks are implemented. See the [offline preparation report](../docs/parity_preparation.md) for the validation evidence and remaining gates. The hash-locked host harness now proposes Harbor 0.27.0; the historical 255-task run retains its 0.26.0 provenance. Freeze the final adapter/upstream revisions, task snapshots, images, SDKs and effective settings before model calls.

Both launchers can validate Docker or Daytona configuration without keys. The native Daytona path runs the original evaluator and is covered by local lifecycle tests; its actual cloud execution is untested. Daytona runtime equivalence, sidecar isolation, protected artifact collection and separate grading still require remote correct, wrong and saved-result controls. A valid configuration is not evidence that a matched Daytona experiment is ready. The supplementary CLI configuration remains subject to maintainer model/protocol confirmation.

Report primary **mean ± sample SEM across three complete runs** per environment and for the equally weighted aggregate, with raw run arrays. Use `SEM = sqrt(sum((x-mean)^2)/(n*(n-1)))`; one run has no defined SEM. Check run-score range overlap per environment and overall. All-zero or otherwise uninformative results in an environment trigger diagnosis and an agreed stronger-model experiment, not a parity claim based only on overlap.

Retain genuine agent failures at native scores. Preserve infrastructure failures and retries separately; never impute zero, select the better retry or add runs until ranges overlap. A source, prompt, scoring, budget or model change creates a new paired experiment revision. Save requests/responses and returned model IDs, action tapes, final native artifacts, agent logs, verifier inputs/results, task snapshots, configuration hashes and usage. Publish redacted raw evidence in the agreed Hugging Face location and a reproducible original-side fork, then fill the README and `parity_experiment.json` from actual results.

## Requested confirmation

1. Accept the original 255-case comparison and the three reference treatments above, or specify a shared corrected benchmark revision.
2. Confirm the primary agent/model, staged run counts, Daytona deployment and per-stage resource limits; provision 2077ai and Daytona keys privately.
3. Approve the proposed standard-agent/model, 58-family subset and three runs, subject to gateway compatibility and a separately agreed budget.
