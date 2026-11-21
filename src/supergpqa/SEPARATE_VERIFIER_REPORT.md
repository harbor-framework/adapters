# Separate-verifier migration validation — 2026-11-21

## Scope

The task template now declares `/app/answer.txt` as an artifact and explicitly
uses `verifier.environment_mode = "separate"`. `tests/Dockerfile` bundles the
unchanged grader, pinned upstream parser, gold record and timeout-decorator
0.5.0. The grading dependency was removed from the agent image. Prompt bytes,
task names, answer paths, gold records and scoring code were kept unchanged.

Validation used Harbor **0.27.0**, Python 3.13.18 and Docker in the existing
Linux aarch64 Lima VM. This is a new environment-validation record; it does not
replace the original Harbor 0.25.0 model-parity or full-bank Oracle evidence.

## Same-task positive and negative controls

Task: `m-a-p/supergpqa-060d1632f1644d4990af62065b597fdd`.

| Submission | Execution | Reward | Verifier mode | Exception |
|---|---|---:|---|---|
| `Answer: D` (gold) | Harbor Oracle agent / reference solve.sh | 1 | separate | None |
| `Answer: A` (valid incorrect option) | Offline saved-submission agent | 0 | separate | None |

This is the representative check requested by the reviewer. The full 26,529-task
Oracle was **not** repeated on the migrated template.

## Saved-response regrading

All **300 saved Harbor-side model responses** (100 questions × 3 runs) were
regraded by Harbor's native regrade workflow with the updated separate verifier.
There were **300/300 unchanged rewards**, zero final trial exceptions, and
**zero new model calls**. Per-run accuracies remain **46%, 44%, 44%**.
The original side did not need to be rerun.

The source shared-verifier trials had retained API responses and grading logs,
but had not declared `/app/answer.txt` in their artifact manifests. The helper
therefore created explicitly labeled **derived source copies**. In each copy it
reconstructed the answer artifact byte-for-byte from `agent/response.txt`,
verified it against the raw API JSON, and recorded source paths, SHA-256 hashes,
and a reconstruction-provenance document before native regrading.
These entries are reconstructed inputs, not claims about original collection.
Every original trial's file contents were checked before and after its regrade
and again after all 300 regrades; the original records remained unchanged.

This 300-response scope is an additional validation choice, not a mandatory
sample count in Harbor's guide. The official regrade feature supports rerunning
verification without rerunning the agent.

## Reproduction

Install Harbor 0.27.0 and this adapter's dependencies, then from the adapters
repository root run:

```bash
PYTHONPATH=src/supergpqa/src python src/supergpqa/scripts/verify_separate.py \
  --experiment-dir /path/to/reconstructed-original-experiment \
  --output-dir /path/to/fresh-migration-evidence --concurrency 4
```

Use `--controls-only` for just the two controls. No API credential is needed.
The output includes `controls.json`, `regrade-audit.json`, derived sources,
new native trial results, and per-response provenance. The local validation
bundle additionally includes the runtime freeze, source snapshot and checksums.

Validation: 30 behavioral tests passed; Ruff lint and formatting passed; ty
passed. Structural validation: 29 passes, no errors, three existing warnings
(pending dataset PR, unavailable billed USD, and the reward-output text scan).

## References

- [Reviewer request](https://github.com/harbor-framework/adapters/pull/82#issuecomment-7036486682)
- [Harbor separate-verifier template change](https://github.com/harbor-framework/harbor/pull/3712)
- [Harbor 0.27.0 regrade documentation](https://github.com/harbor-framework/harbor/blob/v0.27.0/docs-mintlify/jobs/regrade.mdx)
