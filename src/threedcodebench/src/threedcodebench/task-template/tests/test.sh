#!/bin/bash
# Re-executes the agent's script in a fresh Blender process and scores it with
# the upstream 3DCodeBench helpers (see evaluate.py).
#   /logs/verifier/reward.txt    executability (0 or 1)
#   /logs/verifier/metrics.json  per-stage statuses + Chamfer distances
# A verifier-internal error writes no reward, so Harbor records an
# infrastructure failure instead of a score of 0.
mkdir -p /logs/verifier
exec blender-python /tests/evaluate.py --instance "{{INSTANCE}}"
