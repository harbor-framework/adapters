#!/bin/bash
set -euo pipefail

# DRACO ships no reference reports. The oracle copies the report staged into
# solution/report.md at generation time (see the adapter README).
mkdir -p /app
cp /solution/report.md /app/report.md
echo "Oracle report written to /app/report.md ($(wc -c < /app/report.md) bytes)"
