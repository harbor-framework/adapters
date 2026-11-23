#!/bin/bash
# Oracle: write the upstream canonical_solution in place of the buggy body.
set -euo pipefail
cat > {file_path} <<'HUMANEVALPACK_ORACLE_EOF'
{oracle_program}
HUMANEVALPACK_ORACLE_EOF
