#!/usr/bin/env bash
# RSI-Exam ships no frontier-calibrated reference solution for this task
# ({task_id}). This placeholder oracle leaves the shipped weak baseline in
# /app/methods/ untouched, so the verifier grades the baseline itself
# (normalised to ~0 by the task's frozen anchors). It verifies that the
# environment builds and the sealed grader runs end to end; it is NOT a
# full-score oracle. See the adapter README (Notes & Caveats).
set -euo pipefail
echo "[oracle] {task_id}: no upstream reference solution; submitting the shipped baseline unchanged."
