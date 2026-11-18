# Saved validation evidence

This folder contains compact summaries of completed local validation experiments for the Draft BALROG adapter. Packaging did not run games or call models. The unchanged baseline contains **255 completed reference tasks, 239 full oracles and 16 diagnostic references**, with zero infrastructure errors in the five saved baseline Harbor jobs. This does **not** meet the all-oracle acceptance requirement. No real-model parity experiment has been run.

| Environment | Fixed cases completed | Full oracles | Diagnostic references | Mean native progression |
| --- | ---: | ---: | ---: | ---: |
| BabyAI | 50 | 50 | 0 | 1 |
| Baba Is AI | 120 | 120 | 0 | 1 |
| TextWorld | 30 | 30 | 0 | 1 |
| MiniHack | 40 | 39 | 1 | 0.975 |
| NetHack / NLE | 5 | 0 | 5 | 0.0030784538150722346 |
| Crafter | 10 | 0 | 10 | 0.09090909090909091 |

These are offline reference-controller scores, not model performance. The full-oracle count is a coverage count, not an overall benchmark score. A diagnostic reference can complete correctly with a partial or zero native score.

## Contents and provenance

- [baseline.json](baseline.json) lists every fixed task identifier, seed, native budget, initial observation hash, native score, step count, termination flags and oracle classification. Raw Harbor trial and verifier-result hashes bind the summary rows to the saved outputs.
- [validator_reports.json](validator_reports.json) preserves selected fields and all per-case findings from the saved validators. It distinguishes exact native transition checks from cases checked only against server replay and a native final score.
- [provenance.json](provenance.json) records fixture/source pins, source archive hashes, the saved job summaries, generated snapshot hashes, current review file hashes and the raw-source inventory. The current repository review base is separate from the earlier local experiment provenance. An execution adapter git commit and a complete attested image inventory were not recorded; generated snapshot hashes observed during packaging do not retroactively prove execution image identity.
- [proposals/minihack_200.json](proposals/minihack_200.json) describes a **separate, unapproved** 40-case Harbor experiment: all 40 score 1, all replays pass, and 1,531 transitions are checked. Only the ten Boxoban cases use a proposed 200-action limit; the other thirty retain 100. The original fixture remains unchanged. The included proof summary reports exhaustive unit-action BFS: the hard seed-0 board needs at least 104 legal actions, exceeding the original 100. Proof artifacts are identified by hashes; the search program and full state exploration are not packaged here.
- [diagnostics/crafter_private_seed6.json](diagnostics/crafter_private_seed6.json) records **one unapproved privileged-controller experiment** in real Harbor: seed 6 reaches native score 1 after 725 of the original 2,000 allowed actions. Fresh replay diverges at step 25, so the result uses the protected native-state score and explicitly records `replay_verified: false`. It adds no baseline full oracle. The private controller and its installation mechanism are not included.
- [diagnostics/crafter_tactics.json](diagnostics/crafter_tactics.json) retains the negative frozen-policy result: 0/10 full-score successes, all ten predetermined seeds retained, 9,791 legal live actions. Correct immediate-health predictions and preserved original-state fingerprints during copied-state search did not establish reliable long-term completion or deterministic replay.
- [diagnostics/nle_ceiling.json](diagnostics/nle_ceiling.json) records a source-derived scorer ceiling of 0.8067964442444019 and synthetic unit checks. It is not a native trajectory attaining that ceiling, and no fixed-seed ascension was obtained. The scorer proposal remains unapplied.
- [checksums.json](checksums.json) covers the files in this bundle. Checksums provide internal integrity checks, not an external signature or independent reproduction.
- [submission_checks.json](submission_checks.json) records the final saved local checks: 53 unit tests passed and one Windows symlink test skipped; 44 offline runtime tests passed; 37 wheel module files matched the source bytes; and the uv project CLI generated and checked one case for each of the six environments. This was not an installed-wheel execution test. The structure check retains one error for empty parity data and two warnings. Generation and packaging checks did not replay games.

All raw sources referenced by workspace-relative names are **not uploaded in this folder**. They include Harbor job directories, verifier transition logs, native probe output and generated task snapshots. Game assets, large research controllers, generated Compose files, host absolute paths and credentials are excluded. The committed task fixtures and adapter source remain the inputs for a fresh reproduction; these saved summaries are evidence to inspect, not a replacement for that reproduction.

## Check the submitted summaries

From the adapter directory, using Python 3.10 or newer:

```sh
python scripts/build_validation_bundle.py --check
```

This command needs only the checkout. It verifies bundle hashes, exact fixture coverage, seeds, budgets, initial hashes, source pins, native fixture scores, oracle classifications, per-environment aggregates and the separation of proposals/diagnostics. It checks common accidental private-path and credential patterns. It does not start Docker, replay actions, contact an API, reconstruct omitted logs, or establish that a saved run was independently reproduced.

Rebuilding the summaries requires the original local research artifacts, which are not part of this contribution:

```sh
python scripts/build_validation_bundle.py --workspace-root <original-development-workspace>
```

The builder reads an explicit set of saved reports and their referenced trial/verifier results, selects publishable fields, checks them against the committed fixtures, and regenerates bundle checksums. It does not modify native scores, source fixtures or game rules.

## What the complete reference checker verifies

For a new run with its generated task snapshot and complete raw Harbor job artifacts:

```sh
python scripts/check_suite_reference.py \
  --dataset <generated-task-snapshot> \
  --job <raw-Harbor-job> \
  --output <validator-report.json>
```

The strict checker requires a finished job, exact nonduplicate coverage, matching job/trial/task identities, ordered timestamps, no trial exceptions, valid rewards, and no missing or orphan verifier artifacts. It compares task, seed, native budget and initial hash with the generated episode; checks native score, fresh-replay score, Harbor reward and reward file agreement; and checks action/transition counts, legal budget/termination boundaries, and full-length native transition fixtures where available. Partial references remain diagnostic. Its strict baseline path requires successful replay; it does not certify the private Crafter fallback experiment.

The archived jobs contain host-local naive timestamps. Their saved reports explicitly interpret these as UTC-08:00; reproducing their checks requires `--naive-utc-offset=-08:00`. This option is unnecessary when the new run records timezone-aware timestamps. Some early artifacts used six-significant-digit reward text; the checker tolerates only the documented corresponding rounding and reports it per case. Current generated reward files use 17 significant digits.

BabyAI also has its dedicated saved full-split validator. The saved baseline spans several generated runtime snapshots, rather than one simultaneous run of the final review snapshot. Later reset-order, zero-action and Crafter scoring checks are distinct evidence; their existence does not turn an earlier job into a run of later code. No API credential was used, no model result is included, and no claim of Ready for Review is made by this bundle.
