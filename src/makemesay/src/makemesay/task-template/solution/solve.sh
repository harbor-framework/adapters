#!/usr/bin/env bash
set -euo pipefail

# This fixture checks verifier transport and score computation only. It is not
# a MakeMeSay model run and must not be reported as benchmark performance.
solution_dir="$(cd "$(dirname "$0")" && pwd)"
cp "$solution_dir/fixture_result.json" /workspace/makemesay_result.json
