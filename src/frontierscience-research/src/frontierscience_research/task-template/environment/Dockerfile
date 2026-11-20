FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends bash coreutils curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN mkdir -p /logs/agent /logs/verifier
