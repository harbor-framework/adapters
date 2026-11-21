#!/usr/bin/env bash
set -euo pipefail

mkdir -p /logs/verifier
python3 /tests/verify_result.py \
  --expected /tests/expected.json \
  --result /workspace/makemesay_result.json \
  --reward /logs/verifier/reward.json
