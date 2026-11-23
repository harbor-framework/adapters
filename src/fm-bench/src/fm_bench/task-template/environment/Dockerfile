# The agent container. It has the rulebook, the tool schemas and a thin HTTP
# client; the engine, the seed and the world live in the `game` sidecar.
FROM python:3.11.7-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git tmux \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /logs && chmod -R 777 /logs

COPY fm.py /app/fm.py
COPY tools.json /app/tools.json
COPY rules.md /app/rules.md
RUN printf '#!/bin/sh\nexec python3 /app/fm.py "$@"\n' > /usr/local/bin/fm \
    && chmod 755 /usr/local/bin/fm /app/fm.py

ENV FM_SERVER=http://game:8080
