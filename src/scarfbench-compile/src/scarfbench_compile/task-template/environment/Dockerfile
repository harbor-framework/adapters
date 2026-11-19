FROM maven:3.9.12-ibm-semeru-21-noble

USER root

# Toolchain for the docker-free verifier (tests/test.sh):
#   curl        — HTTP health probe
#   jq          — reward.json assembly
#   python3/pip — smoke tests (pytest)
#   unzip       — inspect jar manifests to find the runnable Spring Boot jar
#   iproute2/net-tools/lsof — discover the port the booted app is listening on
#   git/make/uuid-runtime — general build convenience
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    jq \
    make \
    python3 \
    python3-pip \
    unzip \
    iproute2 \
    net-tools \
    lsof \
    uuid-runtime \
    ca-certificates \
    postgresql \
    postgresql-client \
    && pip3 install --break-system-packages pytest requests 2>/dev/null || pip3 install pytest requests \
    && rm -rf /var/lib/apt/lists/*

# Install uv for running smoke tests with pyproject.toml dependencies.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:/root/.local/bin:$PATH"

# Pre-install Playwright browsers so smoke tests run without network access at
# test time. playwright and pytest-playwright are installed via uv at test time
# from each task's smoke/pyproject.toml, but the browser binaries must be
# pre-baked into the image (they are not installed by uv).
# Pin to the same version as tests/smoke/uv.lock so the binary path matches.
# Install chromium system deps explicitly first (--with-deps can silently fail
# inside a minimal image, causing SIGSEGV at browser launch).
RUN apt-get update && apt-get install -y --no-install-recommends \
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
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages playwright==1.58.0 && playwright install chromium

# ActiveMQ Artemis broker — required by cargotracker/quarkus (JMS messaging).
# Installed here so the image is self-contained; fw_prepare() in
# tests-quarkus/framework.sh starts the broker only when the app needs it.
# Version must match the eval-harness Dockerfile (ARTEMIS_VERSION=2.31.2).
ENV ARTEMIS_VERSION=2.31.2
ENV ARTEMIS_HOME=/opt/artemis
RUN mkdir -p ${ARTEMIS_HOME} /var/lib/artemis-broker && \
    curl -fsSL -o /tmp/artemis.tar.gz \
        "https://archive.apache.org/dist/activemq/activemq-artemis/${ARTEMIS_VERSION}/apache-artemis-${ARTEMIS_VERSION}-bin.tar.gz" && \
    tar xzf /tmp/artemis.tar.gz -C ${ARTEMIS_HOME} --strip-components=1 && \
    rm /tmp/artemis.tar.gz && \
    ${ARTEMIS_HOME}/bin/artemis create /var/lib/artemis-broker \
        --user quarkus --password quarkus --allow-anonymous --no-web --silent

# Gradle-only Spring reference apps ship an older wrapper that cannot run on the
# base image's JDK 21; the verifier builds those under JDK 11. Maven builds keep
# using the image's JDK 21.
COPY --from=eclipse-temurin:11-jdk /opt/java/openjdk /opt/java/openjdk-11

# Pre-configure Maven mirror to avoid 429 rate-limiting from repo.maven.apache.org
COPY settings.xml /root/.m2/settings.xml

WORKDIR /app

# Copy the source application into the container.
# The agent's job is to migrate this to the target framework.
COPY app/ /app/
