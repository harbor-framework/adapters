#!/bin/bash
# Oracle: UI-free reference solution (state injection / computed answer) executed by the
# in-container AndroidWorld daemon. See environment/aw/oracles.py and the adapter README.
set -e
/opt/aw/boot.sh || true
python3 /opt/aw/client.py oracle
