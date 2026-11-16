# Seed only, never shipped: each family builder under `asta_bench.benchmarks`
# writes the task's Dockerfile (the Inspect bridge dataset adds the bridge
# runtime layer).
FROM python:3.12-slim

WORKDIR /app

COPY workspace/inspect_config.json /app/inspect_config.json
