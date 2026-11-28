# BrickBench separate GPU verifier image:
# - Physical verification: brickagent@b3df55e3 + bricknet==0.1.1 + pybullet==3.2.7
# - Rendering: bricknet-render==0.1.0 + bpy>=5.1 (requires Python 3.13)
# - VQA Judge: google/gemma-4-31B-it @ 842da3794eaa0b77d5f08bae87a17459d91ff475
FROM python:3.13-slim-trixie

ARG BRICKAGENT_COMMIT="b3df55e36c669b22ef089b13db1ee841907d09b3"
ARG BRICKNET_VERSION="0.1.1"
ARG BRICKNET_RENDER_VERSION="0.1.0"
ARG COLLIDER_URL="https://keeper.mpdl.mpg.de/seafhttp/f/24c17eb2d4d14c7ebd41/?op=view"
ARG GLB_URL="https://keeper.mpdl.mpg.de/seafhttp/f/737aee1bec9849849791/"
ARG GLB_SHA256="4bbc99fec48914e24fa06547a4586cc9a1f479280f8c1f5822385d24337c1dd0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 \
    BRICKNET_DATA=/opt/bricknet \
    BRICKNET_CATALOG=v1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates curl xz-utils \
        libstdc++6 libgomp1 libgl1 libegl1 libgles2 \
        libx11-6 libxxf86vm1 libxfixes3 libxi6 libxkbcommon0 libsm6 libxrender1 \
    && python -m pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cu128 \
        torch torchvision \
    && python -m pip install --no-cache-dir \
        "bricknet==${BRICKNET_VERSION}" \
        "pybullet==3.2.7" \
        numpy scipy pillow \
        "bricknet-render==${BRICKNET_RENDER_VERSION}" \
        "bpy>=5.1" \
        "transformers>=5.5.0" accelerate \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/bricknet/cvx /opt/bricknet/glb /opt/brickagent \
    && curl -4 -fsSL --retry 5 --retry-all-errors --connect-timeout 20 --speed-time 30 --speed-limit 10000 \
        "$COLLIDER_URL" -o /tmp/cvx.tar.xz \
    && tar -xJf /tmp/cvx.tar.xz -C /opt/bricknet/cvx \
    && rm -f /tmp/cvx.tar.xz \
    && curl -4 -fsSL --retry 5 --retry-all-errors --connect-timeout 20 --speed-time 30 --speed-limit 10000 \
        "$GLB_URL" -o /tmp/glb.tar.xz \
    && echo "${GLB_SHA256}  /tmp/glb.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/glb.tar.xz -C /opt/bricknet/glb \
    && rm -f /tmp/glb.tar.xz \
    && curl -fsSL --retry 5 --retry-all-errors --connect-timeout 20 --speed-time 30 --speed-limit 10000 \
        "https://codeload.github.com/kulits/BrickAgent/tar.gz/${BRICKAGENT_COMMIT}" \
        | tar -xz -C /opt/brickagent --strip-components=3 "BrickAgent-${BRICKAGENT_COMMIT}/src/brickagent" \
    && echo /opt > "$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')/brickagent.pth" \
    && chmod -R a+rX /opt/bricknet /opt/brickagent \
    && useradd -m -s /bin/bash builder

COPY . /tests/
RUN chmod -R a+rX /tests && chmod +x /tests/test.sh

WORKDIR /tests
