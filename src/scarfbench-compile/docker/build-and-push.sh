#!/usr/bin/env bash
# Build the ScarfBench toolchain image and push it to GitHub Container Registry.
#
# Usage:
#   ./build-and-push.sh [TAG]
#
# TAG defaults to "latest". Prefer a dated/versioned tag (e.g. 2026-10-09) and
# pin tasks to it so results stay reproducible.
#
# The resulting image URL is what goes into task.toml:
#   docker_image = "ghcr.io/scarfbench/scarfbench-base:<TAG>"
#
# Override the repository with SCARFBENCH_IMAGE_REPO (e.g. to push to a fork).
#
# Prerequisites:
#   A GitHub personal access token (classic) with the write:packages scope, from
#   an account that can publish packages in the scarfbench org:
#     echo "$GHCR_TOKEN" | docker login ghcr.io -u <github-username> --password-stdin
#
# The image contains only the build toolchain — no smoke tests, no verifier
# scripts — so it is safe to host publicly.

set -euo pipefail

TAG="${1:-${SCARFBENCH_IMAGE_TAG:-latest}}"
IMAGE_REPO="${SCARFBENCH_IMAGE_REPO:-ghcr.io/scarfbench/scarfbench-base}"

FULL_IMAGE="${IMAGE_REPO}:${TAG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Building ScarfBench toolchain image (linux/amd64)..."
docker build \
    --platform linux/amd64 \
    --tag "scarfbench-base:${TAG}" \
    "${SCRIPT_DIR}"

echo "==> Tagging as ${FULL_IMAGE}..."
docker tag "scarfbench-base:${TAG}" "${FULL_IMAGE}"

echo "==> Pushing ${FULL_IMAGE}..."
docker push "${FULL_IMAGE}"

echo ""
echo "Done. Add this to your adapter invocation:"
echo ""
echo "    --docker-image \"${FULL_IMAGE}\""
echo ""
echo "Or set the environment variable:"
echo ""
echo "    export SCARFBENCH_DOCKER_IMAGE=\"${FULL_IMAGE}\""
echo ""
echo "And regenerate tasks with:"
echo ""
echo "    uv run scarfbench-compile --docker-image \"${FULL_IMAGE}\""
