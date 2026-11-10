#!/bin/bash

# Grades a CAIBench task.
#
# tests/grade.py reads tests/expected.json and /logs/agent/,
# then writes a float reward to /logs/verifier/reward.txt.

mkdir -p /logs/verifier

python3 /tests/grade.py
exit $?
