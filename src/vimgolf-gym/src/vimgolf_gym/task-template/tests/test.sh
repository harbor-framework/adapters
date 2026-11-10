#!/bin/bash
# Grades /app/solution.txt exactly like vimgolf-evaluate.py
# (--validator vimgolf-validator --solution-not-longer-than-output).
mkdir -p /logs/verifier
python3 /tests/grade.py
if [ ! -s /logs/verifier/reward.txt ]; then
  echo 0 > /logs/verifier/reward.txt
fi
cat /logs/verifier/grading_details.json 2>/dev/null
