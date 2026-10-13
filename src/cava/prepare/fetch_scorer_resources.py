"""Install the scorer's offline resources locally (what tests/Dockerfile bakes into the
verifier image): the nltk packages qa_metrics needs and the PEDANT models pinned to
zli12321/pedant_models@03519c72, sha256-checked. Needed once before running
validate_oracles.py outside Docker, because scoring/offline.py disables downloads.

Usage: python fetch_scorer_resources.py [--nltk-dir DIR]   (default: $NLTK_DATA or ~/nltk_data)
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "cava" / "scoring"))

NLTK_PACKAGES = ["averaged_perceptron_tagger", "punkt", "wordnet", "omw-1.4", "punkt_tab",
                 "averaged_perceptron_tagger_eng"]
PEDANT_COMMIT = "03519c72bb8cf87520dc741554ab3dd68958716d"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nltk-dir", default=os.environ.get("NLTK_DATA",
                                                         str(Path.home() / "nltk_data")))
    args = ap.parse_args()

    import nltk  # plain nltk: offline.py is deliberately not imported here

    for pkg in NLTK_PACKAGES:
        nltk.download(pkg, download_dir=args.nltk_dir, quiet=True)

    # read the pinned hashes without executing offline.py (it would patch nltk.download)
    src = (Path(sys.path[0]) / "offline.py").read_text()
    start = src.index("PEDANT_MODEL_SHA256 = {")
    namespace: dict = {}
    exec(src[start:src.index("}", start) + 1], namespace)
    expected = namespace["PEDANT_MODEL_SHA256"]

    spec = importlib.util.find_spec("qa_metrics")
    model_dir = Path(spec.origin).parent / "classifier"
    model_dir.mkdir(exist_ok=True)
    for name, digest in expected.items():
        url = f"https://github.com/zli12321/pedant_models/raw/{PEDANT_COMMIT}/{name}"
        data = urllib.request.urlopen(url, timeout=120).read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError(f"{name}: sha256 mismatch for {url}")
        (model_dir / name).write_bytes(data)
    print(f"nltk data -> {args.nltk_dir}; PEDANT models -> {model_dir}")


if __name__ == "__main__":
    main()
