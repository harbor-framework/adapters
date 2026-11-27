FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends jq \
    && rm -rf /var/lib/apt/lists/*

# LLM judge client used by run_test.py
RUN pip install --no-cache-dir litellm==1.83.14

WORKDIR /workspace

# Separate-verifier images must bundle the tests (Harbor does not upload them).
COPY . /tests/
