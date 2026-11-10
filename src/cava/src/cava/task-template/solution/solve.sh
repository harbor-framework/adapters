#!/bin/bash
# Oracle: ground-truth answer (and function calls) for this CAVA record.
set -e
python3 - <<'PY'
import base64, json, subprocess
oracle = json.loads(base64.b64decode("{{ORACLE_B64}}"))
for call in oracle.get("function_calls", []):
    subprocess.run(["call_function", call["name"], json.dumps(call["arguments"])], check=True)
with open("/app/answer.txt", "w") as f:
    f.write(oracle.get("answer", ""))
PY
