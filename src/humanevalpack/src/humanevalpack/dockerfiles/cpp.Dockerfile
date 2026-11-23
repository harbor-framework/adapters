FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
# boost/any.hpp is in the upstream include helper; -lcrypto/-lssl are used by CPP/162
RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ libboost-dev libssl-dev python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY workspace/ /workspace/
RUN mkdir -p /logs/verifier
