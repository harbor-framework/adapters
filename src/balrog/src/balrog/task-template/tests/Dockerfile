FROM python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370
ENV PYTHONUNBUFFERED=1
# Harbor does not upload tests at runtime when a dedicated verifier image exists.
COPY . /tests/
WORKDIR /tests
