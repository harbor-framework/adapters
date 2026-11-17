#!/bin/bash
set -euo pipefail
# grade.py writes /logs/verifier/reward.txt (and result.json) and always exits 0 once a reward exists.
mkdir -p /logs/verifier
python3 /tests/grade.py --output-dir /logs/verifier
