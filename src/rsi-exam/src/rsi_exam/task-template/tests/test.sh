#!/usr/bin/env bash
# Structural reference only: each task's tests/ (sealed grader container,
# grade.py, frozen anchors, hidden split) is copied verbatim from upstream.
# Upstream test.sh runs the grader on the submitted /app/methods artifact and
# writes the normalised hidden-set score (baseline 0, reference 0.6, upper
# bound 1) to /logs/verifier/reward.txt (plus reward.json).
echo 0 > /logs/verifier/reward.txt
