#!/bin/bash
# Oracle: replays the recorded action log of the reference policy through the
# same tool endpoint an agent uses. The engine is deterministic, so the replay
# reaches the reference score exactly.
set -euo pipefail

python3 - <<'PY'
import gzip
import json
import os
import urllib.request

SERVER = os.environ.get("FM_SERVER", "http://game:8080")
LOG = os.environ.get("FM_ORACLE_LOG", "/solution/actions.jsonl.gz")


def post(name, args):
    req = urllib.request.Request(
        SERVER + "/tool", data=json.dumps({"name": name, "args": args}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


n = 0
last = {}
with gzip.open(LOG, "rt", encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        last = post(rec["tool"], rec["args"])
        if not last.get("ok"):
            raise SystemExit(f"replay diverged at record {n}: {rec} -> {last}")
        n += 1
over = bool((last.get("data") or {}).get("game_over"))
print(f"replayed {n} actions; game_over={over}")
if not over:
    raise SystemExit("replay ended before the game was over")
PY
