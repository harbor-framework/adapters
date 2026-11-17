#!/bin/bash
# Oracle: a replay-verified VimGolf solution ({{ORACLE_SOURCE}}).
set -e
echo '{{ORACLE_KEYS_B64}}' | base64 -d > /app/solution.txt
