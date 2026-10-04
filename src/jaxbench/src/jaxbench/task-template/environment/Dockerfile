FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# JAX with TPU support (pulls the matching libtpu wheel).
RUN pip install --no-cache-dir "jax[tpu]" numpy

WORKDIR /workspace
COPY workspace/ /workspace/
