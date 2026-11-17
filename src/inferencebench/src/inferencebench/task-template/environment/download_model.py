"""Fill the model caches before the agent starts. The healthcheck runs this once, as root.

The agent's cache gets the whole repository, as in the original benchmark. A second cache, which
only root can write, gets the tokenizer and configuration files that the final evaluation builds
its requests from. Both hold the pinned revision, and refs/main names it, so that a lookup of
the model by name finds this revision without the network.
"""

import os
from pathlib import Path

import huggingface_hub

EVAL_HUB = "/opt/ib_eval_hf/hub"
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


def main() -> None:
    model = os.environ["INFERENCE_BENCH_BASE_MODEL"]
    revision = os.environ["INFERENCE_BENCH_MODEL_REVISION"]
    download(model, revision, None, None)
    download(model, revision, EVAL_HUB, WEIGHTS)


if __name__ == "__main__":
    main()
