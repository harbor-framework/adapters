#!/bin/bash
set -e

echo "Starting DeepResearch Bench verification..."
mkdir -p /logs/verifier
# Remove any stale or agent-written reward first. A reward is written only
# after valid grading; on judge/API failure none is written, so Harbor reports
# a verifier error instead of accepting a 0.
rm -f /logs/verifier/reward.txt /logs/verifier/judgment.json

# Oracle fast path: solve.sh copies a per-task random token that exists only in
# /solution (never visible to agents); a hash match proves the oracle ran.
# The token is unrelated to the public reference report, so downloading that
# report does not trigger this path.
ORACLE_TOKEN_SHA=$(jq -r '.oracle_token_sha256 // empty' /tests/config.json 2>/dev/null || true)
if [ -n "$ORACLE_TOKEN_SHA" ] && [ -f /workspace/.oracle_token ] \
    && [ "$(sha256sum /workspace/.oracle_token | cut -d' ' -f1)" = "$ORACLE_TOKEN_SHA" ]; then
    echo "Oracle token verified; skipping LLM judge."
    echo 1.0 > /logs/verifier/reward.txt
    exit 0
fi

# run_test.py writes 0.0 itself for a missing/empty /workspace/output.md (a
# valid outcome) and exits non-zero without a reward on infrastructure errors.
echo "Running LLM judge evaluation..."
python3 /tests/run_test.py
