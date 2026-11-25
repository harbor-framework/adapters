FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates bubblewrap && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==1.26.4 Pillow==11.3.0 PyYAML==6.0.2 jsonschema==4.25.1
# Keep the model loop unchanged and fixed to the same source revision on both sides.
RUN git clone --filter=blob:none --no-checkout https://github.com/embodied-agent-arena/embodied-agent-arena.git /opt/arena && cd /opt/arena && git sparse-checkout set src scripts runtimes/pukun/scripts runtimes/pukun/HumanCLAWBenchmark/openhands_adapter && git checkout ${arena_commit}
ENV PYTHONPATH=/opt/arena/src
ENV EMBODIED_ARENA_ROOT=/opt/arena
ENV ARENA_CASE_STUDY_HZ=0
WORKDIR /workspace
COPY data/ /workspace/data/
COPY frames/ /workspace/frames/
COPY public-task.json /workspace/public-task.json
COPY run_public.py /opt/geoprobe/run_public.py
