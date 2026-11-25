#!/bin/sh
set -eu
# Multiple native reward dimensions live in /logs/verifier/reward.json.
PYTHONPATH=/tests python -m geoprobe.grader
