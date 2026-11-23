# Agent container: the tools an SREGym agent container provides (kubectl,
# helm, curl, jq, python3), without any SREGym code or problem definitions.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget git jq python3 python3-pip python3-venv \
        less vim-tiny procps iputils-ping dnsutils netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

ARG KUBECTL_VERSION=v1.32.1
ARG HELM_VERSION=v4.0.0
RUN set -eu; arch="$(dpkg --print-architecture)"; \
    curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${arch}/kubectl" -o /usr/local/bin/kubectl; \
    chmod +x /usr/local/bin/kubectl; \
    curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-${arch}.tar.gz" | tar -xz -C /tmp; \
    mv "/tmp/linux-${arch}/helm" /usr/local/bin/helm; rm -rf "/tmp/linux-${arch}"

# The agent runs as this unprivileged user ([agent].user in task.toml), so it
# cannot replace the tools the verifier runs as root.
RUN useradd -m -s /bin/bash agent && mkdir -p /workspace && chown agent:agent /workspace

WORKDIR /workspace
