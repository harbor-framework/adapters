#!/bin/bash
# Idempotent: boots the headless emulator + AndroidWorld daemon (which initializes the task).
# Safe to call repeatedly (entrypoint, solve.sh, test.sh and the agent may all call it).
mkdir -p /logs/aw
if pgrep -f "[a]w/daemon.py" >/dev/null 2>&1; then exit 0; fi
exec 9>/tmp/aw_boot.lock; flock -n 9 || exit 0
(
  export ANDROID_HOME="${ANDROID_HOME:-/opt/android}"
  export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
  export EMULATOR_NAME="${EMULATOR_NAME:-AndroidWorldAvd}"
  export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator"

  log() { printf '[aw-boot] %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> /logs/aw/boot.log; }

  if [ ! -e /dev/kvm ] && [ "${ANDROIDWORLD_ALLOW_TCG:-0}" != "1" ]; then
    msg="AndroidWorld requires /dev/kvm. Set ANDROIDWORLD_ALLOW_TCG=1 only for slow software-emulation debugging."
    log "ERROR: $msg"
    printf '%s\n' "$msg" >&2
    exit 1
  fi

  ACCEL="-accel on"
  if [ ! -e /dev/kvm ]; then
    export ANDROID_I_WANT_MY_TCG=yes
    ACCEL="-accel off -qemu -accel tcg,thread=multi"
  fi
  log "starting boot (emulator=$EMULATOR_NAME accel='$ACCEL')"

  adb kill-server >/dev/null 2>&1 || true
  adb start-server >> /logs/aw/boot.log 2>&1
  # Clean up any orphan emulator holding console/gRPC ports before launching a fresh one.
  adb devices | awk '/^emulator-/{print $1}' | while read -r serial; do
    adb -s "$serial" emu kill >/dev/null 2>&1 || true
  done

  nohup emulator @"${EMULATOR_NAME}" -no-window -no-snapshot -no-boot-anim -noaudio -no-metrics \
      -memory 4096 $ACCEL -gpu swiftshader_indirect -grpc 8554 > /logs/aw/emulator.log 2>&1 &

  booted=0
  for i in $(seq 1 150); do
    if [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; then
      booted=1
      break
    fi
    sleep 4
  done
  if [ "$booted" != "1" ]; then
    log "ERROR: emulator failed to complete boot within 600s"
    exit 1
  fi
  log "emulator boot_completed=1; restarting adbd as root"

  adb root >> /logs/aw/boot.log 2>&1 || true
  adb wait-for-device
  for i in $(seq 1 30); do
    if adb shell true >/dev/null 2>&1; then break; fi
    sleep 1
  done

  adb shell input keyevent 82 >> /logs/aw/boot.log 2>&1 || true
  adb shell "settings put global window_animation_scale 0.0; settings put global transition_animation_scale 0.0; settings put global animator_duration_scale 0.0" >> /logs/aw/boot.log 2>&1 || true
  adb shell "settings put global package_verifier_enable 0; settings put global verifier_verify_adb_installs 0" >> /logs/aw/boot.log 2>&1 || true
  adb shell "settings put global hidden_api_policy_pre_p_apps 1; settings put global hidden_api_policy_p_apps 1; settings put global hidden_api_policy 1" >> /logs/aw/boot.log 2>&1 || true

  export GRPC_VERBOSITY=ERROR GRPC_ENABLE_FORK_SUPPORT=0 GLOG_minloglevel=2
  nohup python3 /opt/aw/daemon.py > /logs/aw/daemon.log 2>&1 &
  log "launched /opt/aw/daemon.py"
) 9>&-
