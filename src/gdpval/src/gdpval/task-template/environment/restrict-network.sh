#!/bin/bash
set -euo pipefail

# Network policy belongs to Harbor/Docker, not agent-writable iptables rules.
# Keep the upstream entrypoint path for image compatibility.
exec "$@"
