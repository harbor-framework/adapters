#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/result.json

python3 /tests/judge.py \
  --state /root/logs/consultation_state.json \
  --case /tests/case.json \
  --reward /logs/verifier/reward.txt \
  --result /logs/verifier/result.json
