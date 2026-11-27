FROM python:3.13-slim-bookworm
WORKDIR /workspace
COPY accounting.json /workspace/accounting.json
COPY submit /usr/local/bin/submit
RUN chmod 755 /usr/local/bin/submit
