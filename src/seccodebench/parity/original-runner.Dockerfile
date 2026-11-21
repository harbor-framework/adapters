# Original-side parity runner: upstream sec-code-bench (patched) + pinned Claude Code CLI.
# Upstream e2e runs the CLI on the host; this image keeps that untrusted code in a container.
FROM python:3.12-slim-bookworm
ARG CLAUDE_CODE_VERSION
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates git \
 && rm -rf /var/lib/apt/lists/*
RUN useradd -m runner
USER runner
# same installer and version pin as Harbor's claude-code agent (install.sh -- <version>)
RUN curl -fsSL https://claude.ai/install.sh | bash -s -- "${CLAUDE_CODE_VERSION}"
ENV PATH=/home/runner/.local/bin:$PATH
COPY --chown=runner:runner sec-code-bench /home/runner/sec-code-bench
# upstream runs via `uv sync` (no build-system: the repo itself is not installed). Install the
# declared [project].dependencies + the dev group (`uv sync` default) from PyPI and run `python -m sec_code_bench.e2e` from the repo root.
RUN cd /home/runner/sec-code-bench \
 && python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print('\n'.join(d['project']['dependencies'] + d.get('dependency-groups', {}).get('dev', [])))" > /tmp/req.txt \
 && pip install --user --no-cache-dir -r /tmp/req.txt
WORKDIR /home/runner/sec-code-bench
