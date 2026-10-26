# GDPval standalone migration

This file records the initial migration stage. The subsequent three-task Docker
review, fixes, and remaining acceptance blockers are in [REVIEW.md](REVIEW.md).

This is a code migration and local generation check. It is not benchmark acceptance,
Docker runtime proof, or a parity result.

## Revisions and scope

- Target repository base: `cfe10f29e1cd8dfeac70381f6547c006dcf8437b`.
- Local branch: `feat/gdpval-adapter`.
- Source PR: <https://github.com/harbor-framework/harbor/pull/1384>.
- Source head: `d935522f2837ba4a05f862741aa014f9cd78b151`, checked on 2026-10-23.
- Public dataset revision observed in the HF cache: `11e7900cdcac61bc4daf59e65feb238acda98fbf`.
- All 19 source files under `adapters/gdpval/` were copied to `src/gdpval/`.
- No other adapter, root summary, shared validator, or Harbor framework file was changed.
- No commit, push, merge, model call, parity run, or dataset publication was performed.

## Local changes

1. README commands now use `src/gdpval/` and the external `harbor` CLI. Registry
   commands remain future examples, not publication evidence. Source oracle and
   historical model results are explicitly attributed to the source PR.
2. The task template uses `version = "1.0"`, as required by the local contract.
   Harbor 0.23.0 accepts this alias for `schema_version`. Names remain
   `openai/gdpval__<source-task-id>`; Harbor accepts this format.
3. Added offline migration tests and a generated-task validation utility under
   `tests/`. They do not change generated instructions or grading.

The generator, dataset loader, CLI, Docker files, network policy, solve script,
verifier, metadata, historical parity records, dependency declarations, and lockfile
are byte-identical to the source PR. `main.py` already resolves the correct repository
root after relocation because the package depth is unchanged. The reference YAML
already uses a repository-root dataset path, so no YAML change was required.

## Reproduction

From the repository root:

```bash
cd src/gdpval
uv sync --locked
uv run gdpval --help
uv run gdpval --output-dir ../../datasets/gdpval-smoke --limit 3 --overwrite
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
uvx ruff check --isolated --select E4,E7,E9,F src tests
uvx ruff check tests
uv run --with harbor==0.23.0 python tests/check_generated.py \
  ../../datasets/gdpval-smoke --report ../../tmp/gdpval-smoke-validation.json
uv build --out-dir ../../tmp/gdpval-dist
cd ../..
python3 scripts/validate_adapter.py gdpval
```

For full task generation only (no agent or model execution):

```bash
cd src/gdpval
uv run gdpval --output-dir ../../datasets/gdpval
uv run --with harbor==0.23.0 python tests/check_generated.py \
  ../../datasets/gdpval --report ../../tmp/gdpval-generated-validation.json
```

The local full generation used the same `GdpvalAdapter.run()` implementation with
one source task ID per call and eight download workers. A temporary launcher under
`tmp/gdpval-generate.py` loaded the source rows once and reused them. It overwrote
only this session's generated output. The canonical CLI was separately checked on
three real source rows. The temporary launcher and generated files are ignored by
Git; they are not adapter implementation files.

The last pending row, `a941b6d8-4289-4500-b45a-f8e4fc94a724`, has no gold
paths but the upstream generator downloads its videos before checking that fact.
After all 185 gold-bearing rows completed, that reference download was stopped
and its session-created partial task directory was removed. The ledger records
this row separately as excluded for missing gold metadata. The other 219 calls
completed with 185 generated tasks, 34 skips, and no uncaught generation exceptions.

## Verification

- `uv sync --locked`: passed with the unchanged upstream dependency lockfile.
- Canonical CLI: four required flags present; default output path resolves to the
  repository's `datasets/gdpval`.
- Real-data smoke: 3 tasks, 8 reference files, 3 gold deliverables. Harbor 0.23.0
  loaded all task configs and `Task` objects. The oracle-default reference YAML
  also loaded through `JobConfig`.
- Offline tests: 3 passed. Coverage includes filtering, limit, skip/overwrite,
  stable regeneration, prompt/rubric preservation, multiple deliverables, source
  bytes, missing deliverable reward 0, exact gold reward 1 without a model call,
  and mocked pairwise model/tie/gold rewards of 1/0.5/0.
- Real-data host replay: all 3 smoke-task solve scripts copied their gold files and
  the corresponding verifier scripts returned exact-match reward 1.0 without a
  model call.
- The shell tests remap container paths into temporary host directories. They
  do not prove Docker mounts, networking, privileges, or agent isolation.
- Python compilation and basic Ruff correctness rules: passed. Added test files
  pass the repository's complete Ruff rules.
- Structural validator: 31 checks passed, 0 errors, 6 warnings. All six warnings
  concern the source PR's one-run historical records, which do not satisfy parity.
- Full repository Ruff rules on the imported source: 13 existing findings
  (broad exception catches, import formatting, class dictionary annotation, and
  a duplicate numeric set member). They were retained to avoid unrelated source
  refactoring; the generator and judge remain byte-identical to the source PR.
- Wheel and sdist build: passed. The wheel includes all 8 task template files.
- Full generated set: **185 tasks**, **220 declared reference files** (219 packaged,
  1 scheduled for Docker build-time download), and **248 gold deliverables** with
  byte-identical `tests/gold/` and `solution/gold/` copies. All 185 task configs and
  `Task` objects loaded in Harbor 0.23.0. Source prompt/rubric preservation,
  expected filenames, rendered placeholders, and shell syntax checks passed.
- The 35 non-generated IDs exactly match the 35 source rows with no gold paths.
  The local ID ledger is `../../tmp/gdpval-generated-validation.json`; the generation
  attempt ledger is `../../tmp/gdpval-generation.json`.
- `harbor run -c src/gdpval/run_gdpval.yaml --dry-run`: blocked because the Docker
  daemon is not running. This CLI preflight requires Docker even in dry-run mode.
  No Docker execution or model evaluation was performed. The YAML independently
  passed `JobConfig` loading.

## Next review

1. **Parity and acceptance:** the copied records use unmatched historical model
   references and one run per side. They predate the shipped pairwise verifier.
   They cannot establish ADP-PARITY or ADP-STATS. Decide the original-side evaluator,
   matched agents/models, and denominator before new paid experiments.
2. **Coverage and provenance:** 185/220 is an upstream claim, not an enforced ID
   allowlist. The generator silently skips rows with missing references or gold
   files and does not emit exclusion reasons. `--limit` selects source rows before
   these skips. Review an explicit exclusion ledger and pin dataset/external asset
   revisions before publication. The current source snapshot has exactly 35 rows without
   gold paths; their IDs match the local exclusion list. Also move the no-gold
   preflight before reference downloads to avoid fetching large unusable videos.
   Source metadata also carries historical registry
   counts and costs; these are not current local delivery claims. Metadata also
   retains upstream `harness: null` and empty agent arrays; review these against
   the local metadata contract before acceptance.
3. **Runtime:** run a small Docker oracle check next. Confirm Compose merging,
   `NET_ADMIN`/iptables, endpoint access, dependency installation, reference paths,
   and verifier isolation. The local installed default Harbor CLI was 0.16.1;
   these schema checks used an isolated Harbor 0.23.0 environment. They do not prove
   that every change in the guide's source baseline commit is in that release.
4. **Grading:** retain the source behavior for review. Gold byte copies bypass
   the pairwise judge. Judge/API failures in `test.sh` become reward 0, which mixes
   infrastructure errors with scored failures. Office XML extraction loses layout;
   audio/video uses file metadata. Review fidelity to expert grading and handling
   of untrusted deliverable content before interpreting model results.
5. **Reproducibility and hygiene:** Docker Python dependencies and the oversized
   reference download still float independently of the adapter lockfile. Resolve
   the 13 existing lint findings separately. Always pass an explicit `--output-dir`
   for installed-wheel use; the upstream default assumes a source checkout.
