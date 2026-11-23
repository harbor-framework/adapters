FROM python:3.12-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN pip install --no-cache-dir numpy==2.1.3
WORKDIR /workspace
COPY workspace/ /workspace/
RUN mkdir -p /logs/verifier
