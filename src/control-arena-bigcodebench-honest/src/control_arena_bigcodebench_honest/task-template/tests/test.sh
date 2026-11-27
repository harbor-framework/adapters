#!/bin/sh
set -eu
mkdir -p /logs/verifier
chmod 700 /logs/verifier /tests
exec python /tests/grade.py /logs/verifier/reward.json
