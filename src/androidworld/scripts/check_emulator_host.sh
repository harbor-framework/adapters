#!/bin/bash
# Preflight for running AndroidWorld oracle/agents: is this host able to run the emulator?
#   Inside a built task container:  bash /opt/aw/../check_emulator_host.sh   (or copy it in)
#   On a Docker host:               bash check_emulator_host.sh <generated-task-dir>
# Prints /dev/kvm, arch and CPU virt flags, then tries to boot the emulator and the daemon.
set -u
echo "== uname -m: $(uname -m)"
echo "== /dev/kvm: $(ls -l /dev/kvm 2>&1)"
echo "== cpu virt flags (vmx/svm count): $(grep -E -c '(vmx|svm)' /proc/cpuinfo 2>/dev/null || echo n/a)"
[ "$(uname -m)" = "x86_64" ] || echo "WARN: not x86_64; the API-33 x86_64 system image will need emulation (too slow)."
[ -e /dev/kvm ] || echo "WARN: no /dev/kvm; emulator would run with -accel off (very slow, likely boot timeouts)."

if command -v emulator >/dev/null 2>&1 && [ -x /opt/aw/boot.sh ]; then
  echo "== inside task container: booting emulator + daemon"
  /opt/aw/boot.sh
  python3 /opt/aw/client.py wait && echo "BOOT OK (task initialized)" || { echo "BOOT FAILED"; tail -50 /logs/aw/emulator.log /logs/aw/daemon.log; exit 1; }
  adb devices -l
  exit 0
fi

TASK_DIR="${1:-}"
if [ -z "$TASK_DIR" ] || ! command -v docker >/dev/null 2>&1; then
  echo "Pass a generated task dir (e.g. datasets/androidworld/system-wifi-turn-on) and have docker available to run the container boot test."
  exit 0
fi
docker build --platform linux/amd64 -t aw-preflight "$TASK_DIR/environment" || exit 1
DEV=""; [ -e /dev/kvm ] && DEV="--device /dev/kvm"
docker run --rm --platform linux/amd64 $DEV --privileged aw-preflight bash -c '
  /opt/aw/boot.sh; python3 /opt/aw/client.py wait && echo "BOOT OK" && adb devices -l || { echo "BOOT FAILED"; tail -50 /logs/aw/*.log; exit 1; }'
