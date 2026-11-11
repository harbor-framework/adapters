# Proposed ARC-AGI-3 validation and parity protocol

Status: awaiting maintainer agreement; no model parity runs started.
Context: harbor-framework/harbor#2728 and its October 5 migration request.

## Decisions requested

1. Select the original runner/evaluator and upstream revision. The vendored engine has
   file hashes but lacks its original upstream commit. Review reset and first-reach
   accounting differences before treating score agreement as benchmark fidelity.
2. Confirm whether replayed wins on every included game establish oracle success, with
   efficiency reported separately. Coverage is partial: complete all 25 games or agree
   an explicitly documented subset before registration. Do not select a parity subset
   based on favorable model outcomes.
3. Select an exact agent version and dated model ID. Claude Code is the proposed first
   agent; no model provider or API credentials are assumed.
4. Freeze game IDs/seeds, primary metric, prompts, tool interfaces, action/token/turn
   budgets, timeouts, network policy, sampling parameters, retries and cost budget.

## Distinct evidence

- Structure: 25 tasks generated with stable names and required assets.
- Runtime/verification: public responses exclude baselines; the scoring formula is
  preserved on equal progress; transport failures produce errors.
- Oracle: legal actions replay to `win` on a fixed game/seed via the public API.
- Model parity: fresh matched model runs on reference and Harbor. Neither historical
  scores nor replaying the same actions on two wrappers establishes model parity.

## Execution after agreement

Freeze code, game hashes, dependencies, effective commands and non-secret settings.
Confirm the selected games are solvable. Run a predeclared 5–10-game sanity cohort on
both sides, covering click and directional games; then one complete cohort on both
sides; investigate differences before reaching three repetitions on both sides.

Maintain an attempt ledger by side/game/seed/repetition. Distinguish genuine failures,
infrastructure failures and diagnostics; do not select the best retry. Save observations,
actions, terminal state, action counts and rewards. Sanitize credentials and private
model reasoning before publication.

## Reporting and delivery

Report coverage, denominators, per-game discrepancies, raw run scores and mean ± sample
SEM. Apply the guide's run-range overlap criterion alongside fidelity checks. Keep
oracle/verifier/model tables separate. Populate parity_experiment.json only with measured
results. After acceptance, upload sanitized parity/oracle artifacts, submit generated tasks
and dataset.toml to harbor-datasets, and verify registry execution after team publication.
