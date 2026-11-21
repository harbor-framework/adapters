"""Fill the model caches with the pinned revision. Runs as root.

In the agent's sandbox, the healthcheck runs it with --record once, before the agent starts. The
agent's cache gets the whole repository, as in the original benchmark, and refs/main names the
pinned revision, so that a lookup of the model by name finds it without the network. The record,
which only root can read, lists the files that the download wrote, so that collect.sh can leave
those that the agent did not change out of the hand-off to the verifier.

In the verifier's sandbox, test.sh runs it with --evaluator and the Hub's cache variables set to a
staging directory: the whole repository goes there, and the files that the hand-off left out are
put back from it. A second cache, which only root can write, gets the tokenizer and configuration
files that the final evaluation builds its requests from.
"""

import argparse
import json
import os
from pathlib import Path

import huggingface_hub

EVAL_HUB = "/opt/ib_eval_hf/hub"
AGENT_HOME = "/home/agent"
WEIGHTS = ["*.safetensors", "*.bin", "*.pt", "*.gguf", "*.h5", "*.msgpack", "*.ot"]


def download(model: str, revision: str, cache_dir: str | None, ignore_patterns: list[str] | None) -> Path:
    snapshot = Path(
        huggingface_hub.snapshot_download(
            model, revision=revision, cache_dir=cache_dir, ignore_patterns=ignore_patterns
        )
    )
    # snapshot_download writes this file itself only when it is given a branch name.
    refs = snapshot.parents[1] / "refs"
    refs.mkdir(exist_ok=True)
    (refs / "main").write_text(revision, encoding="utf-8")
    return snapshot


def record(snapshot: Path, revision: str, path: Path, home: str) -> None:
    """Write what the download put in the repository's blobs directory, relative to the home."""
    repository = snapshot.resolve().parents[1]
    blobs = []
    if (repository / "blobs").is_dir():
        blobs = sorted(
            (
                {"name": blob.name, "size": blob.stat().st_size}
                for blob in (repository / "blobs").iterdir()
                if blob.is_file() and not blob.is_symlink()
            ),
            key=lambda blob: blob["name"],
        )
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "revision": revision,
                "repository": str(repository.relative_to(Path(home).resolve())),
                "blobs": blobs,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, help="write the downloaded files here (agent's sandbox)")
    parser.add_argument("--evaluator", action="store_true", help="also fill the evaluator's cache")
    args = parser.parse_args()
    model = os.environ["INFERENCE_BENCH_BASE_MODEL"]
    revision = os.environ["INFERENCE_BENCH_MODEL_REVISION"]
    snapshot = download(model, revision, None, None)
    if args.record:
        record(snapshot, revision, args.record, AGENT_HOME)
    if args.evaluator:
        download(model, revision, EVAL_HUB, WEIGHTS)


if __name__ == "__main__":
    main()
