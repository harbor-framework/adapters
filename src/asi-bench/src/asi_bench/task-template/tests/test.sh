#!/bin/sh
python /tests/score_entry.py
status=$?
[ -f /logs/verifier/reward.txt ] || echo 0 > /logs/verifier/reward.txt
exit "$status"
