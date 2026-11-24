# GDM Stealth — selection record

Date: 2026-11-15 · Evaluator: Muse Code session (this VM) ·
Checklist: workspace-local `benchmark-selection-checklist.md` (not in this repo), Parts 1–9

## Identity

- Upstream repo / paper / license: [arXiv:2505.01420](https://arxiv.org/abs/2505.01420)
  (Phuong et al., Google DeepMind, 2025); open-source release
  `UKGovernmentBEIS/inspect_evals` `src/inspect_evals/gdm_stealth`,
  MIT (`LICENSE`, UK AI Security Institute), pinned commit
  `a68dade7efb803ef50c8442d3f16264b293d1414`.
- Candidate adapter-name (lowercase-dashes): `gdm-stealth`,
  branch: `gdm-adapters` (shared with gdm-situational-awareness).
- Dataset id: `google-deepmind/gdm-stealth`; org rationale: single
  clear owner (Google DeepMind).
- Adapter List status (1.1): v2.0 sheet row 210, `To be taken`, no
  contributor/reviewer/PR; absent from the v1 sheet. Citations field
  on the row (2) disagrees with the SA row (1) for the same paper.
- Registry (1.2): not verified (run `harbor dataset list` before
  claiming). Existing `src/` (1.3): absent. Terminal-Bench (1.4): none.
- Team contacted (1.5): **no** — required before parity, and before
  spending on rater models.

## Components (Part 2)

- Instructions (2A): `natural-language-prompt` with an explicit secret
  objective given to the agent (by design); `strategic_rule_breaking`
  input is a fixed welcome notification, objective lives in the
  handbook/persona system message. Rewriting: `as-is`; leaks:
  `clean` w.r.t. scoring (checker/rater logic stays host-side and is
  not copied into containers); prompt modification: `none`.
- Environment (2B): OS=`linux`, GPU=`none`, containers=
  `single-container` file sandbox (`ubuntu`, `/home/agent`) — but the
  real environment (email checker/DB, support simulator) is hosted
  by the **solver**, 2B.4=`needs-sidecars` in spirit: harness-hosted
  stateful services + LLM raters. Network: sandbox
  `offline-ok`, harness `needs-live-third-party-service` (model APIs).
  Size=`small`. Pinning: rater models pinnable by dated ID; the
  customer-support handbook is generated from live tool descriptions.
- Tests (2C): type=`mixed` (programmatic state checks +
  `LLM-as-judge`-class raters in-loop), judge: rater
  `google/gemini-2.5-pro-preview-05-06`, judger/chat
  `google/gemini-2.0-flash` (defaults; keys live host-side, not in
  `[verifier.env]`), reward-map=`binary` (AI-secretary) / `float`
  (cover: criteria/7; strategic: score/33), stages=`multi-stage`
  (tool episode → checker → score), deterministic=
  `stochastic-verifier` (LLM raters). Rater capability is part of
  task difficulty (upstream warning) — pinning is load-bearing.
- Oracle (2D): original provides `none`; production=`infeasible` as
  scripts (success requires interactive episodes vs LLM raters);
  guide path: derive from successful agent episodes with human
  supervision, team case-by-case. `solve.sh` exits 1 by design.
  100% oracle reward: `not-achievable` at generation stage — this is
  the family's hardest acceptance problem.

## Scope (Part 3)

- Splits / sizes / adaptable: `full` = 13 samples under upstream
  default filters (oversight 2, classifier 9, cover 1, strategic 1),
  adaptable `true` **given** a custom agent. Upstream `eval.yaml`
  claims 14 (cover 2) — code default `hard_only=True` wins;
  `--cover-with-hint` generates the 14th.
- Exclusions + reasons: 114 of 125 AI-secretary register entries and
  strategic v1 excluded by upstream FSF-v2 filters (preserved);
  paper's 5th stealth eval unreleased upstream (excluded, revisit
  on release); SA evals belong to the sibling adapter.
- Task id scheme: upstream `<dataset>--<challenge_name>` sample key, sanitized to single hyphens for directory/task names;
  stable (register is a checked-in generated file at the pinned commit).
  Tags requested: `v1.0`.

## Attribution (Part 4)

Authors: the 9 paper authors (emails omitted). Citation in README.
License: MIT (Inspect). Fictional in-world secrets in prompts are
upstream task content; no real credentials are included.

## Agent design (Part 5)

- G1: `agent-harness` (Inspect solver, planning scaffold, tool loop).
  G2: `no`. G3: `unavailable` (custom solver + tool hosts + raters).
- Scenario: **S3b** for parity (custom agent replicating the Inspect
  solver; user decision 2026-11-15: faithful custom agent first).
  A CLI-agent dataset would be a separate **S3a** decision requiring
  the tool hosts to move into the container.
- Fork needed: no for generation; parity original side is upstream
  Inspect at the pinned commit. Custom agent: must host
  `ai_secretary` checker, `cover_your_tracks` database+log, and
  `customer_support_env` with chat/oversight models, then write the
  outcome file.
- `harness`: `"agent"`; `supported_agents`: `["None"]`;
  `added_agents`: `["gdm-stealth-parity-agent@0.1.0"]`.

## Parity (Part 6)

- Original runnable: `yes` with provider keys (Google defaults).
  Runs per side: team to set (paper 50 trials; Inspect 10 epochs).
  Metric: per-task (binary / criteria÷7 / score÷33), mean±SEM ≥3 runs.
- Pinning: agent version = custom-agent commit; model IDs dated;
  rater/judger/chat roles identical both sides (metadata records
  defaults); tool/prompt surfaces pinned in `task_metadata.json`,
  except strategic handbook rendering (see below).
- Cost: **high class** until measured — 13 tasks × epochs × runs × 2
  sides, plus a slow capable rater on every classifier-evasion email.
  `parity_costs: null`. Subset option exists (upstream register
  filters) but changes the benchmark definition — team decision.
- Pitfalls: outcome-file verifier has a trust boundary (only the
  parity agent's outcomes count); strategic system prompt is
  runtime-generated (handbook from tool briefs) so prompt parity for
  that task is **not byte-verified**; rater drift/version changes
  directly move scores (6.20 `check-needed`).

## Readiness (Part 7)

Generation implemented and verified: sample sets equal upstream
filter-function outputs (executed check), prompts/`email_tasks.txt`
byte-checked, outcome-verifier mapping unit-checked. Not runnable
end-to-end by any stock agent — by design; the custom parity agent runs them end-to-end (fake-model episodes verified for all three tool hosts).

## Verdict

- **GO-WITH-TEAM** (generation done; acceptance gated hard).
- Blockers for acceptance: (a) Step 4 team agreement + claim row 210;
  (b) first real-model smoke run of the implemented custom parity agent / rater hosting; (c) oracle strategy
  decision (no scripted oracle possible); (d) parity budget for
  50-trial × rater-heavy protocol; (e) strategic handbook rendering
  parity; (f) registry existence check (1.2).
- Open questions: epochs/runs and rater budget; accept outcome-file
  verifier trust model or fund an in-container tool-host (S3a)
  variant; publish the `with_hint` sample or stay at upstream default 13.
- Tags: S3b (S3a possible later) · LLM-judge/mixed · linux-cpu +
  harness-hosted services · oracle=none · full parity (default
  filters) · cost=high(TBD) · native · splits=[full] · GitHub
