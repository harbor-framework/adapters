#!/usr/bin/env bash
# Score a synthetic case's reference world against itself with the original scorer,
# outside Harbor: the original side of the synthetic oracle comparison.
#
#     scripts/run_original_sanity.sh <cases root> <data root> <checkpoint dir> <kind>/<case> [<run name>]
#
# Runs the `4dcb/scorer:dev` container the way harness/runtime/score.py does for a
# `--sanity` entry: /cases (ro), /data (rw), /runs (rw, empty), /checkpoints (ro), the
# manifest at /manifest.json, `[scorer.environment]` of the upstream runtime template.
# The readings land in <data root>/<kind>/<case>/<run name>/results/ (run name default
# `sanity`). The scorer merges into an existing reward.json, so every run needs a new
# run name (sanity-1, sanity-2, ...); an existing one is refused.
#
# Environment: SCORER_IMAGE (default 4dcb/scorer:dev); CUDA_VISIBLE_DEVICES picks the
# GPU (default `--gpus 1`).
#
# The world gate requires solution/build.sh beside the scored world (scorer/gate.py),
# and the released data has none, so the same placeholder build.sh the Harbor oracle
# submits is placed at <data root>/<kind>/<case>/solution/build.sh first. The upstream
# repository itself is not touched.
set -euo pipefail

usage="usage: run_original_sanity.sh <cases root> <data root> <checkpoint dir> <kind>/<case> [<run name>]"
cases="$(cd "${1:?$usage}" && pwd)"
data="$(cd "${2:?$usage}" && pwd)"
checkpoints="$(cd "${3:?$usage}" && pwd)"
case="${4:?$usage}"
run="${5:-sanity}"
image="${SCORER_IMAGE:-4dcb/scorer:dev}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[ -f "$cases/$case/reference.mp4" ] || { echo "missing $cases/$case/reference.mp4" >&2; exit 1; }
[ -d "$data/$case/world" ] || { echo "missing $data/$case/world (synthetic cases only)" >&2; exit 1; }
[ ! -e "$data/$case/$run" ] || { echo "$data/$case/$run exists; pass a new run name" >&2; exit 1; }
for model in dinov3-vitl16-pretrain-lvd1689m tipsv2-l14 uni3d-l; do
    [ -d "$checkpoints/$model" ] || { echo "missing $checkpoints/$model (scripts/download_checkpoints.sh)" >&2; exit 1; }
done

mkdir -p "$data/$case/solution"
install -m 0755 "$here/src/harbor_4dcodebench/task-template/solution/build.sh" "$data/$case/solution/build.sh"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/runs"
printf '[{"case": "%s", "world": "data/%s/world", "out": "data/%s/%s"}]\n' \
    "$case" "$case" "$case" "$run" > "$work/manifest.json"

threads=()
for name in OMP_NUM_THREADS MKL_NUM_THREADS OPENBLAS_NUM_THREADS NUMEXPR_NUM_THREADS \
            OPENCV_FOR_THREADS_NUM CV_NUM_THREADS; do
    threads+=(--env "$name=8")
done

gpus=(--gpus 1)
[ -n "${CUDA_VISIBLE_DEVICES:-}" ] && gpus=(--gpus "device=$CUDA_VISIBLE_DEVICES")

docker run --rm --cpus=8 --memory=32768m "${threads[@]}" "${gpus[@]}" --network none \
    --entrypoint python \
    -v "$cases:/cases:ro" -v "$data:/data:rw" -v "$work/runs:/runs:rw" \
    -v "$checkpoints:/checkpoints:ro" -v "$work/manifest.json:/manifest.json:ro" \
    "$image" -m scorer --manifest /manifest.json --task-timeout 1800 --prepare-timeout 600 \
    || echo "scorer exit status $? (nonzero whenever a world had a failure; read the results)" >&2

echo "results: $data/$case/$run/results"
