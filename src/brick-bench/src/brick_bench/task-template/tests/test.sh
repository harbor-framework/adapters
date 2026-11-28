#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
python3 /tests/grade.py
status=$?

if [ "$status" -ne 0 ]; then
  echo "grade.py exited with status $status" >&2
  exit "$status"
fi

if [ ! -f /logs/verifier/reward.json ] && [ ! -f /logs/verifier/reward.txt ]; then
  echo "grade.py did not write /logs/verifier/reward.json" >&2
  exit 1
fi

exit 0
