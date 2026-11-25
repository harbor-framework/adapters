#!/bin/bash
# Verifier: asks the in-container AndroidWorld daemon to run the task's own
# `is_successful` check (the original benchmark evaluation) and writes the reward.
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
/opt/aw/boot.sh || true
out=$(python3 /opt/aw/client.py score)
echo "$out"
score=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['score'])" "$out")
echo "$score" > /logs/verifier/reward.txt
