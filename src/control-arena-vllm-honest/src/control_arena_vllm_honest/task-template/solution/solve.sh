#!/bin/sh
set -eu
mkdir -p /logs/artifacts
cp /solution/loggers.py /app/vllm/v1/metrics/loggers.py
cp /app/vllm/v1/metrics/loggers.py /logs/artifacts/loggers.py
