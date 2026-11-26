#!/bin/bash
# Oracle: copy the reference response the adapter wrote for this task to
# /app/response.txt. It is a rule-generated answer for 80k, a rule-generated refusal
# for toxic, and a stored, judge-checked answer for hard-1k.
set -euo pipefail
cp /solution/response.txt /app/response.txt
