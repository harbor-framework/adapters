# Verifier image for an MLOps-Bench task.
#
# The verifier runs in this dedicated container (`environment_mode =
# "separate"` in task.toml), never in the agent's container. Its only input
# from the agent is the /workspace artifact Harbor collects after the agent
# phase. The scoring tests (test_f2p.py, test_p2p.py), test.sh and the pinned
# pytest are baked in here, so nothing the agent did can change them.
#
# Same pinned base image and hash-locked pytest as the agent environment.
FROM python:3.11.18-slim-trixie@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-deps --require-hashes -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# This image owns /tests/ (test.sh, test_f2p.py, test_p2p.py).
COPY . /tests/
RUN rm -f /tests/Dockerfile /tests/requirements.txt \
    && chmod +x /tests/test.sh
