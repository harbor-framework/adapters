#!/bin/bash

# Stub, never shipped: the builders generate tests/test.sh from
# VERIFIER_TEST_SH in `asta_bench/benchmarks/base.py`.
set -u
mkdir -p /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json
echo "task-template stub: no scorer; replaced per task by the family builders" >&2
echo 0 > /logs/verifier/reward.txt
