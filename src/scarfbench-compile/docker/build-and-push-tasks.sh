#!/usr/bin/env bash
# Build and push one thin image per generated task: the toolchain image plus
# that task's environment/app/ at /app.
#
# Why: when task.toml sets docker_image, Harbor pulls it and never runs
# environment/Dockerfile, so the toolchain image alone leaves /app empty.
#
# Usage:
#   ./build-and-push-tasks.sh DATASET_DIR [BASE_IMAGE] [TASK_ID...]
#
# Pushes ${SCARFBENCH_TASK_IMAGE_REPO:-ghcr.io/scarfbench/scarfbench-tasks}:<task_id>.
# Generate the dataset with the same repo via `scarfbench-compile --task-image-repo`.
# Set JOBS=N to build N tasks in parallel (default 4).

set -euo pipefail

DATASET_DIR="${1:?usage: $0 DATASET_DIR [BASE_IMAGE] [TASK_ID...]}"
BASE_IMAGE="${2:-ghcr.io/scarfbench/scarfbench-base:2026-10-09}"
shift $(( $# >= 2 ? 2 : $# ))
REPO="${SCARFBENCH_TASK_IMAGE_REPO:-ghcr.io/scarfbench/scarfbench-tasks}"
JOBS="${JOBS:-4}"

build_one() {
    local dir="$1" base="$2" repo="$3"
    local id; id="$(basename "$dir")"
    [ -d "$dir/environment/app" ] || { echo "SKIP $id (no environment/app)"; return 0; }
    printf 'FROM %s\nWORKDIR /app\nCOPY app/ /app/\n' "$base" |
        docker build --platform linux/amd64 -q -t "$repo:$id" -f - "$dir/environment" >/dev/null
    docker push -q "$repo:$id" >/dev/null
    echo "OK   $repo:$id"
}
export -f build_one

if [ $# -gt 0 ]; then
    tasks=(); for t in "$@"; do tasks+=("$DATASET_DIR/$t"); done
else
    tasks=("$DATASET_DIR"/*/)
fi

printf '%s\0' "${tasks[@]}" |
    xargs -0 -n1 -P "$JOBS" -I{} bash -c 'build_one "$1" "$2" "$3"' _ {} "$BASE_IMAGE" "$REPO"
