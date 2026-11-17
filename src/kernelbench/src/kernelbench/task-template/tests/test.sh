#!/bin/bash
mkdir -p /logs/verifier
echo '{"reward": 0, "correct": 0, "compiled": 0, "fast_1": 0, "speedup": 0}' > /logs/verifier/reward.json
echo 0 > /logs/verifier/reward.txt
cd /tmp && python /tests/grade.py 2>&1 | tee /logs/verifier/grade.log
