#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
# An infrastructure failure must not leave behind a stale success reward.
rm -f /logs/verifier/reward.txt
${VERIFIER_PYTHON:-python} -I /tests/verify.py --workspace /work --output-dir /logs/verifier
