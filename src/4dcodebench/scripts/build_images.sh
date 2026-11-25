#!/usr/bin/env bash
# Build the images the generated tasks build FROM.
#
#     scripts/build_images.sh <4DCodeBench checkout> [<checkpoint directory>]
#
# The first three are the upstream images, built exactly as the 4DCodeBench README
# does: 4dcb/sim-base:dev, 4dcb/agent:dev, 4dcb/scorer:dev. With a checkpoint directory
# (the upstream scripts/download_checkpoints.sh, ~6.7 GB, gated DINOv3 access required),
# the fourth, 4dcb/scorer-checkpoints:dev, adds it to the scorer image for the Harbor
# verifier. Without one, only the upstream images are built, so they can build while the
# checkpoints download; run again with the directory afterwards (Docker reuses the cache).
set -euo pipefail

usage="usage: build_images.sh <4DCodeBench checkout> [<checkpoint directory>]"
repo="$(cd "${1:?$usage}" && pwd)"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
checkpoints=""
if [ -n "${2:-}" ]; then
    checkpoints="$(cd "$2" && pwd)"
    for model in dinov3-vitl16-pretrain-lvd1689m tipsv2-l14 uni3d-l; do
        [ -d "$checkpoints/$model" ] || { echo "missing $checkpoints/$model (run scripts/download_checkpoints.sh)" >&2; exit 1; }
    done
fi

(cd "$repo" && docker build -t 4dcb/sim-base:dev -f harness/base/Dockerfile .)
(cd "$repo" && docker build -t 4dcb/agent:dev -f harness/agent/Dockerfile .)
(cd "$repo" && docker build -t 4dcb/scorer:dev -f harness/scorer/Dockerfile .)
if [ -n "$checkpoints" ]; then
    docker build -t 4dcb/scorer-checkpoints:dev --build-arg SCORER_IMAGE=4dcb/scorer:dev \
        -f "$here/docker/scorer-checkpoints.Dockerfile" "$checkpoints"
else
    echo "4dcb/scorer-checkpoints:dev not built: pass the checkpoint directory" >&2
fi
docker image ls --filter reference='4dcb/*'
