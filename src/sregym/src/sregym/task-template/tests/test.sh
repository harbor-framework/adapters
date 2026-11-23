#!/bin/bash
# Verifier for SREGym problem {problem_id}.
#
# SREGym evaluates each stage when the agent submits it (diagnosis: LLM judge
# against the ground-truth root cause; mitigation: the problem's programmatic
# mitigation oracle). This script tells the sidecar that the agent is done
# (so unsubmitted stages are recorded as failed, as in upstream), waits for
# the conductor's final result row, and maps it to Harbor rewards.
set -uo pipefail
# Never run from (or import out of) an agent-writable working directory.
cd /

BRIDGE="http://host.docker.internal:8100"
mkdir -p /logs/verifier
# Never trust a reward file that existed before verification.
rm -f /logs/verifier/reward.json /logs/verifier/reward.txt

# Stop anything the agent left running before reading results.
pkill -KILL -u agent 2>/dev/null || true

curl -fsS -X POST "$BRIDGE/harbor/finish" >/dev/null || true

# Fetch into a fresh root-only directory, never a path the agent could have
# pre-created, and only score a result fetched from the sidecar in this run.
work="$(mktemp -d)"
chmod 700 "$work"
result="$work/sregym-result.json"
fetched=0
for _ in $(seq 1 {verifier_poll_iterations}); do
    rm -f "$result"
    if curl -fsS "$BRIDGE/harbor/result" -o "$result" 2>/dev/null; then
        fetched=1
        python3 -I -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["phase"] in ("done", "scored") else 1)' "$result" && break
    fi
    sleep 5
done

if [ "$fetched" != 1 ]; then
    echo "could not reach the SREGym sidecar" >&2
    exit 2
fi
cp "$result" /logs/verifier/sregym_result.json
python3 -I /tests/score.py "$result" /logs/verifier
