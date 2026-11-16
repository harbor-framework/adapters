#!/bin/bash
set -u

# Clean up any pre-existing or agent-forged reward files
rm -f /logs/verifier/reward.json /logs/verifier/reward.txt /logs/verifier/metrics.json /logs/verifier/report.json
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

cd /testbed
set +e
bash /tests/eval.sh > /logs/verifier/test_output.log 2>&1
set -e

python3 /tests/grade.py /logs/verifier
