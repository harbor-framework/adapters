#!/bin/sh
set -eu
exec python /tests/grade.py /logs/verifier/reward.json
