#!/bin/bash
# Oracle: apply the upstream MLOps-Bench reference patch (expected_changes.patch)
# to the starting workspace.
set -euo pipefail

cd /workspace
git apply --whitespace=nowarn /solution/expected_changes.patch
echo "Applied MLOps-Bench oracle patch."
