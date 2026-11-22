#!/bin/sh
set -eu
# The isolated grader writes /logs/verifier/reward.txt after native verification.
exec python -I /tests/grade.py
