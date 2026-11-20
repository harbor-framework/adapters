#!/bin/sh
# Runs the upstream JobBench rubric judge. verify.py writes the weighted reward
# (0 to 1) to /logs/verifier/reward.json, or exits non-zero without a reward when
# the judge itself fails, so an infrastructure error is never scored as zero.
set -eu

exec python /tests/verify.py
