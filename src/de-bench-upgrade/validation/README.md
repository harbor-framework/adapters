# Validation evidence

This directory records implementation/scoring validation. It contains no agent
parity results and does not claim that a Modal run was performed.
Terminal log line endings and trailing whitespace are normalized for Git.

| Gate | Result | Evidence |
|---|---|---|
| Pinned upstream inventory | 62 ready tasks, 214 scoring-primitive checks, 62 compatible | `inventory.json` |
| Local upstream vs adapter scoring | 248/248 comparisons match, including per-check tri-state outcomes | `scoring-full.json` |
| Reference solutions in local comparison | 62/62 pass | `scoring-full.json` |
| Untouched and delivered baseline | All fail, on both scoring paths | `scoring-full.json` |
| Reference solution fully reverted, delivery retained | All fail, on both scoring paths | `scoring-full.json` |
| Original `_score_trial` in offline Docker | 62/62 oracle pass, 62/62 delivered-baseline fail; oracle check maps equal Harbor | `original-docker.json` |
| Harbor Docker oracle, scoring-smoke profile | 62/62 reward 1, 0 exceptions | `harbor-oracle-full.json` |
| Harbor rerun after image digest/Git bootstrap changes | 5/5 reward 1, 0 exceptions | `harbor-oracle-final-smoke.json` |
| Fresh offline Docker baseline and oracle | 5/5 baseline fail, 5/5 oracle pass | `docker-states.json` |
| Targeted partial reversion in Docker | 3 fail; 2 remain passing | `docker-states.json` |
| Adapter regression suite | 7 passed | command below |
| Installable CLI and distribution | Locked uv CLI, sdist and wheel build passed | commands below |
| Repository structure validator | 28 passed; required parity file absent | `structure-check.txt` |
| Original scoring body in full runtime | 62 oracle pass, 62 delivered-baseline fail | `original-runtime-docker.json` |
| Harbor Docker oracle, final locked full runtime | 62/62 reward 1, 0 exceptions; all per-check outcomes match original runtime scoring | `harbor-oracle-runtime-full.json` |
| Frozen runtime rebuild | All 331 installed package versions match lock; pip check and DB check pass | `runtime-locked-build.log`, `runtime-locked-probe.txt` |
| Full runtime tools and dependency graph | Airflow 3.0.3; dbt-core 1.12.7; pip check and DB check pass | `runtime-probe.txt` |
| Upstream Modal prove | Not run | Requires Modal environment |
| Agent parity | Not run; user deferred pending team configuration | No fabricated result file |

The partial-reversion probe restores original requirements, or original DAGs if
there is no requirements file. It is not guaranteed to invalidate each solution:
`23f2a0` and `2c5f8a` remain passing. No checks were removed to change this outcome.

The first 62-task Docker run used the scoring-smoke image/bootstrap. The
five-task follow-up used the final pinned base-image digest and upstream-style Git
bootstrap. The verifier code and original checks are the same in both runs.
The complete generated task snapshots are retained under the repository's ignored
`datasets/de-bench-upgrade-scoring-smoke/` and `datasets/de-bench-upgrade-final-smoke/`.
Raw Harbor configs, logs, patches, rewards and trial results are retained under
`jobs/de-bench-upgrade/{oracle-full,oracle-final-smoke}/` (also ignored).

The final full-runtime run uses the pinned image digest, final Git bootstrap and
331-package lock. All 62 tasks pass, with zero exceptions, in 4 minutes 26 seconds.
Every oracle per-check outcome matches the original scoring body executed in the
full runtime. The final dataset is `datasets/de-bench-upgrade/`; raw Harbor results
are `jobs/de-bench-upgrade/oracle-runtime-full/`. These local artifacts are ignored
by Git; the compact result summary is retained here.

## Reproduction

From the adapter directory:

```bash
uv sync --locked
uv run de-bench-upgrade --upstream-root /tmp/de-bench-upstream \
  --output-dir /tmp/de-bench-full --environment-profile scoring-smoke
uv run python scripts/validate_real.py --upstream-root /tmp/de-bench-upstream \
  --dataset /tmp/de-bench-full --output /tmp/scoring-full.json
DE_BENCH_ROOT=/tmp/de-bench-upstream uv run python -m unittest discover -s tests -v
uv build
# Build a scoring-smoke task image first, then run the original score-trial body:
uv run python scripts/validate_upstream_container.py \
  --upstream-root /tmp/de-bench-upstream --image de-bench-upgrade-scoring:5dcfc2b \
  --output /tmp/original-docker.json
harbor run -p /tmp/de-bench-full -a oracle -n 4
```

The scorer comparison runs with the actual upstream source; it does not replace
checks with synthetic predicates. The original reference patch helper is loaded
unchanged via AST to avoid importing unrelated agent telemetry/Modal libraries.
The generated verifier is run in a separate Python process. The regression suite
also exercises `.deleted` overlays (none occur in this revision), overwrite/ID
rejection, protected paths, ignored runtime outputs, committed changes, and stash
recovery without changing the agent's repository.

## Outstanding parity preparation

1. Compare resolved runtime packages/tool versions with the original Modal image.
2. Align world-system-prompt placement, agent installation and launch configuration
   on both sides; current Harbor instructions contain both original prompt texts.
3. Obtain agreed agent, dated model ID, run count, task set, budget and credentials.
4. Run upstream Modal prove and paired agent sanity checks; then full paired runs.
5. Record raw scores, mean/sample SEM and matching criterion, and complete
   `parity_experiment.json`, result upload and dataset registration.

The missing parity file is an intentional remaining acceptance gate, not a passed
CI check. The user explicitly requested implementation/validation first while the
experiment configuration remains undecided.

## Agent configuration findings from source inspection

These are preparation findings, not measured parity results:

- Upstream Codex `build_argv` prepends `system_prompt + "\n\n---\n\n" + prompt`.
  Its reasoning levels clamp to low/medium/high. The current generic Harbor
  instruction renderer does not yet reproduce that exact separator/role handling.
- Upstream Codex `resolve_model` only preserves IDs beginning `gpt-5.6-`; other
  inputs are mapped by Claude tier, or fall back to its default. An arbitrary
  agreed model ID must not be passed through this resolver unchanged under the
  assumption that it will run that model. Inspect the actual resolved ID and
  adapt the upstream runner explicitly if the team selects a different model.
- Upstream Codex uses an Anthropic-named gateway credential to configure an OpenAI
  Responses provider, and persists PATH for login shells. Harbor's standard
  provider setup must be aligned rather than assuming identical API routing.
- Upstream Claude Code appends the world text with `--append-system-prompt`, keeps
  the ticket as the user prompt, sets `--effort`, disables updater/telemetry and
  seeds onboarding state. Harbor 0.27.0 exposes `append_system_prompt` but its
  default install method differs (upstream npm versus Harbor native installer).

Source: upstream `src/de_bench/agents/{codex,claude_code}.py` and the locally
installed Harbor 0.27.0 agent implementations. These differences are why no
agent-equivalence claim is attached to the oracle/scoring results.

## Runtime reproduction finding

The first full-runtime build used the upstream dependency declarations and pip
installation order. Airflow 3.0.3 and its constrained providers installed, but the
unconstrained auxiliary group failed after 509.5 seconds with
`pip._vendor.resolvelib.resolvers.ResolutionTooDeep: 200000`.
`runtime-pip-build.log` contains the failure; it was not a cancelled experiment.
The first follow-up used uv 0.13.9 for the same second package group.
The final recipe additionally locks a consistent dependency graph, as described
below. These are explicit environment adaptations whose resolved package set
still needs comparison with Modal before agent parity. No scoring checks were weakened to work around this build issue.

The first uv build completed and its five Harbor oracle tasks passed, but a
separate `pip check` found two conflicts: Snowpark 1.33.0 requires protobuf <6,
and Prometheus exporter 0.48b0 requires OpenTelemetry SDK ~=1.27.0. See
`runtime-initial-probe.log` and `runtime-initial-uv-build.log`. Oracle success
alone therefore did not validate the full agent environment. A subsequent attempt retaining those consumer versions was rejected because
resolving extras alone downgraded the Airflow metapackage; see
`runtime-consumer-pins-build.log`. The final resolution includes all original
runtime roots, fixes Airflow at 3.0.3, keeps dbt-core on 1.x, and includes the
existing Snowpark/Prometheus consumers with compatible versions. It passes both
dependency consistency and DB initialization gates.

The final runtime records 331 packages in the shipped `runtime/requirements.lock`.
Relevant resolved versions include Airflow 3.0.3, dbt-core 1.12.7, Snowpark 1.58.0,
Prometheus exporter 0.66b2 and protobuf 6.33.6. The managed secondary interpreter
is pinned to Python 3.11.18. OpenTelemetry uses beta-versioned companion packages
as part of its normal dependency graph; a blanket prerelease ban is unsuitable.
The final recipe installs the frozen package list, rather than re-resolving
floating auxiliary packages on every build. This adaptation must be applied
symmetrically to upstream before agent parity is meaningful.

## Copilot grading-integrity fixes (PR #135)

The review identified command execution through submitted Git configuration and
reference-answer exposure through escaping symlinks. Both issues were reproduced
before the fix: a malicious fsmonitor created an execution marker, and escaping
links were accepted, including links restored from a stash.

The verifier now initializes a fresh recovery repository in a separate scratch
directory and imports only regular SHA-1 object/pack files and parsed commit IDs.
It does not copy submitted config, hooks, index, info attributes, alternates or
replacement refs. Every Git invocation uses a fixed executable/search path, an
allowlisted environment, disabled system/global configuration, empty templates,
and disabled hooks/fsmonitor/automatic maintenance. External merge/filter drivers
cannot be configured by the submission. The original agent repository is not
modified.

The workspace root itself cannot be a symlink. File and directory symlinks,
including chains, are checked before capture, after
each stash application and after final patch replay. Escaping/cyclic links fail
verification without a reward file; internal relative links remain supported.
This is process-level input hardening, not a claim of separate-container verifier
isolation; that migration remains a distinct follow-up.

Security regression results:

- Host regression suite: 17 passed (`security-regression-tests.txt`).
- The same suite in the locked full-runtime Docker image, with network disabled:
  17 passed (`security-docker-tests.txt`).
- Full 62-task, four-state scoring comparison: 248/248 per-check maps and final
  results match upstream (`security-scoring-full.json`).
- Tests cover local and inherited Git command injection, packed stash objects and
  refs, symlinked object storage, root/file/directory/chained/stashed escaping links,
  stale reward removal, and successful internal relative links.
- Full-runtime Harbor oracle after the fixes: **62/62 reward 1, zero exceptions**,
  with all oracle per-check outcomes matching the original runtime scorer
  (`harbor-oracle-security-fixes.json`).
