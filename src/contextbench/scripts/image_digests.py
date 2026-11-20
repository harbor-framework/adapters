"""Resolve the digests of the images that generated Dockerfiles start from.

Writes src/contextbench/image-digests.json, which maps each image reference
that the agent and verifier Dockerfiles use to the digest of its linux/amd64
manifest. The images are the native image of every valid row of the four
pinned datasets, `GIT_IMAGE` and `VERIFIER_IMAGE`. Generation writes
`name:tag@sha256:...` and refuses an image the file lacks. The file is
rewritten from scratch, so images that no dataset uses drop out.

Each tag is resolved with a manifest HEAD request, which returns the tag's
digest and media type. Docker Hub does not count HEAD requests against its
pull rate limit, and the script prints the `ratelimit-remaining` values that
Docker Hub returned, which stay unchanged. When a tag names a multi-platform
index, the script reads the index to find its linux/amd64 manifest. A Docker
Hub index is read by digest from mirror.gcr.io, and from Docker Hub, where
the request counts as a pull, only when the mirror lacks it. Every index is
checked against its digest.

Usage (from src/contextbench):
    uv run python scripts/image_digests.py
    uv run python scripts/image_digests.py --dataset-path custom.parquet
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contextbench.adapter import (
    DATASETS,
    GIT_IMAGE,
    IMAGE_DIGESTS_PATH,
    VERIFIER_IMAGE,
    download_dataset,
    load_prepared,
)

_INDEX_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
)
_MANIFEST_TYPES = (
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)
_ACCEPT = ", ".join(_INDEX_TYPES + _MANIFEST_TYPES)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_DOCKER_HUB = "registry-1.docker.io"
_MIRROR = "mirror.gcr.io"
_ATTEMPTS = 6


@dataclass(frozen=True)
class Reference:
    registry: str
    repository: str
    tag: str


def parse_reference(reference: str) -> Reference:
    """Split `[registry/]repository:tag` the way Docker resolves it."""
    name, separator, tag = reference.rpartition(":")
    if not separator or "/" in tag or "@" in reference:
        raise ValueError(f"expected a tagged image reference: {reference}")
    first, _, rest = name.partition("/")
    if rest and ("." in first or ":" in first or first == "localhost"):
        registry, repository = first, rest
    else:
        registry, repository = "docker.io", name
    if registry == "docker.io":
        registry = _DOCKER_HUB
        if "/" not in repository:
            repository = f"library/{repository}"
    return Reference(registry, repository, tag)


class Registry:
    """Anonymous manifest requests with bearer-token auth and retries."""

    def __init__(self) -> None:
        self._tokens: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()
        self.counts: Counter[str] = Counter()
        self.docker_hub_remaining: list[str] = []

    def _token(self, challenge: str) -> str:
        fields = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
        query = urllib.parse.urlencode(
            {key: fields[key] for key in ("service", "scope") if key in fields}
        )
        with urllib.request.urlopen(f"{fields['realm']}?{query}", timeout=60) as reply:
            body = json.load(reply)
        return str(body.get("token") or body["access_token"])

    def _send(
        self, method: str, host: str, repository: str, reference: str
    ) -> tuple[dict[str, str], bytes]:
        url = f"https://{host}/v2/{repository}/manifests/{reference}"
        key = (host, repository)
        for attempt in range(_ATTEMPTS):
            headers = {"Accept": _ACCEPT}
            if token := self._tokens.get(key):
                headers["Authorization"] = f"Bearer {token}"
            request = urllib.request.Request(url, method=method, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=60) as reply:
                    with self._lock:
                        self.counts[f"{method} {host}"] += 1
                        if host == _DOCKER_HUB and (
                            remaining := reply.headers.get("ratelimit-remaining")
                        ):
                            self.docker_hub_remaining.append(remaining)
                    response = {
                        name.lower(): value for name, value in reply.headers.items()
                    }
                    return response, reply.read()
            except urllib.error.HTTPError as error:
                challenge = error.headers.get("WWW-Authenticate", "")
                if error.code == 401 and challenge.startswith("Bearer "):
                    self._tokens[key] = self._token(challenge)
                    continue
                if error.code not in {429, 500, 502, 503, 504}:
                    raise
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(min(60, 2**attempt))
        raise RuntimeError(f"{method} {url} failed after {_ATTEMPTS} attempts")

    def head(self, image: Reference) -> tuple[str, str]:
        """Return the tag's digest and media type."""
        headers, _ = self._send("HEAD", image.registry, image.repository, image.tag)
        digest = headers.get("docker-content-digest", "")
        media_type = headers.get("content-type", "").split(";")[0].strip()
        if _DIGEST.fullmatch(digest) is None:
            raise RuntimeError(f"no digest for {image}: {headers}")
        return digest, media_type

    def index(self, image: Reference, digest: str) -> dict[str, Any]:
        """Read an index by digest and check its content against the digest."""
        hosts = [image.registry]
        if image.registry == _DOCKER_HUB:
            hosts.insert(0, _MIRROR)
        for host in hosts:
            try:
                _, body = self._send("GET", host, image.repository, digest)
            except (urllib.error.HTTPError, RuntimeError):
                continue
            if f"sha256:{hashlib.sha256(body).hexdigest()}" == digest:
                return json.loads(body)
        raise RuntimeError(f"could not read index {digest} of {image}")


def amd64_manifest(index: dict[str, Any]) -> str:
    """Return the digest of an index's one linux/amd64 image manifest."""
    candidates = [
        entry
        for entry in index.get("manifests", [])
        if entry.get("platform", {}).get("os") == "linux"
        and entry.get("platform", {}).get("architecture") == "amd64"
        and entry.get("mediaType") in _MANIFEST_TYPES
    ]
    if len(candidates) > 1:
        candidates = [
            entry for entry in candidates if not entry["platform"].get("variant")
        ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one linux/amd64 manifest, found {len(candidates)}"
        )
    return str(candidates[0]["digest"])


def resolve(registry: Registry, reference: str) -> str:
    image = parse_reference(reference)
    digest, media_type = registry.head(image)
    if media_type in _INDEX_TYPES:
        return amd64_manifest(registry.index(image, digest))
    if media_type not in _MANIFEST_TYPES:
        raise RuntimeError(f"unexpected media type {media_type!r} for {reference}")
    return digest


def native_images(dataset_paths: list[Path]) -> set[str]:
    """The native images of every row that generation accepts."""
    return {
        row.native.image
        for path in dataset_paths
        for row in load_prepared(path).prepared.values()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dataset-path",
        type=Path,
        action="append",
        default=[],
        help="Also pin the native images of this local parquet (repeatable).",
    )
    parser.add_argument("--output", type=Path, default=IMAGE_DIGESTS_PATH)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    paths = [download_dataset(spec) for spec in DATASETS.values()] + args.dataset_path
    natives = native_images(paths)
    images = sorted(natives | {GIT_IMAGE, VERIFIER_IMAGE})
    print(f"resolving {len(images)} images ({len(natives)} native)", flush=True)

    registry = Registry()
    digests: dict[str, str] = {}
    failures: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(resolve, registry, image): image for image in images}
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            image = futures[future]
            try:
                digests[image] = future.result()
            except (OSError, RuntimeError, ValueError) as error:
                failures[image] = str(error)
            if done % 100 == 0:
                print(f"{done}/{len(images)}", flush=True)

    print(f"requests: {dict(sorted(registry.counts.items()))}")
    remaining = Counter(registry.docker_hub_remaining)
    print(f"Docker Hub ratelimit-remaining values: {dict(sorted(remaining.items()))}")
    if failures:
        for image, error in sorted(failures.items()):
            print(f"FAILED {image}: {error}")
        raise SystemExit(
            f"{len(failures)} image(s) not resolved; {args.output} unchanged"
        )
    args.output.write_text(
        json.dumps(dict(sorted(digests.items())), indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {len(digests)} digests to {args.output}")


if __name__ == "__main__":
    main()
