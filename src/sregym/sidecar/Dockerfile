# SREGym backend sidecar for Harbor tasks.
#
# Base: SREGym's upstream Docker-in-Docker runtime (docker/dind/Dockerfile),
# built from a pinned SREGym commit. It owns a private dockerd and a 4-node
# KIND/Calico cluster. Its entrypoint must be preserved: it prepares cgroups,
# starts dockerd, creates the cluster, then execs CMD.
#
# Build (see README, "Usage: Create Task Directories"):
#   git clone --recurse-submodules https://github.com/SREGym/SREGym && cd SREGym
#   git checkout <commit> && git submodule update --init --recursive
#   docker buildx build --load -t sregym-dind:<commit> -f docker/dind/Dockerfile .
#   docker build --build-arg SREGYM_DIND_IMAGE=sregym-dind:<commit> \
#       -t sregym-harbor-sidecar:<commit> <this directory>
ARG SREGYM_DIND_IMAGE=sregym-dind:local
FROM ${SREGYM_DIND_IMAGE}

# Fixes for upstream SREGym bugs found by the oracle runs, applied to the
# pinned checkout. Each patch documents its reason; see README "Upstream fixes".
COPY patches/ /opt/harbor/patches/
RUN for p in /opt/harbor/patches/*.patch; do patch -p1 -d /opt/sregym --forward < "$p" || exit 1; done

COPY bridge.py /opt/harbor/bridge.py
COPY healthcheck.sh /opt/harbor/healthcheck.sh
RUN chmod +x /opt/harbor/healthcheck.sh

# The DinD image's ENTRYPOINT (tini -> docker/dind/entrypoint.sh) runs this
# once the cluster is ready. PATH already includes SREGym's virtualenv.
CMD ["python", "/opt/harbor/bridge.py"]
