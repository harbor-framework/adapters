FROM node:22.17.0-bookworm-slim AS node
FROM python:3.13-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir aws-cdk-lib==2.198.0 constructs==10.4.2 pytest==8.4.0
RUN pip install --no-cache-dir defusedxml==0.7.1
ENV AWS_EC2_METADATA_DISABLED=true PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/repo
WORKDIR /repo
COPY . /tests/
