FROM python:3.13-slim

WORKDIR /tests

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "inspect_ai=={inspect_ai_version}" "inspect_petri @ git+https://github.com/meridianlabs-ai/inspect_petri.git@{inspect_petri_revision}"

COPY . /tests/
