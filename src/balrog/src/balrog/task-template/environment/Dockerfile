FROM python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370
COPY requirements-agent.lock /opt/requirements-agent.lock
RUN python -m pip install --no-cache-dir -r /opt/requirements-agent.lock
COPY vendor/balrog.tar.gz /tmp/balrog.tar.gz
# Only agent/prompt/client code enters this container; game state and oracle do not.
RUN mkdir -p /opt/balrog \
    && tar -xzf /tmp/balrog.tar.gz -C /opt/balrog \
       LICENSE balrog/__init__.py balrog/agents balrog/client.py \
       balrog/prompt_builder balrog/config/config.yaml \
    && rm /tmp/balrog.tar.gz
RUN useradd --create-home --uid 1000 agent \
    && mkdir -p /app /logs/agent /logs/verifier \
    && chown agent:agent /app /logs/agent
COPY play.py /usr/local/lib/balrog/play.py
RUN printf '#!/bin/sh\nexec /usr/local/bin/python3 -I /usr/local/lib/balrog/play.py "$@"\n' > /usr/local/bin/balrog \
    && chmod 755 /usr/local/bin/balrog
ENV BALROG_SERVER=http://game:8080 PYTHONPATH=/opt/balrog PYTHONUNBUFFERED=1
WORKDIR /app
