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

## P4: Codex `exec` flag order (required, CLI invocation)

Upstream `CodexEditor` emits `codex --skip-git-repo-check ... exec`. `--skip-git-repo-check` is an `exec` subcommand flag, so every Codex release rejects the command ("unexpected argument"). `patches/p4_codex_exec_flags.diff` emits `--dangerously-bypass-approvals-and-sandbox exec --skip-git-repo-check`, which is the same effective invocation as Harbor's codex agent.

## P5: the 300 s CLI timeout must kill the whole process tree (required)

`CliEditor` runs the CLI with `subprocess.Popen(...).communicate(timeout=300)` and calls `proc.kill()` on timeout. That kills only the `codex` launcher. Its native child keeps the stdout/stderr pipes open, so the following `communicate()` waits until the agent finishes by itself. Upstream therefore never enforces its 300 s limit: original-side agents ran for up to ~1060 s. Harbor stops the agent at 300 s (`[agent] timeout_sec`). `patches/p5_cli_timeout_process_group.diff` starts the CLI in its own session (`start_new_session=True`) and kills the process group (`os.killpg`) on timeout.

## P6: neutral agent working directory (required)

`e2e.py` makes the agent's cwd `<case_id>_<scenario>_cycle-<n>`, e.g. `XXEJDOM2_gen_cycle-0` or `BufferOverflowVLA_gen_cycle-0`. Codex sends the cwd to the model in its `<environment_context>`, so the original side names the vulnerability class the task is graded on. Harbor's agent works in `/app`. `patches/p6_neutral_workspace_name.diff` names the directory `task-<sha1(case_scenario_cycle)[:10]>`. With the case-named cwd, XXEJDOM2 gen passed 3/3 on the original side; with a neutral name it passed 1/3, against 0/3 on Harbor.

Effect of P5 and P6 together: the original side went from 62.5% (10/16 in each of 3 runs) to 50.0%, against 45.8 ± 2.1% on Harbor.

## Runner environment (not upstream code)

`run_original.sh` runs upstream inside `parity/original-runner.Dockerfile` so the agent never runs on the host. Settings kept identical to Harbor's codex agent:
- **CLI install.** Codex CLI 0.118.0 is installed with the same nvm v0.40.2 / Node 22 / `npm i -g @openai/codex@<version>` steps. Codex ≥ 0.17x ignores `OPENAI_BASE_URL`; 0.118.0 honors it.
- **Auth.** `codex exec` reads the key from `$CODEX_HOME/auth.json`, not from `OPENAI_API_KEY`. The runner writes the same `{"OPENAI_API_KEY": ...}` file that Harbor's agent writes.
- **Flags.** Both sides pass `-c model_reasoning_effort=high --enable unified_exec -c web_search=disabled`. Codex's built-in web search fails behind the parity gateway ("Access denied for web search"), which ended trials on both sides until it was disabled.
- **Toolchains.** The runner has the toolchains the Harbor task images give the agent: JDK 17 + Maven, gcc/cmake, Go 1.25.5, Node 22, jq and ping.
- **Java judge argument.** Upstream e2e refuses any Java run without an odd `--judge-llm-list`, even though the parity Java cases are `UnitTester`-only. The runner passes a placeholder judge pointing at `127.0.0.1:9`: it is never called, and a judge call would fail loudly.
- **Session records.** Codex session rollouts are saved to `<run>/codex-sessions/` for auditing.

## Not patched (identical by construction)

- The prompt text: Harbor `instruction.md` = `e2e.py` prompt rewrite (strip the last output-format section, append `EXTEND_PROMPT`), byte for byte.
- Scoring: functional-then-security, with the pass rule from `RemoteVerifyResult.from_api_response`, ported verbatim into each `tests/verify.py`.
