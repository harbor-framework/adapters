"""Report the native images that edit files tracked at the base commit.

Some native images change tracked files while they build, such as a
package.json script or a lockfile. The agent image keeps those edits in the
working tree, as native agents see them, and the collect command leaves them
out of the model patch (task-template/environment/Dockerfile).

For every task of a dataset, this script runs the native image once and
compares its repository with the base commit's tree through a scratch index,
ignoring file modes as the agent image does. It needs Docker. It pulls each
native image it lacks, through mirror.gcr.io when that mirror has a Docker Hub
image and at most 50 an hour from Docker Hub itself, and removes the images it
pulled.

Usage (from src/contextbench):
    uv run python scripts/native_image_edits.py --dataset verified
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

from contextbench.adapter import (
    CONTEXTBENCH_COMMIT,
    DATASETS,
    PreparedRow,
    download_dataset,
    load_prepared,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DOCKER_HUB_PULLS_PER_HOUR = 50
# Runs in the native image: count file-mode changes, then list the content
# changes against the base tree with modes ignored.
PROBE = r"""
cd "$REPOSITORY" 2>/dev/null || { echo NO_REPOSITORY; exit 0; }
g() { git -c safe.directory='*' "$@"; }
g cat-file -e "$BASE^{commit}" 2>/dev/null || { echo NO_BASE_COMMIT; exit 0; }
for mode in true false; do
  GIT_INDEX_FILE=/tmp/probe-$mode g -c core.fileMode=$mode read-tree "$BASE"
  GIT_INDEX_FILE=/tmp/probe-$mode g -c core.fileMode=$mode \
    update-index -q --refresh --ignore-submodules > /dev/null 2>&1
done
echo MODES "$(GIT_INDEX_FILE=/tmp/probe-true g -c core.fileMode=true \
  diff-files --summary --ignore-submodules | grep -c 'mode change')"
echo BEGIN
GIT_INDEX_FILE=/tmp/probe-false g -c core.fileMode=false \
  diff-files --name-status --ignore-submodules
echo END
"""

_hub_lock = threading.Lock()
_hub_pulls: list[float] = []


def _docker(*arguments: str, timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )


def _wait_for_docker_hub() -> None:
    with _hub_lock:
        while True:
            now = time.time()
            _hub_pulls[:] = [pulled for pulled in _hub_pulls if now - pulled < 3600]
            if len(_hub_pulls) < DOCKER_HUB_PULLS_PER_HOUR:
                _hub_pulls.append(now)
                return
            time.sleep(30)


def _pull(image: str) -> tuple[str | None, bool]:
    """Return a local name for the image and whether this call pulled it."""
    names = [image]
    if image.startswith("docker.io/"):
        names.insert(0, "mirror.gcr.io/" + image.removeprefix("docker.io/"))
    for name in names:
        if _docker("image", "inspect", name).returncode == 0:
            return name, False
    for name in names:
        if name.startswith("docker.io/"):
            _wait_for_docker_hub()
        if _docker("pull", "-q", name).returncode == 0:
            return name, True
    return None, False


def _probe(instance_id: str, prepared: PreparedRow) -> dict[str, Any]:
    result: dict[str, Any] = {
        "instance_id": instance_id,
        "source": prepared.source,
        "native_image": prepared.native.image,
    }
    try:
        name, pulled = _pull(prepared.native.image)
    except subprocess.TimeoutExpired:
        name, pulled = None, False
    if name is None:
        return result | {"status": "pull_failed"}
    try:
        run = _docker(
            *("run", "--rm", "--entrypoint", "sh"),
            *("-e", f"REPOSITORY={prepared.native.repository_path}"),
            *("-e", f"BASE={prepared.commit}"),
            *(name, "-c", PROBE),
        )
    except subprocess.TimeoutExpired:
        return result | {"status": "probe_failed", "stderr": "timed out"}
    finally:
        if pulled:
            _docker("image", "rm", name)
    output = run.stdout
    for status in ("NO_REPOSITORY", "NO_BASE_COMMIT"):
        if status in output:
            return result | {"status": status.lower()}
    modes = re.search(r"^MODES (\d+)$", output, re.MULTILINE)
    if modes is None or "BEGIN\n" not in output or "\nEND" not in output:
        return result | {"status": "probe_failed", "stderr": run.stderr[-500:]}
    changes = output.split("BEGIN\n", 1)[1].rsplit("END", 1)[0].splitlines()
    print(f"{instance_id}: {len(changes)} edited files", flush=True)
    return result | {
        "status": "edited" if changes else "unchanged",
        "mode_changes": int(modes[1]),
        "files": len(changes),
        "changes": changes[:20],
    }


def native_image_edits(dataset_name: str, workers: int) -> dict[str, Any]:
    spec = DATASETS[dataset_name]
    prepared = load_prepared(download_dataset(spec)).prepared
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        results = sorted(
            pool.map(lambda item: _probe(*item), prepared.items()),
            key=lambda item: item["instance_id"],
        )
    by_source: dict[str, Counter[str]] = {}
    for item in results:
        counts = by_source.setdefault(item["source"], Counter())
        counts["tasks"] += 1
        counts[item["status"]] += 1
        counts["with_mode_changes"] += item.get("mode_changes", 0) > 0
    return {
        "contextbench_commit": CONTEXTBENCH_COMMIT,
        "dataset": spec.name,
        "dataset_sha256": spec.sha256,
        "description": (
            "Native images whose repository, as the image leaves it, differs "
            "from the base commit in files tracked there: edited content or "
            "deleted files, with file modes ignored."
        ),
        "adapter_handling": (
            "The agent image keeps these edits in the working tree, with HEAD "
            "and the index at the base commit, and records the tree it leaves "
            "as the model patch's baseline, so the patch holds only the agent's "
            "changes. Git ignores file modes in the agent image, so mode-only "
            "changes (`with_mode_changes`) do not show as edits."
        ),
        "counts_by_source": {
            source: dict(sorted(counts.items()))
            for source, counts in sorted(by_source.items())
        },
        "edited": [item for item in results if item["status"] == "edited"],
        "with_mode_changes": [
            item["instance_id"] for item in results if item.get("mode_changes")
        ],
        "not_probed": [
            item for item in results if item["status"] not in {"edited", "unchanged"}
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="verified")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    report = native_image_edits(args.dataset, args.workers)
    output = args.output or OUTPUT_DIR / f"native-image-edits-{args.dataset}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['counts_by_source']}; wrote {output}")


if __name__ == "__main__":
    main()
