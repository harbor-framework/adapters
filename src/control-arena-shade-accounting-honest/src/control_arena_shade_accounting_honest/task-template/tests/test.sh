#!/bin/sh
set -eu
python /tests/grade.py
test -s /logs/verifier/reward.txt
