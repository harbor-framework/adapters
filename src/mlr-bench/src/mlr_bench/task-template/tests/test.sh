#!/bin/bash
# MLR-Bench verifier: scores the agent's paper with the official MLR-Judge
# end-to-end evaluator (upstream mlrbench/evals/overall_review.py).
#
# A missing or empty paper scores 0. If the judge cannot return a complete
# review, judge.py writes no reward and exits non-zero, so the trial is
# recorded as a verifier error rather than as a zero score.
set -euo pipefail

mkdir -p /logs/verifier

echo "Installing judge dependencies..."
pip install --quiet litellm

echo "Running MLR-Judge (overall review)..."
python3 /tests/judge.py

echo "Reward: $(cat /logs/verifier/reward.txt)"
