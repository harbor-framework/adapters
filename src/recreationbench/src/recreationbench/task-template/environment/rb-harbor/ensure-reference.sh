#!/usr/bin/env bash
# Start the benchmark's own static handler for the frozen reference if it is not
# already serving, then wait until it answers. Idempotent: used by the image
# entrypoint and by the task healthcheck (for providers that skip entrypoints).
set -u
PORT="${RB_REFERENCE_PORT:-8100}"
URL="http://127.0.0.1:${PORT}/"

up() { curl -fsS -o /dev/null --max-time 5 "$URL"; }

if up; then exit 0; fi
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    exec sudo -n "$0" "$@"
  fi
  echo "reference server is not running and only root can start it" >&2
  exit 1
fi
SITE_DIR="$(cat /opt/rb-harbor/site_dir)"
PIPELINE="${RB_PIPELINE_DIR:-/workspace/RecreationBench}"
if ! pgrep -f "static_handler.py ${PORT} " >/dev/null 2>&1; then
  cd /
  nohup setsid python3 "${PIPELINE}/scripts/web/serving/static_handler.py" "${PORT}" "${SITE_DIR}" \
    >/var/log/rb-reference.log 2>&1 </dev/null &
fi
for _ in $(seq 1 60); do
  if up; then exit 0; fi
  sleep 1
done
echo "reference server did not come up; see /var/log/rb-reference.log" >&2
tail -n 20 /var/log/rb-reference.log >&2 || true
exit 1
