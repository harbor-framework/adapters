FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Verifier dependencies (tests/evaluate.py): the official DRACO grader library,
# pinned to the commit whose default judge prompt matches the paper's Appendix
# C.5, and LiteLLM as the judge client.
RUN pip install --no-cache-dir \
        "litellm==1.103.4" \
        "https://github.com/paper-instruments/rubric/archive/eb0755a1c4682cd20c490550bd6260ccea8bafe0.tar.gz"
