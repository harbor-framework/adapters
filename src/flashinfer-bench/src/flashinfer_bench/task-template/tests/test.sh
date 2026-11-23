#!/bin/bash
set -euo pipefail
# Writes /logs/verifier/reward.txt using the unchanged upstream speedup score.
python /tests/runtime/evaluate.py
