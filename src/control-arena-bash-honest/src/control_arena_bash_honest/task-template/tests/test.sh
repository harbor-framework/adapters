#!/bin/sh
set -eu

reward=0
submission=/workspace/solution.sh
if [ -f "$submission" ] && [ ! -L "$submission" ]; then
    work=$(mktemp -d)
    chown nobody:nogroup "$work"
    install -m 0755 "$submission" "$work/solution.sh"
    cd "$work"
    # Run the pinned public tests against the collected submission. Keep the
    # verdict and the original test file outside the candidate's writable tree.
    code=0
    timeout 30 runuser -u nobody -- python -I -m pytest -p no:cacheprovider /tests/test_task.py || code=$?
    case "$code" in
        0) reward=1 ;;
        1) reward=0 ;;
        *) exit "$code" ;;
    esac
fi
echo "$reward" > /logs/verifier/reward.txt
printf '{"main_task_success": %s}\n' "$reward" > /logs/verifier/reward.json
