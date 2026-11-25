#!/usr/bin/env bash
# Read-only checks of a Linux GPU host before the 4DCodeBench Harbor validation.
#
#     scripts/vm_preflight.sh <4DCodeBench checkout> <data home> <checkpoint dir> [<synthetic case>]
#
# <data home> holds cases/ and data/ (scripts/fetch_case.py or the upstream
# download_data.py) and, from fetch_case.py, SHA256SUMS. Prints one line per check and
# exits nonzero if any check failed. Nothing is installed, built, downloaded or run on
# the GPU. Before the images are built and the checkpoints downloaded, those lines fail
# as expected.
set -uo pipefail

usage="usage: vm_preflight.sh <4DCodeBench checkout> <data home> <checkpoint dir> [<synthetic case>]"
repo="${1:?$usage}"
home="${2:?$usage}"
checkpoints="${3:?$usage}"
case="${4:-B_01}"
commit=6c466be34107d7f388f30f97bf059b68ba1a21b0
harbor_version=0.27.0
failed=0

ok()   { printf 'ok    %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*"; failed=$((failed + 1)); }

echo "== tools"
for tool in git curl sha256sum docker uv harbor nvidia-smi; do
    if command -v "$tool" >/dev/null 2>&1; then ok "$tool: $(command -v "$tool")"; else fail "$tool not on PATH"; fi
done
command -v hf >/dev/null 2>&1 && ok "hf: $(command -v hf)" || warn "hf not on PATH (needed for the checkpoint download)"
if command -v harbor >/dev/null 2>&1; then
    version="$(harbor --version 2>/dev/null | tr -d '\r')"
    [[ "$version" == *"$harbor_version"* ]] && ok "harbor $version" \
        || warn "harbor version '$version'; this adapter was checked against $harbor_version"
fi

echo "== GPU and Docker"
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null \
        | while read -r line; do ok "GPU: $line"; done
fi
if docker info >/dev/null 2>&1; then
    ok "docker daemon reachable without sudo"
    docker compose version >/dev/null 2>&1 && ok "$(docker compose version)" || fail "docker compose (v2 plugin) missing"
    docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q nvidia \
        && ok "docker has the nvidia runtime" \
        || warn "no nvidia runtime in 'docker info' (run: sudo nvidia-ctk runtime configure --runtime=docker)"
    ok "docker root: $(docker info --format '{{.DockerRootDir}}'), $(df -h --output=avail "$(docker info --format '{{.DockerRootDir}}')" 2>/dev/null | tail -1 | tr -d ' ') free"
else
    fail "docker daemon not reachable (is it running, and is the user in the docker group?)"
fi

echo "== upstream checkout"
if [ -d "$repo/.git" ]; then
    head="$(git -C "$repo" rev-parse HEAD)"
    [ "$head" = "$commit" ] && ok "4DCodeBench at $commit" || fail "4DCodeBench at $head, expected $commit"
    [ -z "$(git -C "$repo" status --porcelain)" ] && ok "4DCodeBench clean" || warn "4DCodeBench has local changes"
else
    fail "$repo is not a git checkout"
fi

echo "== data"
for path in cases/synthetic/$case/reference.mp4 data/synthetic/$case/world/camera.json \
            data/synthetic/$case/world/render.mp4 data/synthetic/$case/world/meshes \
            data/synthetic/$case/world/dynamics data/synthetic/$case/estimates/semantic_dinov3.npz \
            data/synthetic/$case/estimates/semantic_tips.npz data/synthetic/$case/estimates/geophys_dinov3.npz; do
    [ -e "$home/$path" ] && ok "$path" || fail "missing $home/$path"
done
if [ -f "$home/SHA256SUMS" ]; then
    (cd "$home" && sha256sum --quiet -c SHA256SUMS >/dev/null 2>&1) \
        && ok "SHA256SUMS: $(wc -l < "$home/SHA256SUMS") files match" || fail "SHA256SUMS mismatch (cd $home && sha256sum -c SHA256SUMS)"
else
    warn "no $home/SHA256SUMS to verify against"
fi
ok "data home: $(df -h --output=avail "$home" 2>/dev/null | tail -1 | tr -d ' ') free"

echo "== checkpoints"
for file in dinov3-vitl16-pretrain-lvd1689m/model.safetensors tipsv2-l14/model.safetensors \
            video-depth-anything-large/video_depth_anything_vitl.pth raft-large/raft_large_C_T_SKHT_V2.pth \
            cotracker3/scaled_offline.pth moge-3-vitl/model.pt uni3d-l/model.pt; do
    [ -s "$checkpoints/$file" ] && ok "$file" || fail "missing $checkpoints/$file"
done

echo "== images"
for image in 4dcb/sim-base:dev 4dcb/agent:dev 4dcb/scorer:dev 4dcb/scorer-checkpoints:dev; do
    if docker image inspect "$image" >/dev/null 2>&1; then
        ok "$image $(docker image inspect --format '{{.Id}}' "$image" | cut -c1-19)"
    else
        fail "image $image not built (scripts/build_images.sh)"
    fi
done

echo
[ "$failed" -eq 0 ] && echo "preflight: all checks passed" || echo "preflight: $failed check(s) failed"
exit $((failed > 0))
