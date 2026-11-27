#!/bin/sh
set -eu
/opt/infra-scorer/bin/python -I /tests/grade.py
test -s /logs/verifier/reward.txt
