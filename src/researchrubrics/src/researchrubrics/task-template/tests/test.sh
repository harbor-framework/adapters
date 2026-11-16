#!/bin/bash
set -uo pipefail

REWARD_FILE="/logs/verifier/reward.txt"
mkdir -p /logs/verifier
# Never trust a reward left over from the agent's run or an earlier attempt.
rm -f "$REWARD_FILE" /logs/verifier/reward.json

# evaluate.py grades /app/report.md with the LLM judge and writes $REWARD_FILE.
python3 -I /tests/evaluate.py
status=$?

if [ $status -ne 0 ]; then
    echo "Verifier failed with exit code $status" >&2
    exit $status
fi
if [ ! -s "$REWARD_FILE" ]; then
    echo "evaluate.py exited cleanly but did not write $REWARD_FILE" >&2
    exit 1
fi
echo "Reward: $(cat "$REWARD_FILE")"
