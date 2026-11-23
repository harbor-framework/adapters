#!/bin/bash
# Oracle for SREGym problem {problem_id}.
#
# 1. Diagnosis: submit the problem's ground-truth root cause to the conductor.
# 2. Mitigation: apply SREGym's own recovery (problem.recover_fault()), then
#    submit the empty mitigation solution so the conductor runs the oracle.
# The bridge's oracle endpoints require a per-task token that exists only in
# this file and in the sidecar's environment.
set -euo pipefail

BRIDGE="http://host.docker.internal:8100"
CONDUCTOR="http://${API_HOSTNAME:-host.docker.internal}:${API_PORT:-8000}"
TOKEN="{oracle_token}"

stage() { curl -fsS "$CONDUCTOR/status" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("stage"))'; }
wait_stage() {
    for _ in $(seq 1 600); do
        s="$(stage || true)"
        [ "$s" = "$1" ] && return 0
        [ "$s" = "done" ] && return 1
        sleep 2
    done
    return 1
}
submit() {
    python3 -c 'import json,sys; print(json.dumps({"solution": sys.argv[1]}))' "$1" \
        | curl -fsS -X POST -H 'Content-Type: application/json' --data @- "$CONDUCTOR/submit"
    echo
}

current="$(stage)"
echo "conductor stage: $current"

# Check the agent's interfaces as well: kubectl through SREGym's filtering
# Kubernetes API proxy, with the kubeconfig the sidecar handed to `main`.
kubectl get pods -A -o wide > /tmp/oracle-pods.txt
head -50 /tmp/oracle-pods.txt
# Evidence for the agent-phase allowlist: a non-allowlisted host should fail.
if curl -fsS -m 10 -o /dev/null https://example.com 2>/dev/null; then
    echo "egress check: example.com REACHABLE (allowlist not enforced)"
else
    echo "egress check: example.com blocked"
fi

if [ "$current" = "diagnosis" ]; then
    root_cause="$(curl -fsS -H "X-Harbor-Oracle-Token: $TOKEN" "$BRIDGE/harbor/oracle/root_cause" \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["root_cause"])')"
    echo "submitting diagnosis"
    if [ -z "$root_cause" ]; then
        echo "problem has no ground-truth root cause" >&2
        exit 1
    fi
    submit "$root_cause"
    if ! wait_stage mitigation; then
        echo "conductor did not open the mitigation stage" >&2
        exit 1
    fi
fi

echo "applying recover_fault()"
curl -fsS -X POST -H "X-Harbor-Oracle-Token: $TOKEN" "$BRIDGE/harbor/oracle/recover"
echo
recovery=""
for _ in $(seq 1 360); do
    recovery="$(curl -fsS -H "X-Harbor-Oracle-Token: $TOKEN" "$BRIDGE/harbor/oracle/recover" \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])' || true)"
    [ "$recovery" = "done" ] || [ "$recovery" = "failed" ] && break
    sleep 5
done
echo "recovery: $recovery"
if [ "$recovery" != "done" ]; then
    echo "recover_fault() did not complete" >&2
    exit 1
fi
# SREGym grades mitigation as soon as it is submitted, and several oracles
# check pod state or traffic at that moment. A careful agent confirms its fix
# before submitting, so the oracle does too: wait for the application's pods
# to settle (rollouts finished, containers ready), then hold for a short
# stabilization period. This changes only when the reference solution
# submits, not how it is graded.
APP_NAMESPACES="{app_namespaces}"
READY_TIMEOUT_SEC="${ORACLE_READY_TIMEOUT_SEC:-600}"
SETTLE_SEC="${ORACLE_SETTLE_SEC:-{oracle_settle_sec}}"
pods_settled() {
    local ns
    for ns in $APP_NAMESPACES; do
        kubectl get pods -n "$ns" -o json | python3 -c '
import json, sys
bad = []
for p in json.load(sys.stdin)["items"]:
    st = p.get("status", {})
    if st.get("phase") == "Succeeded":
        continue
    if p["metadata"].get("deletionTimestamp"):
        bad.append(p["metadata"]["name"] + ":terminating")
        continue
    if st.get("phase") != "Running":
        bad.append(p["metadata"]["name"] + ":" + str(st.get("phase")))
        continue
    for c in st.get("containerStatuses") or []:
        if not c.get("ready"):
            bad.append(p["metadata"]["name"] + "/" + c["name"] + ":notready")
if bad:
    print(" ".join(bad[:5]))
    sys.exit(1)
' || return 1
    done
}
wait_settled() {
    local timeout="$1" deadline=$((SECONDS + $1))
    until pods_settled; do
        if [ "$SECONDS" -ge "$deadline" ]; then
            echo "pods not settled after ${timeout}s; continuing"
            return 0
        fi
        sleep 10
    done
}
echo "waiting for application pods to settle"
wait_settled "$READY_TIMEOUT_SEC"
echo "stabilizing for ${SETTLE_SEC}s"
sleep "$SETTLE_SEC"
wait_settled 120
echo "submitting mitigation"
submit ""
