#!/bin/bash
set -euo pipefail
mkdir -p "$(dirname "/app/{target_file}")"
cp /solution/{oracle_filename} "/app/{target_file}"
