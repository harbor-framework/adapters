#!/bin/bash
set -euo pipefail

mkdir -p /work
cp /solution/build.py /work/build.py
cd /work
python3 -c '
import build
model = build.build()
model.write("/work/model.mpd")
'
