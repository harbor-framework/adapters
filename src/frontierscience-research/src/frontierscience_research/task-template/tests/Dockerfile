# Verifier image: the LLM judge runs here, in a container separate from the agent's.
# The agent's /workspace/answer.md arrives as an artifact (see task.toml).
FROM python:3.12-slim

RUN pip install --no-cache-dir "anthropic==2.8.0"

WORKDIR /workspace

COPY . /tests/
RUN chmod +x /tests/test.sh && mkdir -p /logs/verifier
