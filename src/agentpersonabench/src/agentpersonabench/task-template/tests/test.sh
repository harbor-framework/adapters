#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier /input
cp -a /app/input/. /input/

export ADHERENCE_OUTPUT_DIR=/app/output
export ADHERENCE_VERIFIER_DIR=/logs/verifier

set +e
python3 /tests/verifier.py
set -e

if [ ! -f /logs/verifier/reward.txt ]; then
  echo 0 > /logs/verifier/reward.txt
fi
exit 0
