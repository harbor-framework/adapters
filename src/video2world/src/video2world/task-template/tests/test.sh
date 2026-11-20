#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
{python} /tests/verifier.py grade --package /workspace/pkg --config /tests/evaluator.json --out /logs/verifier
