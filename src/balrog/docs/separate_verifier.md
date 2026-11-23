# Separate verifier migration

Generated BALROG tasks use Harbor 0.26.0's separate verifier support. This implements the packaging change requested after [Harbor #3712](https://github.com/harbor-framework/harbor/pull/3712), while preserving the native game, actions, budgets, progression metric and replay policy. Existing generated task directories must be regenerated; installing a newer Harbor version does not migrate them.

## Execution and evidence transfer

1. The agent interacts with the existing isolated `game` service through observations and actions. Simulator state and action history remain in that service.
2. After the agent finishes, Harbor runs `python -I /app/export_result.py` as the game user through `[[verifier.collect]]`. The exporter authenticates to the service's local `/result` endpoint using its private `RESULT_TOKEN`. The existing result method freezes the episode under its lock and performs native scoring and replay checks.
3. The exporter writes the returned native result atomically to `/var/lib/balrog/result.json`. It removes any previous export before requesting a new one, so an export failure cannot leave that old file in place. The artifact contains the task identity, original action records, native score and replay evidence; it contains no token.
4. The task declares that exact artifact path with `service = "game"`. Harbor collects it from the game sidecar before stopping the original environment, then restores it at the same absolute path in the separate verifier. The path does not overlap the agent's `/logs/artifacts` tree.
5. The dedicated `tests/Dockerfile` bundles `test.sh`, `verifier.py` and the generated `task_config.json`. The verifier checks the native result schema and replay policy, and matches task ID, environment, native task, seed, action budget and initial-observation hash against that frozen configuration. It writes the unchanged progression value to `/logs/verifier/reward.txt` and preserves the result in `/logs/verifier/result.json`.

The verifier has its own environment configuration and does not inherit the agent-container healthcheck. It needs neither the original live game nor its token. The collect request timeout is 100 seconds for BabyAI and 1,700 seconds for the other environments, within collect-hook limits of 120 and 1,800 seconds respectively.

Artifact provenance matters: the verifier validates a result exported by the protected game service. Its schema checks alone do not authenticate an arbitrary agent-authored score file. Do not change the artifact source to the agent container or allow another artifact to overwrite that destination. Review the saved artifact manifest for the exact source, `service = "game"` and successful collection.

Harbor may log collect or transfer failures as warnings. The verifier therefore removes stale grading outputs and fails without a reward if evidence is missing, malformed or belongs to another frozen task. A valid failed episode receives reward 0; an infrastructure failure does not. A receipt for an earlier run of the identical task cannot be distinguished by task identity alone; freshness relies on collecting from the newly created protected game service, not on a cryptographic per-trial nonce.

The native scoring policy remains unchanged. In particular, the disclosed Crafter native-state fallback remains subject to maintainer review, and this migration does not address the NetHack scoring issue or MiniHack action-budget proposal.

## Validation status

The full post-migration Docker job, `separate-verifier-full-v1`, completed **255/255 tasks with zero exceptions and zero retries** on Harbor **0.26.0**. It retained **239 full-score oracles and 16 diagnostic references**. Every trial used a separate verifier and successfully collected the protected result from service `game`; the offline verifier result matched that artifact. All 255 fresh replays passed, all scores matched the frozen references, and the generated tasks and source snapshots were unchanged. The existing Crafter fallback was not needed in this run. See the [full validation report](separate_verifier_full_validation.md) and [255-task evidence summary](separate_verifier_full_validation.json).

The saved 255-case baseline predates this migration and ran the grader in the agent environment. It establishes historical native/reference behavior, not successful separate-verifier execution.

The original `validation/` bundle and its checksums remain unchanged. Its source hashes describe the earlier review snapshot, so a strict `python scripts/build_validation_bundle.py --check` intentionally rejects the changed runtime. To audit the archived bundle, run `python scripts/build_validation_bundle.py --check --historical`: all bundle, fixture and score checks remain enforced, while source differences are listed explicitly. This is an integrity check of historical evidence, not validation of the new verifier.

Separate representative Docker checks completed on Harbor **0.26.0** for `babyai-goto-seed-0`, using its original 64-action budget and frozen initial state:

| Submission | Actual reward | Actions | Episode outcome | Harbor job / trial |
|------------|---------------|---------|-----------------|--------------------|
| Reference solution | **1.0** | 3 | Terminated; replay verified | `separate-verifier-babyai-correct-v2` / `babyai-goto-seed-0__sdSUCHS` |
| Known-wrong submission: 64 legal `turn left` actions | **0.0** | 64 | Truncated; replay verified | `separate-verifier-babyai-wrong-v2` / `babyai-goto-seed-0__9YcJD7N` |

Both trials completed with zero exceptions and recorded `verifier_environment_mode = "separate"`. Both artifact manifests record `/var/lib/balrog/result.json` with `service = "game"` and `status = "ok"`. The result in the dedicated verifier matched the collected native progression.

A verifier-only regrade, `babyai-correct-separate-regrade-v2`, also returned **1.0** with zero exceptions. Its agent execution, agent setup and original environment setup fields are null: the saved evidence was graded without rerunning the agent or game episode.

The [representative validation summary](separate_verifier_validation.json) records these control trials and their hashes. They validate correct/incorrect grading and saved-evidence regrading; full-suite coverage is established by the separate 255-task run above. Raw jobs, artifacts and earlier attempts remain saved locally and have not been published to Hugging Face. The full run and representative controls do not fix incomplete oracles or constitute model parity. No model API key was required.

Local regression checks completed with 65 host tests passing and one Windows symlink-permission skip, plus 10 native BabyAI runtime tests passing. Four additional focused tests verified historical-mode behavior, including rejection of corrupted evidence and changed oracle counts even when a checksum is recomputed. The repository adapter contract check still reports the existing empty-parity error and two warnings; this migration does not establish Ready for Review status.

## Artifact retention and regrading

Preserve complete original job directories, including failed attempts. Keep:

- Original action records/submissions and agent/model logs.
- The collected game `result.json`, artifact manifest and collect-hook logs.
- Verifier result, reward and diagnostic files, plus job/trial configuration and results.
- The exact generated task, source revisions, runtime provenance and verifier implementation used.

The saved native result includes the action history needed to inspect what the agent submitted. The collected artifact and its manifest allow Harbor to run the offline verifier after the original game has been deleted. Regrading does not rerun the agent or collect hook; it cannot recover evidence that was never saved. Historical shared-verifier jobs need an explicit evidence/provenance audit before any conversion for regrading.

For a completed separate-verifier trial, Harbor 0.26.0 supports:

```bash
harbor trials regrade SOURCE_TRIAL -p GENERATED_TASK -e docker --trial-name balrog-separate-regrade -o REGRADES_DIR
```

Use a new output location and retain the source trial. Check that the regraded score agrees with the original saved progression and that no agent execution occurred. The successful representative regrade is recorded above; the command is the general reproduction procedure for other saved trials.

Model parity has not run. When it does, preserve the same evidence and upload the experiment artifacts to the intended Hugging Face fork after removing credentials. No Hugging Face publication is implied by this local migration.

Harbor references: [separate verifier](https://github.com/harbor-framework/harbor/blob/v0.26.0/docs-mintlify/tasks/separate-verifier.mdx), [sidecar-artifact example](https://github.com/harbor-framework/harbor/blob/v0.26.0/examples/tasks/sidecar-artifacts/task.toml).
