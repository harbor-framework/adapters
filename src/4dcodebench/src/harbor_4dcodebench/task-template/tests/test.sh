#!/usr/bin/env bash
# Harbor verifier entry point: score /workspace/world with the original 4DCodeBench
# scorer and write /logs/verifier/reward.json (see run_verifier.py).
set -uo pipefail

mkdir -p /logs/verifier
python /tests/run_verifier.py 2>&1 | tee /logs/verifier/4dcodebench_verifier.log
exit "${PIPESTATUS[0]}"
