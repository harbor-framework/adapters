FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
RUN pip install --no-cache-dir numpy==1.26.4
COPY . /tests/
ENV PYTHONPATH=/tests
WORKDIR /workspace
