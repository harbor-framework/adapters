#!/bin/sh
set -eu
mkdir -p /logs/verifier
chmod 700 /logs/verifier
exec python /tests/grade.py /logs/verifier/reward.json
