#!/bin/bash
set -euo pipefail

mkdir -p /workspace
cat > /workspace/response.txt <<'__HARBOR_IFEVAL_ORACLE_EOF__'
{oracle_response}
__HARBOR_IFEVAL_ORACLE_EOF__
