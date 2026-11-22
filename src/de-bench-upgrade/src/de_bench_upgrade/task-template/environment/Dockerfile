# Scoring-only validation image. Does NOT reproduce upstream agent tooling.
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir PyYAML==6.0.4 packaging==26.3
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /work
COPY workspace/ /work/
COPY bootstrap.py add-excludes.json /tmp/
RUN python /tmp/bootstrap.py && rm /tmp/bootstrap.py
