#!/bin/bash
set -euo pipefail
cd /testbed
/opt/miniconda3/bin/python /tests/grade.py
test -s /logs/verifier/reward.txt
