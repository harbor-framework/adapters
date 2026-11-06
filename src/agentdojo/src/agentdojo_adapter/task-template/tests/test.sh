#!/bin/bash
set -uo pipefail

REWARD_FILE="/logs/verifier/reward.txt"
mkdir -p /logs/verifier

# evaluate.py fetches the upstream checks from agentdojo-runtime and writes
# reward.json (reward, utility, security) and $REWARD_FILE (utility).
python3 /tests/evaluate.py
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
