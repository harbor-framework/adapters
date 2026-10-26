# GDPval migration acceptance — 2026-10-26

Accepted scope: migration of Harbor PR #1384 into the standalone adapters repository,
plus basic checks and one real-model end-to-end smoke. The user accepted this limited
scope on 2026-10-26. This is not acceptance of official GDPval score equivalence,
full-dataset model performance, or unrestricted public-network evaluation security.

## Provenance and changes

Source PR: https://github.com/harbor-framework/harbor/pull/1384
Pinned head: `d935522f2837ba4a05f862741aa014f9cd78b151`.
The dataset loader, instruction template, and Oracle script match that head.
Local changes cover standalone packaging/docs, network profiles, separate verifier
execution, stale-score removal, symlink rejection, and strict judge-error handling.
Normal judge prompts, content extraction, and win/tie/loss mapping remain unchanged.

## Evidence

- Five offline regression tests passed on 2026-10-26.
- Structural validation: 31 passed, zero errors, six historical single-run parity warnings.
- Historical three-task PDF/DOCX/XLSX Oracle and NOP checks exercise packaging and
  missing-output behavior; Oracle uses an exact-byte shortcut, not semantic grading.
- Real task `7b08cd4d-df60-41ae-9102-8aaa49306ba2`: Harbor 0.23.0,
  terminus-2, `openai/claude-sonnet-5`, judge `anthropic/claude-sonnet-5`,
  one attempt, concurrency one, no retries, agent timeout multiplier 0.25,
  no explicit max_turns. Model IDs are relay labels, not independently verified identities.
- Run `2026-10-26__10-28-11` completed in 5m31s with zero trial exceptions.
  It produced `Fall Music Tour Output.xlsx`; the real judge returned gold/0.
  Judge rationale: correct grand totals but missing required party breakdowns and
  differences in expense allocation. These findings were not independently audited.
- Local ignored evidence: `/tmp/gdpval-live-jobs/2026-10-26__10-28-11/`;
  IDE copy: repository `tmp/gdpval-live-20261026-102811/`.
  These local paths are not published evidence or files included in this commit.

## Limits retained

Official paired per-task model outputs, grades, trajectories, and complete runnable
configurations were not located in the public sources checked. No official parity
claim is made. Historical `parity_experiment.json` entries predate the current
pairwise verifier and are engineering references only.

The adapter mean uses win=1, tie=0.5, loss=0. Official wins-plus-ties percentages
use a different aggregate and must not be compared directly. The 185-task subset
also differs from the official 220-task gold set.

Exact-byte Gold copies receive 1, although approximately equivalent independently
produced files may receive tie/0.5. Office files are judged through extracted XML,
not full rendering or spreadsheet recalculation; multimedia coverage is limited.
Default public networking does not block public Gold access. Verifier isolation
under agent cleanup failure remains unaccepted; see SECURITY.md.

## Official sources checked

- https://huggingface.co/datasets/openai/gdpval/tree/main
- https://arxiv.org/html/2510.04374v1 (sections 3.1, 4, A.6)
- https://evals.openai.com/gdpval/grading
- https://evals.openai.com/gdpval/leaderboard

The current grading guidance recommends human expert pairwise preferences and
allows local LLM judging as an estimate. The hosted leaderboard is no longer active.
