#!/bin/bash
# Oracle: ship vLLM with default settings, which is the "vLLM default" row of the paper's
# Table 2. InferenceBench has no reference solution because the score is an unbounded
# speedup. This run checks the task and verifier end to end against published numbers; it
# is not an upper bound on the score.
set -euo pipefail

case "${INFERENCE_BENCH_ORACLE:-vllm}" in
    vllm) ;;
    # Not an oracle run: recomputes the quality gate's PyTorch reference. See the README.
    pytorch-reference) exec /bin/bash /solution/pytorch_reference.sh ;;
    *)
        echo "unknown INFERENCE_BENCH_ORACLE: ${INFERENCE_BENCH_ORACLE}" >&2
        exit 2
        ;;
esac

python3 -m pip install --no-warn-script-location \
    --extra-index-url https://download.pytorch.org/whl/cu128 \
    --constraint /solution/vllm-constraints.txt "vllm=={vllm_version}"
# vLLM {vllm_version} does not start with the transformers release that upstream's lock pins:
# it reads a tokenizer attribute that transformers 5 removed. Upstream measures its vLLM
# baseline with src/eval/inference/runtime_shims first on PYTHONPATH. The launcher puts the
# task's site-packages directory first, and Python loads only one sitecustomize module, so the
# shims are appended to the one that is already there.
cat /solution/vllm_runtime_shims.py >> /home/agent/task/.local/lib/python3.10/site-packages/sitecustomize.py
cp /solution/start_server.sh /home/agent/task/start_server.sh
chmod +x /home/agent/task/start_server.sh
