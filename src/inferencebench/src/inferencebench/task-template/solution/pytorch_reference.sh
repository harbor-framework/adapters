#!/bin/bash
# Recomputes the PyTorch quality reference as upstream's run_precompute_all_baselines.sh does
# for the torch backend: upstream's reference server and precompute_quality_baseline at
# concurrency 1, with the packages of upstream's torch baseline container under its lock. The
# questions are the set that this image caches; the image build checks its sha256.
# solve.sh runs this instead of the vLLM oracle when INFERENCE_BENCH_ORACLE=pytorch-reference.
# It leaves no server for the verifier, so the trial is not a benchmark result. Its product is
# /logs/artifacts/pytorch_reference/, which Harbor copies to artifacts/logs/artifacts/ in the
# trial directory.
set -euo pipefail

OUT=/logs/artifacts/pytorch_reference
VENV=/tmp/ib_pytorch_reference
MODEL="${INFERENCE_BENCH_BASE_MODEL}"
NAME="$(printf '%s' "${MODEL}" | sed -E 's/[^A-Za-z0-9_.-]+/_/g')"
SAMPLES="/opt/inference_eval/baselines/samples/mmlu_pro/${INFERENCE_BENCH_QUALITY_SEED}_${INFERENCE_BENCH_QUALITY_MMLUPRO_N}/samples.jsonl"
URL="http://${HOST}:${PORT}"
mkdir -p "${OUT}"

# Upstream's container installs these packages and their CUDA libraries into one directory,
# where torch finds the libraries it was built against. A user install here would leave the
# CUDA libraries that the image already has in the image's directory, and torch would then load
# the base image's CUDA libraries instead. A virtual environment without the image's packages
# keeps them together, as upstream's container does. The image's user install settings would
# make pip install into, and list, the user site instead.
unset PIP_USER PYTHONUSERBASE
python3 -m venv "${VENV}"
PY="${VENV}/bin/python"
"${PY}" -m pip install --no-cache-dir --no-warn-script-location \
    --constraint /solution/torch-constraints.txt {torch_packages}
"${PY}" -m pip freeze > "${OUT}/pip-freeze.txt"

# The healthcheck cached the pinned revision of the model under its name.
export HF_HUB_OFFLINE=1
# What the reference runs on. This stops the run if torch does not use the CUDA libraries that
# it was installed with.
"${PY}" /solution/pytorch_provenance.py "${OUT}/provenance.json" "${VENV}" "${SAMPLES}" "${MODEL}"

cd /solution/ib
"${PY}" -u -m src.eval.inference.servers.transformers_openai_server --host "${HOST}" --port "${PORT}" \
    --model "${MODEL}" --max-model-len "${INFERENCE_BENCH_MAX_MODEL_LEN}" > "${OUT}/server.log" 2>&1 &
server=$!
stop_server() {
    kill "${server}" 2> /dev/null || return 0
    for _ in $(seq 1 20); do
        kill -0 "${server}" 2> /dev/null || return 0
        sleep 0.5
    done
    kill -KILL "${server}" 2> /dev/null || true
}
trap stop_server EXIT
ready=0
for _ in $(seq 1 "${INFERENCE_BENCH_SERVER_WAIT_S}"); do
    if ! kill -0 "${server}" 2> /dev/null; then
        tail -n 50 "${OUT}/server.log"
        echo "[pytorch-reference] the server exited before it was ready" >&2
        exit 1
    fi
    if python3 /opt/inference_eval/bin/server_ready.py "${URL}"; then
        ready=1
        break
    fi
    sleep 1
done
[ "${ready}" -eq 1 ] || { echo "[pytorch-reference] the server did not become ready" >&2; exit 1; }

INFERENCE_BENCH_QUALITY_MMLUPRO_SAMPLES_FILE="${SAMPLES}" \
    "${PY}" -u -m src.eval.inference.precompute_quality_baseline \
    --server-url "${URL}" --base-model "${MODEL}" --backend torch \
    --registry "${OUT}/quality/${NAME}_torch.json" --out-root "${OUT}/quality/torch/${NAME}" \
    --seed "${INFERENCE_BENCH_QUALITY_SEED}" --mmlupro-n "${INFERENCE_BENCH_QUALITY_MMLUPRO_N}" --concurrency 1

cat "${OUT}/quality/${NAME}_torch.json"
echo
echo "[pytorch-reference] done: ${OUT}/quality/${NAME}_torch.json"
