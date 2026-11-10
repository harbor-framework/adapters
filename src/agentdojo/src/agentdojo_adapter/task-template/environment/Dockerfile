FROM python:3.12-slim

WORKDIR /app

# MCP client for the oracle solution. The suite tools and data live in the
# agentdojo-runtime sidecar, not in this container.
RUN pip install --no-cache-dir "fastmcp==4.0.11"
