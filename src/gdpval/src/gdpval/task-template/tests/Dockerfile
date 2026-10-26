FROM public.ecr.aws/docker/library/python:3.11-slim

# This build context is tests/, never environment/ or the agent filesystem.
WORKDIR /workspace
RUN apt-get update && apt-get install -y --no-install-recommends iptables && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "litellm>=1.80.8" "pypdf>=6.4.1"
WORKDIR /tests
COPY . /tests/
RUN mkdir -p /app /logs/verifier
CMD ["sleep", "infinity"]
