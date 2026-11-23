#!/bin/bash

# Grades an ARC-AGI-3 game session.
#
# Uses the agent's actions log to replay the game.

echo "Grading ARC-AGI-3 session..."

mkdir -p /logs/verifier

python3 /tests/grade.py
exit $?
