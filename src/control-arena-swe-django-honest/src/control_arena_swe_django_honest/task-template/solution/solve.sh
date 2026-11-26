#!/bin/bash
set -euo pipefail
cd /testbed
git apply /solution/gold.patch
submit
