#!/bin/bash
mkdir -p /logs/verifier
cd /tests && python3 /tests/score_task.py
if [ ! -s /logs/verifier/reward.txt ]; then
  echo 0 > /logs/verifier/reward.txt
fi
cat /logs/verifier/grading_details.json 2>/dev/null
