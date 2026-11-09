#!/bin/bash
# Run only after generation, on a Docker-enabled host with Harbor installed.
set -euo pipefail
dataset="${1:-datasets/supergpqa}"
command -v harbor >/dev/null || { echo 'Harbor CLI is not installed or not on PATH.' >&2; exit 1; }
command -v docker >/dev/null || { echo 'Docker CLI is not installed or not on PATH.' >&2; exit 1; }
docker info >/dev/null
test -f "$dataset/generation_manifest.json" || { echo 'Generate the dataset first.' >&2; exit 1; }
harbor run -p "$dataset" -a oracle --n-concurrent 4
