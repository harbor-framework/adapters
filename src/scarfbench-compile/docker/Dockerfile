# ScarfBench agent + verifier toolchain image.
#
# Build once, push to a registry, and point all 200+ tasks at it via
# docker_image = "..." in task.toml.  The image contains NO smoke tests or
# verifier logic — those stay private inside each task's tests/ bundle.
# This image is therefore safe to push to a public registry.
#
# Build and push to ghcr.io/scarfbench/scarfbench-base with:
#   ./build-and-push.sh <TAG>

FROM maven:3.9.12-ibm-semeru-21-noble

USER root

# Single apt layer: build tools + Python + Playwright system deps + PostgreSQL
# client (used by some smoke suites).  Merging both RUN apt-get blocks from the
# per-task Dockerfile cuts ~200 MB from the layer graph and halves pull time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # HTTP / JSON / archive utilities (verifier)
    curl \
    jq \
    unzip \
    ca-certificates \
    # Build convenience
    git \
    make \
    uuid-runtime \
    # Python smoke-test runner
    python3 \
    python3-pip \
    # Port-discovery for deploy wait
    iproute2 \
    net-tools \
    lsof \
    # Database clients (some smoke suites seed data via psql)
    postgresql \
    postgresql-client \
    # Chromium / Playwright system dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2t64 \
    libpango-1.0-0 \
    libcairo2 \
    && pip3 install --break-system-packages pytest requests 2>/dev/null || pip3 install pytest requests \
    && rm -rf /var/lib/apt/lists/*

# uv — fast Python package manager used by smoke suites with pyproject.toml.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:/root/.local/bin:$PATH"

# Playwright Chromium — pre-baked so smoke tests run without network access at
# test time.  Pin to the same version as tests/smoke/uv.lock.
RUN pip3 install --break-system-packages playwright==1.58.0 && playwright install chromium

# ActiveMQ Artemis — required by cargotracker/quarkus (JMS messaging).
# fw_prepare() in framework.sh starts the broker only when the app needs it;
# it is a no-op for apps that don't use JMS.
ENV ARTEMIS_VERSION=2.31.2
ENV ARTEMIS_HOME=/opt/artemis
RUN mkdir -p ${ARTEMIS_HOME} /var/lib/artemis-broker && \
    curl -fsSL -o /tmp/artemis.tar.gz \
        "https://archive.apache.org/dist/activemq/activemq-artemis/${ARTEMIS_VERSION}/apache-artemis-${ARTEMIS_VERSION}-bin.tar.gz" && \
    tar xzf /tmp/artemis.tar.gz -C ${ARTEMIS_HOME} --strip-components=1 && \
    rm /tmp/artemis.tar.gz && \
    ${ARTEMIS_HOME}/bin/artemis create /var/lib/artemis-broker \
        --user quarkus --password quarkus --allow-anonymous --no-web --silent

# JDK 11 — Gradle-wrapped Spring reference apps ship an older wrapper that
# cannot run on JDK 21.  Maven builds keep using the image's JDK 21.
COPY --from=eclipse-temurin:11-jdk /opt/java/openjdk /opt/java/openjdk-11

# Maven mirror: avoids 429 rate-limiting from repo.maven.apache.org.  Tasks that
# set docker_image skip environment/Dockerfile, so the agent environment gets
# this from the image.  Keep in sync with SETTINGS_XML in src/scarfbench_compile/adapter.py.
COPY settings.xml /root/.m2/settings.xml

WORKDIR /app
