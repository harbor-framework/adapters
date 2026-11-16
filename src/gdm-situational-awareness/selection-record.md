# GDM Situational Awareness (gdm_self_reasoning) — selection record

Date: 2026-11-15 · Evaluator: Muse Code session (this VM) ·
Checklist: workspace-local `benchmark-selection-checklist.md` (not in this repo), Parts 1–9

## Identity

- Upstream repo / paper / license: [arXiv:2505.01420](https://arxiv.org/abs/2505.01420)
  (Phuong et al., Google DeepMind, 2025); open-source release
  `UKGovernmentBEIS/inspect_evals` `src/inspect_evals/gdm_self_reasoning`,
  MIT (`LICENSE`, UK AI Security Institute), pinned commit
  `a68dade7efb803ef50c8442d3f16264b293d1414`.
- Candidate adapter-name (lowercase-dashes): `gdm-situational-awareness`,
  branch: `gdm-adapters` (shared with gdm-stealth this session).
- Dataset id: `google-deepmind/gdm-situational-awareness`; org rationale:
  single clear owner (Google DeepMind).
- Adapter List status (1.1): v2.0 sheet row 242, `To be taken`, no
  contributor/reviewer/PR; absent from the v1 `Adapter List` sheet.
  Note the row's description ("suite of 16") covers stealth too — scope
  was settled by user decision 2026-11-15 as the 11 SA evals only.
- Registry (1.2): not verified (`harbor` was installed this session;
  run `harbor dataset list` before claiming). Existing `src/` (1.3):
  absent (no `gdm*`/`situational`/`self_reasoning` directory among 88).
- Terminal-Bench (1.4): no adapter known in this repo's records.
- Team contacted (1.5): **no** — required before parity (Step 4).

## Components (Part 2)

- Instructions (2A): `natural-language-prompt`, one objective per
  challenge; hints vary by sample (`easy` adds noticing+execution
  hints, `hard` none). Rewriting: `as-is` (verbatim); leaks: `clean`
  (objectives contain no answers; checkers live host-side upstream and
  are ported only into `tests/`); prompt modification: `none`.
- Environment (2B): OS=`linux`, GPU=`none`, containers=`single-container`
  per challenge (own Dockerfile from `python:3.9-slim-buster` base;
  `max_tokens` upstream also defines a separate verifier sandbox),
  network=`offline-ok` at runtime (upstream compose `network_mode: none`),
  size=`small`. Resources: 1 cpu / 2048 MB / 10240 MB assigned by adapter
  (upstream has no Harbor-equivalent declaration). Dependency pinning:
  base image is EOL (`3.9-slim-buster`) — availability risk, 2B.8=`pinnable
  but stale`. Canary strings: `ok` (none present; validator scans for them).
- Tests (2C): type=`programmatic-metric` (binary final-state checks
  over config/result side files; Game-of-Life execution for
  `max_tokens`), judge=`none`, reward-map=`binary`, stages=
  `single-stage` per trial, deterministic=`deterministic`
  (verifier); agent sampling is the noise source. Original metric:
  per-challenge solved iff ≥1 of 50 trials (Inspect default 10 epochs).
- Oracle (2D): original provides `none`; production=
  `AI-generated-feasible` realized as hand-scripted solutions per
  challenge; broken oracles `n/a`; 100% under Harbor: **demonstrated**
  2026-11-15 (22/22 trials, mean 1.000, no exceptions; Harbor 0.26.0).
  `approved_directories` initially failed to build because Debian
  buster left the main apt mirrors; fixed by pointing apt at
  `archive.debian.org` in its generated Dockerfile.

## Scope (Part 3)

- Splits / sizes / adaptable: one split `full`, 11 challenges × 2
  samples = 22, all `adaptable: true`.
- Exclusions + reasons: hint combos (`easy,hard`) and (`hard,easy`)
  excluded because upstream `_KEEP_COMBOS` drops them. Fifth paper
  stealth eval belongs to the sibling adapter's family and is
  unreleased upstream — out of scope here.
- Task id scheme: upstream sample ids
  (`<challenge>_<noticing>_<execution>`), sanitized; stable and unique.
  Tags requested: `v1.0` (default).

## Attribution (Part 4)

- Authors: the 9 paper authors (no emails known; omitted, permitted).
  Citation: arXiv:2505.01420 (BibTeX in README). License: MIT for the
  Inspect code/data used; paper text not redistributed.

## Agent design (Part 5)

- G1: `agent-harness` (Inspect solver with planning scaffolding).
  G2: `no` (no Harbor-compatible agent upstream; solver is model-
  agnostic Inspect code). G3: `unavailable` in Harbor.
- Scenario: **S3b** (custom agent in place; no separate dataset
  required for parity, CLI agents explicitly non-parity).
  User decision 2026-11-15: faithful custom agent first.
- Fork needed: parity side is the upstream Inspect repo itself (pin
  recorded; a fork is only needed if Inspect-side changes are required).
  Custom agent needed: yes — port of `solver_pipeline` + per-challenge
  dynamics in `tests/task_metadata.json`. Standard-agent
  generalization run: optional, explicitly not parity evidence.
- `harness` value: `"agent"`; `supported_agents`: `["None"]`;
  `added_agents`: `["gdm-self-reasoning-parity-agent@0.1.0"]`.

## Parity (Part 6)

- Original runnable: `yes` (Inspect tasks incl. tests in-repo).
  Runs per side: ≥3 runs × 10–50 epochs (team to set). Metric:
  binary success → per-trial rate + solved-challenges count.
- Pinned agent@version / model-id: TBD with team; solver dynamics,
  message_limit=80, tools, and prompts are already pinned in metadata.
- Cost estimate: unknown (22 tasks × epochs × runs × 2 sides; cheap
  models plausible) — `parity_costs: null`. Full or subset: full (22).
- Pitfall flags (6.15–6.20): `no_hint` samples are capability probes —
  expect near-zero success and wide per-trial variance (6.4 high for
  aggregation by at_least_1); `latency_calculator`/`max_messages`
  outcomes depend on harness counters invisible to a final-state
  verifier (6.8 effective-runtime class); no numerical-fit/null-loss
  or streaming-specific risks (6.16–6.17 `low`).

## Readiness (Part 7)

Generation implemented (`--output-dir/--limit/--overwrite/--task-ids`
plus `--source-dir`); 22 tasks generated and inspected; verifier
synthetic tests 25/25; Harbor oracle verification 22/22 at reward 1.0.
README sections and metadata written; HF upload and registry steps
are standard.

## Verdict

- **GO-WITH-TEAM** (generation, oracle, and custom agent done; parity gated on team terms + real-model smoke run).
- Blockers: none for generation or oracle (Step 3 done 2026-11-15).
  For acceptance: (a) Step 4 team agreement incl. claim of Adapter
  List row 242; (b) first real-model smoke run of the implemented custom parity agent;
  (c) registry existence check (1.2); (d) WIP PR with the oracle
  result (guide asks for a screenshot; the Harbor job result is the
  stronger evidence to link).
- Open questions for team: epochs (10 vs paper 50) and run count;
  whether CLI-agent results should also be published as a separate
  non-parity dataset; reviewer assignment (docs disagree:
  `@Slimshilin` vs `@XiangningLin`).
- Tags: S3b · deterministic · linux-cpu · oracle=AI-built(scripted) ·
  full parity · cost=TBD · native · splits=[full] · GitHub
