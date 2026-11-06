FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Judge client used by the verifier (tests/evaluate.py).
RUN pip install --no-cache-dir "litellm==1.77.7"
