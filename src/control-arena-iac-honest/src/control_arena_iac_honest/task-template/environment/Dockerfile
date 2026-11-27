FROM node:22.17.0-bookworm-slim AS node
FROM python:3.13-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir aws-cdk-lib==2.198.0 constructs==10.4.2 pytest==8.4.0
ENV AWS_EC2_METADATA_DISABLED=true PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/repo
WORKDIR /repo
COPY repo/ /repo/
COPY cdk_inspect.py /usr/local/lib/cdk_inspect.py
RUN chmod 755 /usr/local/lib/cdk_inspect.py \
    && ln -s /usr/local/lib/cdk_inspect.py /usr/local/bin/cdk_ls \
    && ln -s /usr/local/lib/cdk_inspect.py /usr/local/bin/cdk_synth
