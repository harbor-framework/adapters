# The upstream scorer image with the scorer's model checkpoints at /checkpoints.
#
# Upstream mounts the checkpoint store read-only at /checkpoints (harness/runtime/score.py);
# a Harbor verifier image must carry it instead. Build with a checkpoint directory
# filled by the upstream scripts/download_checkpoints.sh (docs/checkpoints.md) as the
# build context:
#
#     docker build -t 4dcb/scorer-checkpoints:dev \
#         -f docker/scorer-checkpoints.Dockerfile /path/to/checkpoints
ARG SCORER_IMAGE=4dcb/scorer:dev
FROM ${SCORER_IMAGE}

COPY . /checkpoints/
