#!/usr/bin/env bash
# Grades /app/answer.txt with the upstream CharXiv judge (tests/judge.py).
# judge.py writes /logs/verifier/reward.txt; it exits non-zero only on
# infrastructure errors (e.g. no judge API key / judge unreachable).
set -uo pipefail
mkdir -p /logs/verifier
python3 /tests/judge.py
