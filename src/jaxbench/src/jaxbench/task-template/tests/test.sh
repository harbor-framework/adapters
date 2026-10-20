#!/bin/bash
# Grade /workspace/kernel.py with JAXBench's own `evaluate` harness.
# The harness copy under /tests is pristine (the agent never sees or edits it).
set -uo pipefail

mkdir -p /logs/verifier
echo '{"reward": 1.0, "speedup": 0.0, "correct": 0, "fast_1": 0}' > /logs/verifier/reward.json

KERNEL=/workspace/kernel.py
RESULT=/logs/verifier/evaluation.json

if [ ! -f "$KERNEL" ]; then
  echo "No kernel found at $KERNEL"
  exit 1
fi

echo "--- Candidate kernel ---"
cat "$KERNEL"
echo "--- End candidate kernel ---"

# The TPU can be opened by only one process. If the agent timed out, processes it started
# (e.g. its own benchmark runs) may still hold /dev/vfio/* and make the evaluator fail with
# "TPU initialization failed: Device or resource busy". Stop them before grading.
# (The image has no ps/fuser, so scan /proc for open file descriptors.)
for proc in /proc/[0-9]*; do
  pid=${proc#/proc/}
  [ "$pid" = "$$" ] && continue
  if ls -l "$proc/fd" 2>/dev/null | grep -q "/dev/vfio"; then
    echo "Stopping leftover process $pid holding the TPU: $(tr '\0' ' ' < "$proc/cmdline" 2>/dev/null | cut -c1-120)"
    kill -9 "$pid" 2>/dev/null
  fi
done
sleep 2

cd /tests
python -m JAXBench evaluate \
  --workload "{{workload}}" \
  --kernel "$KERNEL" \
  --tpu v6e \
  --json > "$RESULT"
echo "JAXBench evaluate exit code: $?"
cat "$RESULT"

# Exits 0 if the kernel is correct, 1 otherwise (the reward file is written either way).
python /tests/compute_reward.py "$RESULT" /logs/verifier/reward.json
