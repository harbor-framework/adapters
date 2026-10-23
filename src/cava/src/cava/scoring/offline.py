"""Keeps the scorer offline, pinned and deterministic. Import before anything from qa_metrics.

qa_metrics calls nltk.download() six times at import and PEDANT() re-downloads its
models from the mutable ``main`` branch of zli12321/pedant_models on every init (with no
request timeout). tests/Dockerfile bakes the nltk data and the PEDANT models of commit
03519c72 into the image, so here downloads become no-ops and the models are checked
against their pinned sha256 instead. A missing nltk resource then fails loudly with a
LookupError on first use instead of reaching the network.

It also seeds langdetect, which IFEval's language checks call: unseeded, the same short
response can be detected differently across calls (e.g. 293/300 vs 7/300).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os

import langdetect
import nltk

PEDANT_MODEL_SHA256 = {
    "lr_classifier.pkl": "4c132d47ea40c352831c158671d7b11a445769b9402cf13f4698ea10b6f59ab1",
    "tf-idf_vectorizer.pkl": "4d869e2f0b121789920e9da416549c3b96da9548cb603d73c5d0c314c9a10920",
    "rule_classifier.pkl": "ff5761ea5a7f84bc9911bf9f4ca5248b18a4125298c79f8122b834c04d323b63",
    "type_classifier.pkl": "e9a823f3f4417d7f68a6e47f78d7ad9fff9266d21f65350e4233fb429d15ee1a",
}


def _no_download(*args, **kwargs):
    return True


def pedant_model_dir() -> str:
    spec = importlib.util.find_spec("qa_metrics")
    return os.path.join(os.path.dirname(spec.origin), "classifier")


def verify_pedant_models() -> None:
    model_dir = pedant_model_dir()
    for name, expected in PEDANT_MODEL_SHA256.items():
        with open(os.path.join(model_dir, name), "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        if digest != expected:
            raise RuntimeError(f"PEDANT model {name} has sha256 {digest}, expected {expected}")


nltk.download = _no_download
langdetect.DetectorFactory.seed = 0

import qa_metrics.pedant  # noqa: E402  (after the nltk patch: it downloads at import)

qa_metrics.pedant.download_link = _no_download
