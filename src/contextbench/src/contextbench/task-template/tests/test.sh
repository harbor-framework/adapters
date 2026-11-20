#!/bin/sh
set -u

# The verifier image holds /tests and /workspace, and Harbor mounts /logs.
# Tests set CONTEXTBENCH_VERIFIER_ROOT to run this script against a scratch
# directory instead.
root=${CONTEXTBENCH_VERIFIER_ROOT:-}

mkdir -p "$root/logs/verifier"
rm -f "$root/logs/verifier/reward.txt" "$root/logs/verifier/reward.json" \
    "$root/logs/verifier/contextbench-metrics.json"

python "$root/tests/score.py" \
    --trajectory "$root/logs/agent/trajectory.json" \
    --gold "$root/tests/gold.json" \
    --attribution-config "$root/tests/attribution.json" \
    --repository "$root/workspace" \
    --model-patch "$root/logs/artifacts/contextbench-model.patch" \
    --collection-error "$root/logs/artifacts/contextbench-collect-error.txt" \
    --output "$root/logs/verifier/reward.json" \
    --diagnostics "$root/logs/verifier/contextbench-metrics.json" || exit

python -c 'import json, sys; print(json.load(open(sys.argv[1]))["reward"])' \
    "$root/logs/verifier/reward.json" > "$root/logs/verifier/reward.txt"
