#!/bin/bash
# Oracle: copy the reference answer (written against this task's rubric) into place.
set -euo pipefail

SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -s "$SOLUTION_DIR/answer.md" ]; then
    echo "No oracle answer was generated for this task (solution/answer.md missing)." >&2
    exit 1
fi

mkdir -p /workspace
cp "$SOLUTION_DIR/answer.md" /workspace/answer.md
echo "Oracle answer written to /workspace/answer.md"
