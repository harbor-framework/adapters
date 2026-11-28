# Original-side parity runner: upstream sec-code-bench (patched) + pinned Codex CLI.
# Upstream e2e runs the CLI on the host; this image keeps that untrusted code in a container.
FROM golang:1.25.5-bookworm AS go

FROM python:3.12-slim-bookworm
ARG CODEX_VERSION
# Give the agent the same toolchains the Harbor task images put in its sandbox (JDK 17 + maven,
# gcc/cmake, Go 1.25.5, jq/ping; Node 22 comes with the Codex install below), so neither side's
# agent can compile/run tests the other cannot.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates git ripgrep \
      openjdk-17-jdk-headless maven build-essential cmake gcc-multilib jq iputils-ping \
 && rm -rf /var/lib/apt/lists/*
COPY --from=go /usr/local/go /usr/local/go
ENV GOTOOLCHAIN=local PATH=/usr/local/go/bin:$PATH
RUN useradd -m runner
USER runner
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# same installer and version pin as Harbor's codex agent (nvm v0.40.2, node 22, npm @openai/codex@<version>)
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash \
 && export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" \
 && nvm install 22 && nvm alias default 22 \
 && npm install -g "@openai/codex@${CODEX_VERSION}" \
 && ln -s "$(dirname "$(nvm which 22)")" "$HOME/node-bin" \
 && codex --version
ENV PATH=/home/runner/node-bin:$PATH
COPY --chown=runner:runner sec-code-bench /home/runner/sec-code-bench
# upstream runs via `uv sync` (no build-system: the repo itself is not installed). Install the
# declared [project].dependencies + the dev group (`uv sync` default) from PyPI and run `python -m sec_code_bench.e2e` from the repo root.
RUN cd /home/runner/sec-code-bench \
 && python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print('\n'.join(d['project']['dependencies'] + d.get('dependency-groups', {}).get('dev', [])))" > /tmp/req.txt \
 && pip install --user --no-cache-dir -r /tmp/req.txt
WORKDIR /home/runner/sec-code-bench
