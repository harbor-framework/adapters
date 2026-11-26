#!/bin/bash

# Grades a Petri audit.
#
# The audit's transcript is collected as an artifact.
#
# tests/judge.py scores it on the Petri judge dimensions,
# then writes a float reward to /logs/verifier/reward.txt
# and all dimension scores to /logs/verifier/scores.json.


echo "Grading Petri audit..."

mkdir -p /logs/verifier

python3 /tests/judge.py
exit $?
