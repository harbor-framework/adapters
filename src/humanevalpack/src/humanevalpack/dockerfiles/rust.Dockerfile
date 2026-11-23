FROM rust:1.83-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
# Same dependencies as the upstream evaluator's Cargo.toml; prebuilt so that
# agent and verifier builds are fast and work offline.
ENV CARGO_TARGET_DIR=/opt/humanevalpack/rust-target
COPY workspace/Cargo.toml /opt/humanevalpack/rust/Cargo.toml
RUN cd /opt/humanevalpack/rust && mkdir src && echo 'fn main(){}' > src/main.rs \
    && cargo generate-lockfile && cargo build && cargo test --no-run \
    && rm -rf src
WORKDIR /workspace
COPY workspace/ /workspace/
RUN cp /opt/humanevalpack/rust/Cargo.lock /workspace/Cargo.lock && mkdir -p /logs/verifier
