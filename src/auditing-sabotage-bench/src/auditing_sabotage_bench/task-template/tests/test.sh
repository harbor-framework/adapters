#!/bin/bash
# Grade the audit report with the upstream scoring logic (see grade.py).
set -uo pipefail

mkdir -p /logs/verifier
python3 /tests/grade.py
status=$?
if [ ! -f /logs/verifier/reward.txt ]; then
  echo "grade.py did not write a reward (exit $status)" >&2
  exit 1
fi
exit 0
