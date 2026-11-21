FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        build-essential \
        ripgrep \
    && rm -rf /var/lib/apt/lists/*

# The codebases ship uv/poetry lockfiles; the auditor may install them to run code.
RUN pip install --no-cache-dir uv==0.11.32

# The paper (PAPER.md), README, CLAUDE.md context and codebase under audit.
COPY workspace/ /workspace/

# Upstream SingleAgentStrategy.setup(): audit journal and background-job helper.
COPY audit/ /workspace/.audit/
RUN mkdir -p /workspace/.jobs && chmod +x /workspace/.audit/start_job.sh

WORKDIR /workspace
