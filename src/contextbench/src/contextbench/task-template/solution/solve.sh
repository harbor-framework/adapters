#!/bin/sh
set -eu

# The oracle trajectory reads every gold range; the verifier clamps ranges to
# the checkout and credits nothing for files absent at the base commit.
cp /solution/oracle-trajectory.json /logs/agent/trajectory.json
if [ -s /solution/solution.patch ]; then
    git -C /workspace apply --whitespace=nowarn /solution/solution.patch
fi
