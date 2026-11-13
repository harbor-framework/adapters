#!/bin/bash

# Per-family builders generate the actual tests/test.sh from the shared
# verifier contract in `asta_bench/benchmarks/base.py` (VERIFIER_TEST_SH).
# This stub is never shipped; it only mirrors that contract's shape: remove
# any pre-existing reward, score, and record a reward only for a scored
# outcome.
set -u
mkdir -p /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json
echo "task-template stub: no scorer; replaced per task by the family builders" >&2
echo 0 > /logs/verifier/reward.txt
