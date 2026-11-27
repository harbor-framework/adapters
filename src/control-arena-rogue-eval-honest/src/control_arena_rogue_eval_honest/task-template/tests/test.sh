#!/bin/sh
set -eu
python -I /tests/grade.py
test -s /logs/verifier/reward.json
