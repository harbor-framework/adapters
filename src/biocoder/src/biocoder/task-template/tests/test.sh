#!/bin/bash
set -u

# Clean up any pre-existing or agent-forged reward files
rm -f /logs/verifier/reward.json /logs/verifier/reward.txt /logs/verifier/metrics.json
mkdir -p /logs/verifier

# Check if solution file exists
if [ ! -f /app/solution.py ]; then
    echo "ERROR: /app/solution.py not found"
    echo '0.0' > /logs/verifier/reward.txt
    exit 0
fi

# Execute differential testing runner (writes reward to /logs/verifier/reward.txt)
set +e
python3 /tests/test_runner.py
runner_exit=$?
set -e

# Fallback: guarantee reward.txt exists on every code path
if [ ! -f /logs/verifier/reward.txt ]; then
    echo "WARNING: test_runner did not write reward.txt, defaulting to 0.0"
    echo '0.0' > /logs/verifier/reward.txt
fi

exit 0
