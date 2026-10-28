#!/bin/bash
# Scoring metadata is uploaded by Harbor with /tests after agent execution.
set -Eeuo pipefail
python3 "$(dirname "$0")/verify.py"
