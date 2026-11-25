#!/usr/bin/env bash
# Oracle for 4DCodeBench synthetic case {case_key}: submit the published reference world.
#
# /solution/world is the case's reference world as released by the benchmark authors
# (4DCodeBench/Dataset-Synthetic, worlds/{case_name}.h5, unpacked by the upstream
# scripts/download_data.py). It is copied to /workspace/world unchanged.
#
# The scorer's world gate requires solution/build.sh to exist (scorer/gate.py). The
# simulation program that produced the reference world is not released, so
# /workspace/solution/build.sh is a placeholder that says so and exits with status 1;
# it is not a scene-generation program and cannot rebuild the world.
#
# The score of this submission is the case's per-metric ceiling, the same quantity as
# the original `harness/runtime/score.py --sanity` reading. It is not expected to be 1
# on every metric.
set -euo pipefail

rm -rf /workspace/world /workspace/solution
mkdir -p /workspace/solution
cp -a /solution/world /workspace/world
install -m 0755 /solution/build.sh /workspace/solution/build.sh
echo "oracle: copied the reference world of {case_key} and the placeholder build.sh"
