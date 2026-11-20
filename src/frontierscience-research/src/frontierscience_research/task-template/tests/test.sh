#!/bin/bash
# Grade /workspace/answer.md against the rubric with an LLM judge.
# grader.py writes /logs/verifier/reward.json ({"reward", "score"}) and
# /logs/verifier/grading.json (full judge transcript and metadata).
set -uo pipefail

mkdir -p /logs/verifier
python3 /tests/grader.py
