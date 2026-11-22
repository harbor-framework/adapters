#!/bin/sh
set -eu
if [ ! -f /solution/trajectory.json ]; then
  echo 'No validated reference trajectory exists for this task yet.' >&2
  exit 1
fi
exec python /solution/replay.py /solution/trajectory.json
