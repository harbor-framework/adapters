#!/bin/bash
set -euo pipefail
answer_path="${CHESS_PUZZLES_ANSWER_PATH:-/app/answer.txt}"
mkdir -p "$(dirname "$answer_path")"
printf '%s\n' '__TARGET__' > "$answer_path"
