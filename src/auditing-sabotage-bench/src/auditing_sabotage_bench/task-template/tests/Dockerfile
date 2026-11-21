# Verifier image: grades /workspace/audit_report.txt (transferred as an artifact).
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

RUN pip install --no-cache-dir openai==3.50.0

COPY . /tests/
WORKDIR /tests
