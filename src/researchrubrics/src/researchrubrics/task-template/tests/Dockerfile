# Verifier image. The verifier runs in its own container, so the agent never
# sees the rubrics, the judge prompts or the judge client.
FROM python:3.12-slim

RUN pip install --no-cache-dir "litellm==1.77.7"

COPY . /tests/
