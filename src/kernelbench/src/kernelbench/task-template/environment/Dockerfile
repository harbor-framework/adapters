FROM docker.io/pytorch/pytorch:2.9.1-cuda12.8-cudnn9-devel

RUN apt-get update && apt-get install -y --no-install-recommends git tmux asciinema \
    && rm -rf /var/lib/apt/lists/*

# Runtime deps of the upstream eval modules (their package __init__ also pulls in the
# LLM SDK clients, which the eval never calls).
RUN pip install --no-cache-dir \
    pydantic==2.14.3 python-dotenv==1.2.4 tqdm==4.67.1 tomli==2.5.0 einops==0.8.2 \
    ninja==1.13.0 requests==2.32.5 packaging==25.0 numpy==2.3.4 transformers==5.23.0 \
    openai==3.51.0 litellm==1.109.1 together==3.1.1 google-genai==3.3.0 anthropic==2.8.0

# Upstream graders, pinned. Hidden test inputs are not part of the image; the
# verifier ships them in /tests.
RUN git init -q /opt/KernelBench && cd /opt/KernelBench \
    && git fetch -q --depth 1 {kb_repo} {kb_rev} && git checkout -q FETCH_HEAD && rm -rf .git
RUN git init -q /opt/kbv && cd /opt/kbv \
    && git fetch -q --depth 1 {kbv_repo} {kbv_rev} && git checkout -q FETCH_HEAD \
    && rm -rf .git hidden_tests stripped_prompts *.pdf

# Upstream bug (both repos): _process_input_tensor casts every input tensor to the
# eval precision, turning int64 class labels into floats, so e.g. L1-95
# CrossEntropyLoss fails even for the reference. Cast floating tensors only.
RUN sed -i 's/^    input_tensor = input.to(dtype=precision)$/    input_tensor = input.to(dtype=precision) if input.is_floating_point() else input/' \
      /opt/KernelBench/src/kernelbench/eval.py /opt/kbv/src/eval.py \
    && test "$(grep -l 'if input.is_floating_point() else input' /opt/KernelBench/src/kernelbench/eval.py /opt/kbv/src/eval.py | wc -l)" = 2

ENV PYTHONPATH=/opt/KernelBench/src MAX_JOBS=16 LITELLM_LOCAL_MODEL_COST_MAP=True
WORKDIR /workspace
COPY {copies} /workspace/
