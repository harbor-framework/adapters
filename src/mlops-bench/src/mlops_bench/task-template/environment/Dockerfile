# Agent environment for an MLOps-Bench task.
#
# Base image pinned by digest (python:3.11.18-slim-trixie). Python packages are
# pinned and hash-locked in requirements.txt; git is pinned to the trixie
# package version.
FROM python:3.11.18-slim-trixie@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

# Skip "recommended" packages in every apt install, including the ones CLI
# agents run at setup time (e.g. Claude Code's curl/nodejs/npm/procps: 352 MB
# instead of 1.02 GB). Tasks are stdlib-only and never use apt.
RUN echo 'APT::Install-Recommends "false";' > /etc/apt/apt.conf.d/99-no-install-recommends

RUN apt-get update \
    && apt-get install -y --no-install-recommends git=1:2.47.3-0+deb13u1 \
    && rm -rf /var/lib/apt/lists/*

# pytest is the benchmark's only evaluation dependency (tasks are stdlib-only).
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-deps --require-hashes -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

WORKDIR /workspace

# Only the editable starting workspace (`repo/`) is copied in. The upstream
# oracle/, buggy/, expected_changes.patch, metadata.json and the F2P/P2P tests
# are never placed in the agent environment.
COPY repo/ /workspace/

RUN git init -q \
    && git add -A \
    && git -c user.name=mlops-bench -c user.email=mlops-bench@localhost commit -q -m "MLOps-Bench starting workspace"
