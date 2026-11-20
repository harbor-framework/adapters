#!/bin/bash
# JobBench ships rubrics, not reference deliverables. When a reference
# deliverable has been added for this task it lives next to this script in
# deliverables/ and is submitted as the final output. Without one the oracle
# fails loudly instead of submitting an empty answer.
set -euo pipefail

SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DELIVERABLES="$SOLUTION_DIR/deliverables"

if [ ! -d "$DELIVERABLES" ] || [ -z "$(ls -A "$DELIVERABLES")" ]; then
    echo "No reference deliverable is available for this JobBench task." >&2
    exit 1
fi

mkdir -p /workspace/output
cp -R "$DELIVERABLES"/. /workspace/output/
