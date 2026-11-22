#!/bin/sh
set -eu
mkdir -p /logs/verifier
exec /usr/bin/python3 -I /tests/grade.py
