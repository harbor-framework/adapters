FROM eclipse-temurin:17-jdk-jammy
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY workspace/ /workspace/
RUN mkdir -p /logs/verifier
