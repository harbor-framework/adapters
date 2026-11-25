#!/usr/bin/env bash
# 4DCodeBench Harbor adapter: ORACLE PLACEHOLDER, not a scene-generation program.
#
# The oracle submits the published reference world of a synthetic case unchanged. The
# scorer's world gate requires solution/build.sh to exist (scorer/gate.py), but the
# program that generated the reference world is not released, so this script cannot
# rebuild world/ and exits with status 1.
echo "4DCodeBench oracle placeholder: the reference world was not produced by this script and cannot be rebuilt by it." >&2
exit 1
