#!/usr/bin/env bash
# Original-side parity run: upstream `vita run` (pinned vitabench commit) inside a container.
#
# Uses the vita-runtime sidecar image built from a generated task (it contains the full,
# unmodified vitabench checkout), and the same models.yaml generator as the Harbor side
# (vita_models_config.py), so both sides call the same endpoint with the same settings.
#
# Usage:
#   OPENAI_API_KEY=... OPENAI_BASE_URL=... \
#   AGENT_MODEL=gpt-4.1 USER_MODEL=gpt-4.1 EVALUATOR_MODEL=<judge> \
#   [LLM_ARGS_JSON='{"temperature": 0.0}'] [NUM_TRIALS=3] [MAX_CONCURRENCY=4] \
#   src/vita-bench/parity/run_original.sh <generated-task-dir> <task_set> <out_dir> [task_id ...]
#
#   task_set: delivery | instore | ota | cross_domain. Omit task ids to run the whole set.
#   Results: <out_dir>/<save_to>.json (upstream simulation file).
set -euo pipefail

TASK_DIR="${1:?generated task dir (any task; used only to build the runtime image)}"
TASK_SET="${2:?task set: delivery|instore|ota|cross_domain}"
OUT_DIR="${3:?output dir}"
shift 3
TASK_IDS=("$@")

: "${OPENAI_API_KEY:?}" "${AGENT_MODEL:?}" "${USER_MODEL:?}" "${EVALUATOR_MODEL:?}"
OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
NUM_TRIALS="${NUM_TRIALS:-3}"
MAX_CONCURRENCY="${MAX_CONCURRENCY:-4}"
SEED="${SEED:-300}"                 # upstream DEFAULT_SEED
LLM_ARGS_JSON="${LLM_ARGS_JSON:-}"  # optional per-model overrides, applied to all three roles
IMAGE="${IMAGE:-vita-runtime-original}"

case "$TASK_SET" in
  cross_domain) DOMAIN="delivery,instore,ota" ;;
  delivery|instore|ota) DOMAIN="$TASK_SET" ;;
  *) echo "unknown task set: $TASK_SET" >&2; exit 2 ;;
esac

mkdir -p "$OUT_DIR"
SAVE_TO="${SAVE_TO:-${TASK_SET}_$(echo "$AGENT_MODEL" | tr '/:' '__')_t${NUM_TRIALS}}"
docker build -q -t "$IMAGE" "$TASK_DIR/environment/runtime-server" >/dev/null

ID_ARGS=()
[ "${#TASK_IDS[@]}" -gt 0 ] && ID_ARGS=(--task-ids "${TASK_IDS[@]}")
# LLM_ARGS_JSON goes into models.yaml (merged into each model entry), exactly as on the Harbor
# side. Upstream's --*-llm-args flags are declared with type=dict and cannot parse a JSON string.

# The key is passed by name (-e VAR), so it never appears on the docker command line.
docker run --rm --network bridge \
  -e OPENAI_API_KEY -e OPENAI_BASE_URL="$OPENAI_BASE_URL" \
  -e AGENT_MODEL="$AGENT_MODEL" -e USER_MODEL="$USER_MODEL" -e EVALUATOR_MODEL="$EVALUATOR_MODEL" \
  -e LLM_ARGS_JSON="$LLM_ARGS_JSON" \
  -v "$(cd "$OUT_DIR" && pwd)":/out:Z \
  --entrypoint bash "$IMAGE" -c '
    set -euo pipefail
    cd /opt/vitabench
    python3 -c "
import os, sys
sys.path.insert(0, \"/app\")
from vita_models_config import write_models_config
o = os.environ.get(\"LLM_ARGS_JSON\") or None
write_models_config({os.environ[\"AGENT_MODEL\"]: o, os.environ[\"USER_MODEL\"]: o, os.environ[\"EVALUATOR_MODEL\"]: o})
"
    vita run --domain "'"$DOMAIN"'" --task-set-name "'"$TASK_SET"'" '"${ID_ARGS[*]:+$(printf '%q ' "${ID_ARGS[@]}")}"' \
      --agent-llm "$AGENT_MODEL" --user-llm "$USER_MODEL" --evaluator-llm "$EVALUATOR_MODEL" \
      --num-trials '"$NUM_TRIALS"' --seed '"$SEED"' --max-steps 300 --max-errors 10 \
      --language english --max-concurrency '"$MAX_CONCURRENCY"' --save-to "'"$SAVE_TO"'"
    # Upstream stores the full llm args, including the Authorization header (API key), in its
    # results. Redact before anything leaves the container.
    find data/simulations -maxdepth 1 -name "'"$SAVE_TO"'*" -type f -exec sed -i -E "s/\"Bearer [^\"]*\"/\"Bearer <redacted>\"/g" {} +
    if grep -rqE "Bearer [A-Za-z0-9_-]{20,}" data/simulations/"'"$SAVE_TO"'"*; then echo "refusing to copy: unredacted key" >&2; exit 3; fi
    umask 077
    cp -r data/simulations/"'"$SAVE_TO"'"* /out/
  '
chmod -R go-rwx "$OUT_DIR"
echo "Wrote $OUT_DIR/$SAVE_TO (upstream simulation batch; API keys redacted)"
