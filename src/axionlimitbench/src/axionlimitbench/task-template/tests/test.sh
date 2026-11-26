#!/bin/bash
set -uo pipefail

PYTHON=/usr/local/bin/python3
RESULT=/app/result.json
WORK=/tmp/score

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

rm -rf "$WORK"
mkdir -p "$WORK"

if [ -L "$RESULT" ]; then
    echo "Rejecting symlinked result: $RESULT"
elif [ -f "$RESULT" ]; then
    cp "$RESULT" "$WORK/result.json"
else
    echo "Result file not found: $RESULT"
fi

if ! "$PYTHON" /tests/score.py "$WORK/result.json" /logs/verifier; then
    echo "Scorer failed"
    echo 0 > /logs/verifier/reward.txt
fi
