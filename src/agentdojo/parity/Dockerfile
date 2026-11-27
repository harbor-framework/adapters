FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm ca-certificates git \
    && npm install -g @openai/codex@0.118.0 \
    && rm -rf /var/lib/apt/lists/*
