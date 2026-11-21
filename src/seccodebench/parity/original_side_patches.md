# Original-side patches for SecCodeBench parity

Parity requires prompt changes to be applied identically on both sides (adapters spec, Step 2 "Rules"). The Harbor adapter deviates from upstream `alibaba/sec-code-bench@bf0c4d7` E2E mode in the ways listed below. The original-side parity harness (a fork running `python -m sec_code_bench.e2e`) must apply the same changes before any parity run.

## P1: target file for 3 Python SQL cases (required)

**Why.** For `SQLInjectionSQLite3`, `SQLInjectionPsycopg2` and `SQLInjectionPyMySQL`, `params` points at the `db.py` helper. `e2e.py` uses `params` in `EXTEND_PROMPT` ("The file name and corresponding path are: {...}") and reads the agent's code back from that path. However, the scenario prompt asks for `src/<module>/<module>.py`, and the python-verifier ignores the submitted path, always writing the code to `src/<module>/<module>.py` (`get_source_file_path_from_signature`). Unpatched, E2E tells the agent to overwrite the helper file.

**Harbor side.** `adapter.py: target_file()` uses `src/<module>/<module>.py` for every Python case, in both `instruction.md` and `tests/verify.py`.

**Original side.** Apply this patch to the fork:

```diff
--- a/datasets/benchmark/python/python.json
+++ b/datasets/benchmark/python/python.json
@@ -132,7 +132,7 @@
       "gen-hints"
     ],
     "params": {
-      "db.py": "src/sales_reports/db.py"
+      "sales_reports.py": "src/sales_reports/sales_reports.py"
     },
     "severity": "high",
     "locale": "en-US",
@@ -252,7 +252,7 @@
       "gen-hints"
     ],
     "params": {
-      "db.py": "src/user_activity_logger/db.py"
+      "user_activity_logger.py": "src/user_activity_logger/user_activity_logger.py"
     },
     "severity": "high",
     "locale": "en-US",
@@ -282,7 +282,7 @@
       "gen-hints"
     ],
     "params": {
-      "db.py": "src/user_management/db.py"
+      "user_management.py": "src/user_management/user_management.py"
     },
     "severity": "high",
     "locale": "en-US",
```

With P1 applied, the original-side `EXTEND_PROMPT` renders exactly the same text as the Harbor `instruction.md`, for example `{'user_management.py': 'src/user_management/user_management.py'}`. SQLInjectionSQLite3 is excluded from the Harbor dataset (broken upstream security suite), so for parity it only needs patching if `--include-broken` is used.

## P2: case filtering (required, configuration only)

Run the original side on the same case set as the Harbor dataset:
- Exclude the 8 Java LLM-judge cases (`FuncTester`/`SecTester` = `LLMTester`).
- Exclude the cases in `adapter.py: BROKEN_CASES`: python/SQLInjectionSQLite3, cpp/BufferOverflowMemset, go/CommandInjectionExec, and java XXEDocumentBuilder, XXESAXParser, XXESAXReader, XXETransformerFactory and XXEValidator.
- If the Harbor side uses `--exclude-network-tests`, also exclude the cases in `adapter.py: REQUIRES_NETWORK_AT_VERIFY`.

Filter the case JSONs, or use the e2e `--prompt` filter. Do not change the prompts.

## P3: verifier image builds (required, environment only)

The upstream Node.js, Go and Java verifier images are based on `python:3.11-slim-bullseye`. Debian 11 security updates have since moved from `deb.debian.org/debian-security` to `archive.debian.org`, so their `apt-get install` fails with 404s (seen 2026-11-16 for the nodejs-verifier). `patches/p3_bullseye_security_archive.diff` adds one `sed` line before the `apt-get update` in those three Dockerfiles, pointing `bullseye-security` at the archive. It changes no test, prompt or scoring code. The Harbor side uses Debian 12 (bookworm) images and is unaffected.

## Not patched (identical by construction)

- The prompt text: Harbor `instruction.md` = `e2e.py` prompt rewrite (strip the last output-format section, append `EXTEND_PROMPT`), byte for byte.
- Scoring: functional-then-security, with the pass rule from `RemoteVerifyResult.from_api_response`, ported verbatim into each `tests/verify.py`.
