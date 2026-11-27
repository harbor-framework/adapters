#!/bin/bash
set -uo pipefail

WORKING_DIR="{working_dir}"
BASE_COMMIT="{base_commit}"
PATCH=/tmp/submission/model.patch
OUT=/logs/verifier

mkdir -p "$OUT"
echo 0 > /logs/verifier/reward.txt
: > "$OUT/stage_exit_codes.tsv"
record() { printf '%s\t%s\n' "$1" "$2" >> "$OUT/stage_exit_codes.tsv"; }

PYTHON="$(command -v python3)"
if [ -z "$PYTHON" ]; then echo "python3 not found in the verifier image"; exit 0; fi

cd "$WORKING_DIR" || { echo "missing working directory: $WORKING_DIR"; record setup 2; exit 0; }
git config --global --add safe.directory "$WORKING_DIR" >/dev/null 2>&1 || true

# 1. The agent's changes.
if [ -L "$PATCH" ] || [ ! -f "$PATCH" ]; then
    echo "No submitted patch at $PATCH"
    record model_patch 2
    exit 0
fi
cp "$PATCH" /tmp/model.patch
git apply --allow-empty --reject --whitespace=nowarn /tmp/model.patch > "$OUT/model_patch.log" 2>&1
MODEL_RC=$?
record model_patch "$MODEL_RC"
if [ "$MODEL_RC" -ne 0 ]; then echo "The submitted patch does not apply"; exit 0; fi

# 2. The hidden tests. Files they touch are first reset to the base commit, so
#    the submission cannot replace or weaken them.
"$PYTHON" /tests/grade.py list-test-files /tests/test.patch | while IFS= read -r f; do
    if git cat-file -e "$BASE_COMMIT:$f" 2>/dev/null; then
        git checkout -q "$BASE_COMMIT" -- "$f"
    else
        rm -f -- "$f"
    fi
done
git apply --allow-empty --reject --whitespace=nowarn /tests/test.patch > "$OUT/test_patch.log" 2>&1
TEST_PATCH_RC=$?
record test_patch "$TEST_PATCH_RC"
if [ "$TEST_PATCH_RC" -ne 0 ]; then echo "The test patch does not apply"; exit 0; fi

# 3. Rebuild, run the tests, print the results (the task's own commands).
bash /tests/rebuild.sh > "$OUT/rebuild.log" 2>&1
record rebuild "$?"
bash /tests/run_tests.sh > "$OUT/test.log" 2>&1
record test "$?"
bash /tests/print.sh > "$OUT/print.log" 2>&1
record print "$?"

# 4. Parse and decide.
if ! "$PYTHON" /tests/grade.py grade /tests/expected.json "$OUT/print.log" /tests/log_parser.py "$OUT"; then
    echo "Grader failed"
    echo 0 > /logs/verifier/reward.txt
fi
