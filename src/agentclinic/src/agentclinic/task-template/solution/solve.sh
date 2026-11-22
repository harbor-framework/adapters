#!/bin/bash
set -euo pipefail

python3 - <<'PY'
import json
import time
import urllib.request

BASE = "http://clinic:8000"
DIAGNOSIS = {diagnosis_json}

for _ in range(120):
    try:
        urllib.request.urlopen(BASE + "/health", timeout=2)
        break
    except OSError:
        time.sleep(0.5)

request = urllib.request.Request(
    BASE + "/api/submit_diagnosis",
    data=json.dumps({"text": DIAGNOSIS}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=60) as response:
    body = json.load(response)
print(body["reply"])
if body.get("status") != "submitted":
    raise SystemExit(f"the clinic did not accept the diagnosis: {body}")
PY
