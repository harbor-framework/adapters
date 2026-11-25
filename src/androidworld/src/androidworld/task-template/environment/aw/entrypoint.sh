#!/bin/bash
# Start emulator + daemon in the background, then hand over to the container command
# (Harbor's default is `sleep infinity`). Environments that ignore ENTRYPOINT still work
# because solve.sh / test.sh call `boot.sh` + `client.py wait` themselves.
nohup /opt/aw/boot.sh > /tmp/aw_boot.out 2>&1 &
exec "$@"
