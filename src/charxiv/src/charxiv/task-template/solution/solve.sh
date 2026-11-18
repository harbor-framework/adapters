#!/usr/bin/env bash
# Oracle: write the CharXiv ground-truth answer.
set -euo pipefail
mkdir -p /app
cat > {{answer_path}} <<'CHARXIV_ORACLE_EOF'
{{answer}}
CHARXIV_ORACLE_EOF
