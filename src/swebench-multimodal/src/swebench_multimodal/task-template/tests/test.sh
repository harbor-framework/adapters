#!/bin/bash
set -eu

# Clean up any pre-existing or agent-forged reward files
rm -f /logs/verifier/reward.json /logs/verifier/reward.txt /logs/verifier/metrics.json /logs/verifier/report.json
mkdir -p /logs/verifier
python3 -I /tests/apply_submission.py

cd /testbed
set +e
bash /tests/eval.sh > /logs/verifier/test_output.log 2>&1
set -e

python3 /tests/grade.py /logs/verifier
