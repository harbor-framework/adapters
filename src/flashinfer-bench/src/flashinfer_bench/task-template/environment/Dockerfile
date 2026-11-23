FROM pytorch/pytorch:2.8.0-cuda12.9-cudnn9-devel@sha256:cf5aa3f7045a68c10d80f546746591c5ccae6a33729e5e32625ff76bd2c036fe
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git init /opt/flashinfer-bench && cd /opt/flashinfer-bench \
    && git remote add origin https://github.com/flashinfer-ai/flashinfer-bench.git \
    && git fetch --depth 1 origin @@UPSTREAM_REVISION@@ \
    && git checkout --detach FETCH_HEAD \
    && git submodule update --init --recursive
# Editable install retains bundled eval_config.yaml, which upstream's wheel does not declare.
RUN pip install --no-cache-dir 'flashinfer-python==0.6.4' 'openai==3.50.0' \
    'pydantic==2.14.3' 'safetensors==0.6.2' 'apache-tvm-ffi==0.1.6' \
    'docstring-parser==0.16' 'pyyaml==6.0.3' \
    && pip install --no-deps -e /opt/flashinfer-bench
WORKDIR /workspace
COPY data /workspace/data
COPY manifest.json /workspace/manifest.json
COPY runtime /opt/adapter-runtime
# Inputs are pinned and hydrated before the agent starts; no private services needed.
RUN python /opt/adapter-runtime/assets.py /workspace/data /workspace/manifest.json /tmp/flashinfer-tensors
