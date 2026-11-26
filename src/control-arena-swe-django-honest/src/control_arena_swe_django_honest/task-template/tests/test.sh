#!/bin/bash
set -euo pipefail
cd /testbed
exec /opt/miniconda3/bin/python /tests/grade.py
