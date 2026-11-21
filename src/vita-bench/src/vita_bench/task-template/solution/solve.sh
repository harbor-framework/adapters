#!/bin/bash
# Oracle solution: replay a pre-validated reference conversation.
#
# VitaBench ships no reference solutions (grading is a rubric-based LLM judge over
# the whole conversation), so the adapter stores one validated trajectory per task
# (see src/vita-bench/oracle/ and scripts/build_oracle.py). The trajectory is
# loaded into the vita-runtime sidecar (POST /state, authenticated with the
# per-task token in /solution/oracle_token) so the verifier scores it with the
# official evaluator exactly like a live agent run.
set -euo pipefail

ORACLE="/solution/oracle_trajectory.json"
TOKEN_FILE="/solution/oracle_token"
RUNTIME_URL="${VITA_RUNTIME_URL:-http://vita-runtime:8000}"

if [ ! -f "${ORACLE}" ]; then
  echo "No oracle trajectory available for this task (${ORACLE} missing)." >&2
  exit 1
fi

python3 - "${ORACLE}" "${TOKEN_FILE}" "${RUNTIME_URL}" <<'PYEOF'
import json
import sys
import time
import urllib.request

oracle_path, token_path, runtime_url = sys.argv[1:4]
with open(token_path, encoding="utf-8") as fp:
    token = fp.read().strip()
with open(oracle_path, encoding="utf-8") as fp:
    oracle = json.load(fp)

missing = {"messages", "termination_reason"} - set(oracle)
if missing:
    raise SystemExit(f"Oracle trajectory is missing fields: {sorted(missing)}")
if oracle["termination_reason"] not in {"agent_stop", "user_stop"}:
    raise SystemExit(
        f"Oracle trajectory has non-success termination: {oracle['termination_reason']}"
    )
oracle.setdefault("states", {"old_states": [], "new_states": []})
oracle["start_tool_called"] = True
oracle["oracle_replay"] = True

# Wait for the sidecar (healthchecks are not honoured by every runtime).
deadline = time.time() + 300
while True:
    try:
        urllib.request.urlopen(f"{runtime_url}/health", timeout=5).read()
        break
    except OSError:
        if time.time() > deadline:
            raise SystemExit(f"vita-runtime not reachable at {runtime_url} after 300s")
        time.sleep(2)

body = json.dumps(oracle).encode("utf-8")
request = urllib.request.Request(
    f"{runtime_url}/state", data=body, method="POST",
    headers={"Content-Type": "application/json", "X-Vita-Oracle-Token": token},
)
with urllib.request.urlopen(request, timeout=60) as response:
    print("runtime:", response.read().decode("utf-8"))
print(f"Replayed oracle trajectory with {len(oracle['messages'])} messages.")
PYEOF
