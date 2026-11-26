#!/bin/bash
set -euo pipefail

# Reference solution: apply the developers' patch.
cd {working_dir}
git apply --allow-empty --reject --whitespace=nowarn /solution/gold.patch
echo "Applied the reference patch"
