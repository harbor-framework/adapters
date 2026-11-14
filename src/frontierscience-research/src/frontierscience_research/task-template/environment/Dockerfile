FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends bash coreutils curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Anthropic SDK for the LLM judge in tests/grader.py
RUN pip install --no-cache-dir "anthropic==2.8.0"

WORKDIR /workspace

RUN mkdir -p /logs/agent /logs/verifier
