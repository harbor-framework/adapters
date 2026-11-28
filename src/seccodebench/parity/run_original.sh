#!/usr/bin/env bash
# Original-side SecCodeBench parity run (upstream E2E mode + Codex CLI).
#
# usage: run_original.sh --model MODEL --cases LANG:CASE[:SCENARIO][,...] [--scenarios "gen fix"]
#                        [--run-name NAME] [--cli-version VERSION] [--work DIR]
#   e.g. run_original.sh --model deepseek-v4.1-flash --cases python:SSTIJinja2Template,cpp:BufferOverflowStrcpy
#
# Steps (all upstream code runs inside containers, never on the host):
#   1. clone alibaba/sec-code-bench at the pinned commit into $WORK and apply patches P1
#      (prompt/target fix) and P3 (verifier image build fix), see original_side_patches.md
#   2. P2: write filtered case lists (only the requested cases, only the requested scenarios)
#   3. bring up the upstream verifier services (docker-compose-verifiers.yml) for the needed languages
#   4. build the runner image (patched upstream + pinned Codex CLI) and run
#      `python -m sec_code_bench.e2e --editor codex --cli-model MODEL --experiment-cycle 1`
#      with --network host (e2e rewrites verifier URLs to localhost:<published port>)
# OPENAI_API_KEY and OPENAI_BASE_URL must be set in the environment; they are passed through by
# name only. Codex >= 0.17x ignores OPENAI_BASE_URL, so keep CLI_VERSION at a release that reads it.
set -euo pipefail

COMMIT=bf0c4d727098733af34c7add14a8d37ee84fd2a7
CLI_VERSION=0.118.0   # keep identical to parity/run_harbor_parity.yaml (agents[].kwargs.version)
SCENARIOS="gen fix"
RUN_NAME="orig-$(date +%Y%m%d-%H%M%S)"
WORK="${SCB_ORIG_WORK:-$PWD/.seccodebench-original}"
MODEL="" CASES=""
while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL=$2; shift 2 ;;
    --cases) CASES=$2; shift 2 ;;
    --scenarios) SCENARIOS=$2; shift 2 ;;
    --run-name) RUN_NAME=$2; shift 2 ;;
    --cli-version) CLI_VERSION=$2; shift 2 ;;
    --work) WORK=$2; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac
done
[ -n "$MODEL" ] && [ -n "$CASES" ] || { echo "--model and --cases are required" >&2; exit 2; }
for v in OPENAI_API_KEY OPENAI_BASE_URL; do [ -n "${!v:-}" ] || { echo "$v is not set" >&2; exit 2; }; done
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$WORK/sec-code-bench"
OUT="$WORK/runs/$RUN_NAME"
mkdir -p "$WORK/runs" "$OUT"

# 1. pinned upstream + P1
if [ ! -d "$REPO/.git" ]; then
  # SCB_UPSTREAM_SRC may point at an existing local clone (faster than GitHub for a 2 GB repo)
  git clone -q "${SCB_UPSTREAM_SRC:-https://github.com/alibaba/sec-code-bench.git}" "$REPO"
  git -C "$REPO" checkout -q "$COMMIT"
fi
# apply the patches whenever the checkout is clean (also recovers a clone interrupted before this step)
if git -C "$REPO" diff --quiet; then
  for p in p1_python_params p3_bullseye_security_archive p4_codex_exec_flags p5_cli_timeout_process_group p6_neutral_workspace_name; do
    git -C "$REPO" apply "$HERE/patches/$p.diff"
  done
fi
[ "$(git -C "$REPO" rev-parse HEAD)" = "$COMMIT" ] || { echo "upstream checkout is not at $COMMIT" >&2; exit 1; }

# 2. P2: filtered case lists (data only; no upstream code executed)
CASE_DIR="$WORK/cases/$RUN_NAME"
LANG_ARGS=$(python3 -I - "$REPO" "$CASE_DIR" "$CASES" "$SCENARIOS" <<'EOF'
import json, sys
from pathlib import Path
repo, out, cases, scenarios = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4].split()
files = {"python": "python/python.json", "nodejs": "nodejs/nodejs.json", "cpp": "cpp/c.json",
         "go": "go/go.json", "java": "java/java.json"}
want = {}
for item in cases.split(","):
    lang, cid, *only = item.split(":")  # optional LANG:CASE:SCENARIO restricts that case
    want.setdefault(lang, []).append((cid, only[0] if only else None))
out.mkdir(parents=True, exist_ok=True)
args = []
for lang, cids in want.items():
    data = json.loads((repo / "datasets/benchmark" / files[lang]).read_text())
    sel = {}
    for cid, only in cids:
        spec = dict(sel.get(cid) or data[cid])
        keep = [only] if only else scenarios
        prev = sel[cid]["scenarios"] if cid in sel else []
        spec["scenarios"] = [s for s in data[cid]["scenarios"] if s in keep or s in prev]
        sel[cid] = spec
    (out / f"{lang}.json").write_text(json.dumps(sel, indent=2, ensure_ascii=False))
    args.append(f"--lang-config {lang}:en-US:/cases/{lang}.json")
print(" ".join(args))
EOF
)
LANGS=$(echo "$LANG_ARGS" | grep -oE '[a-z]+:en-US' | cut -d: -f1 | sort -u)
# upstream e2e refuses any java run without an odd --judge-llm-list, even for UnitTester-only cases
# (the adapter excludes the LLMTester cases). Pass a placeholder that points nowhere: no judge is
# ever called, and a judge call would fail loudly instead of silently grading.
JUDGE_ARGS=""
echo "$LANGS" | grep -qx java && JUDGE_ARGS="--judge-llm-list OPENAI::unused::unused::http://127.0.0.1:9/v1"
chmod -R a+rX "$CASE_DIR"   # case data only (no secrets); the runner container's user must read it under umask 077

# 3. verifier services for the needed languages
declare -A SVC=([python]=python-verifier [nodejs]=nodejs-verifier [cpp]=c-verifier [go]=go-verifier [java]=java-verifier)
SERVICES=$(for l in $LANGS; do echo -n "${SVC[$l]} "; done)
COMPOSE=(-f docker-compose-verifiers.yml)
[ "${SCB_LOCAL_PODMAN:-0}" = 1 ] && COMPOSE+=(-f "$HERE/compose.local-podman.yml")
(cd "$REPO" && docker compose "${COMPOSE[@]}" up -d --build $SERVICES)
for l in $LANGS; do
  port=$(case $l in cpp) echo 24683;; python) echo 24684;; go) echo 24685;; nodejs) echo 24686;; java) echo 24687;; esac)
  ready=0
  for _ in $(seq 1 60); do
    if curl -sf -m 5 -o /dev/null "http://127.0.0.1:$port/" || curl -sf -m 5 -o /dev/null "http://127.0.0.1:$port/health"; then
      ready=1; break
    fi
    sleep 5
  done
  if [ "$ready" != 1 ]; then
    echo "ERROR: ${SVC[$l]} (localhost:$port) did not become ready within 5 minutes; aborting before the e2e run." >&2
    echo "       check: docker logs ${SVC[$l]}   (on NFS-backed rootless podman set SCB_LOCAL_PODMAN=1)" >&2
    exit 1
  fi
done

# 4. runner image + e2e run
CTX="$WORK/runner-ctx"; rm -rf "$CTX"; mkdir -p "$CTX"
mkdir -p "$CTX/sec-code-bench/datasets"   # runner needs only the package, prompts/case lists and configs
cp -r "$REPO/sec_code_bench" "$REPO/pyproject.toml" "$REPO/README.md" "$REPO/system_config.yaml" "$CTX/sec-code-bench/"
cp -r "$REPO/datasets/benchmark" "$CTX/sec-code-bench/datasets/"
docker build -q -t "seccodebench-orig-runner:$CLI_VERSION" --build-arg "CODEX_VERSION=$CLI_VERSION" \
  -f "$HERE/original-runner.Dockerfile" "$CTX" >/dev/null
chmod 777 "$OUT"
# shellcheck disable=SC2086
docker run --rm --network host -e OPENAI_API_KEY -e OPENAI_BASE_URL \
  -v "$CASE_DIR":/cases:ro -v "$OUT":/out \
  "seccodebench-orig-runner:$CLI_VERSION" \
  bash -c '
    # codex exec authenticates from $CODEX_HOME/auth.json, not OPENAI_API_KEY (same file Harbor writes);
    # session rollouts are kept under /out/codex-sessions so the agent trajectories can be audited
    mkdir -p ~/.codex /out/codex-sessions && ln -s /out/codex-sessions ~/.codex/sessions && umask 077 && python -c "import json,os; json.dump({\"OPENAI_API_KEY\": os.environ[\"OPENAI_API_KEY\"]}, open(os.path.expanduser(\"~/.codex/auth.json\"), \"w\"))"
    exec "$@"' _ \
  python -m sec_code_bench.e2e --editor codex --cli-model "$MODEL" \
    --cli-extra-arg=--enable --cli-extra-arg=unified_exec \
    --cli-extra-arg=-c --cli-extra-arg=model_reasoning_effort=high \
    --cli-extra-arg=-c --cli-extra-arg=web_search=disabled \
    --experiment-cycle 1 --threads 1 --log-dir /out $LANG_ARGS $JUDGE_ARGS
echo "results: $OUT"
