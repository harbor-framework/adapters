# Migration validation — 2026-10-28

This report covers the standalone BrowseComp-Plus migration, not a new model experiment.
Destination contract v1 was inspected at adapters commit
`7b4df9deb2381ae32f26e6cebec06aaa2975dc56`; source adapter files match
harbor PR #1511 head `eedc646d0637ebbefe459a5bd965fa242faecac6`.

## Local environment and checks

macOS arm64, Python 3.12.12, uv 0.9.26; optional external Harbor 0.8.0 from
PyPI, pytest 9.2.0, Ruff 0.17.3, ty 0.0.93. Dependencies are in `uv.lock`.
No Harbor source checkout is needed by the installed adapter.

| Check | Result |
| --- | --- |
| `uv run --extra agent --group dev pytest tests -q` | 27 passed, plus 6 helper subtests; synthetic data and mocked backends only |
| `python3 -m unittest discover -s scripts/tests -v` from repository root | 12 passed |
| Structural validator on a clean source snapshot | 31 passed, zero errors, zero warnings |
| `uv run --extra agent --group dev ruff check --fix .` | Passed under project-local scope |
| `uv run --extra agent --group dev ruff format .` | Passed, 10 files unchanged on final run |
| `uv run --extra agent --group dev ty check` | Passed under the explicitly configured migrated CLI/agent/test scope |
| `uv lock --check` | Passed, 111 resolved packages |
| `bash -n scripts_build_index/download_indexes.sh` | Passed |
| External Harbor JobConfig / TaskConfig parsing | Both job configs accepted, concurrency 2, task name accepted |
| Empty-credential oracle configuration | Resolves without API key or base URL; parity config still requires a key |
| Independent statistics recomputation | Historical raw arrays agree with mean/sample SEM strings |

The local lint/type scope excludes upstream/runtime code with optional backend
dependencies; it is not a claim that every inherited reference file passes a
new repository-wide type policy. Modified runtime/helper files additionally
passed scoped Ruff E4/E7/E9/F checks. The tests retain inherited SyntaxWarnings
for `\%` escapes inside original judge strings; those strings were preserved.
`git diff --check` likewise reports inherited trailing whitespace in preserved
judge strings and the oracle shell source, which was not rewritten for migration.

The validator recursively scans installed `.venv` contents, so validating an
adapter after installing Harbor in-place finds unrelated strings in Harbor's
site-packages. The reported structural result uses only the staged source
snapshot; the added CI validates before dependency installation for the same reason.

## Installed-wheel checks

Built the final wheel and installed it into a separate virtualenv outside both
repositories. From `/tmp`, verified:

- The canonical `browsecomp-plus --help` CLI and underscore compatibility alias.
- `browsecomp_plus.deep_research_agent:DeepResearchAgent` imports from installed
  site-packages with external Harbor 0.8.0 and reports version 1.0.11.
- The packaged Jinja installer renders; its embedded Python runner compiles.
- Package code and template assets match the final source tree; caches are excluded.
- A synthetic encrypted record generates a complete task via the installed package.
- Generation-only `--skip-download` does not attempt a corpus or historical-run download.

The installer is byte-identical to the source, SHA-256
`ecfcc6e5837c1cfd1489bb372b4089e7ef003b80ee6a4578ca0472eac5f6db92`.
The template instruction, both verifier Python files, oracle/test shell scripts,
and original agent prompts are also byte-identical. Grader template ASTs in
modified evaluation helpers remain equal to the source. Generated task names
now use one namespace slash: `texttron/browsecomp-plus-<id>`.

## Runtime and evidence limits

A Docker daemon was unavailable. No Docker image, real BM25 retrieval, live model
call, cloud job, full oracle rerun, new parity run/upload, registry publication,
or dataset upload was performed. BM25 downloads are tested with stubs; dense
FAISS/ReasonIR model construction is tested with fake backends, not downloaded models.

Historical model comparisons, missing original outputs, full oracle results,
excluded reward-hacking runs, and related BrowseComp scope are recorded in
[REVIEW_CONTEXT.md](REVIEW_CONTEXT.md). Historical evidence is carried forward
with its original links and does not establish current runtime or parity acceptance.
