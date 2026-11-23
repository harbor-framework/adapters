#!/bin/bash
# Verifier: asks the game sidecar for the settled result and writes the reward.
# reward = clip(S_final / reference, 0, 1); the raw S_final is reported next to
# it as a second metric. It also saves the run's action log.
set -Eeuo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
import json
import os
import sys
import urllib.request
from pathlib import Path

REWARD = Path("/logs/verifier/reward.txt")
METRICS = Path("/logs/verifier/reward.json")
RESULT = Path("/logs/verifier/result.json")
ACTIONS = Path("/logs/verifier/actions.jsonl")
server = os.environ.get("FM_SERVER", "http://game:8080")
token = os.environ.get("RESULT_TOKEN", "")

try:
    with urllib.request.urlopen(f"{server}/result?token={token}", timeout=300) as r:
        data = json.loads(r.read())
    reward = float(data["reward"])
    s_final = float(data["s_final"])
except Exception as e:
    # an unreachable server or a malformed result is an infrastructure failure,
    # not a low score: write no reward and fail, so the trial shows as an error
    print(f"could not read the result from the game server: {e}", file=sys.stderr)
    sys.exit(1)

REWARD.write_text(f"{reward:.4f}")
# Harbor reads reward.json when it is there, so it carries two metrics: `reward`
# is the number in reward.txt, `s_final` is the original, uncapped FM-Bench score
METRICS.write_text(json.dumps({"reward": round(reward, 4), "s_final": s_final}))
RESULT.write_text(json.dumps(data, indent=1, sort_keys=True))
print(f"reward={reward:.4f}  S_final={data['s_final']}  reference={data['reference']}  "
      f"settle={data['settle_reason']}")

# The audit trail: the seed and this log replay to the same final state in the
# FM-Bench engine. The reward is already written; a failure here only warns.
try:
    with urllib.request.urlopen(f"{server}/actions?token={token}", timeout=300) as r:
        actions = json.loads(r.read())
    ACTIONS.write_text("".join(json.dumps(a, sort_keys=True) + "\n" for a in actions))
    print(f"saved {len(actions)} actions to {ACTIONS}")
except Exception as e:
    print(f"warning: could not save the action log: {e}", file=sys.stderr)
PY
