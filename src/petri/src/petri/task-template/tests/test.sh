#!/bin/bash

# Grades a Petri audit.
#
# The transcript is only retrievable from the auditor sidecar using RESULT_TOKEN.
#
# tests/judge.py scores it on the Petri judge dimensions in tests/dimensions/
# and writes a float reward to /logs/verifier/reward.txt.

echo "Grading Petri audit..."

mkdir -p /logs/verifier

python3 /tests/judge.py
exit $?
