#!/bin/bash
set -euo pipefail
echo 'Video2World oracle is only generated for convertible tasks (72/222); this task lacks a convertible upstream candidate package or controller.' >&2
exit 1
