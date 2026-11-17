"""Exact-match scoring for Chess Puzzles, identical to Inspect AI's ``exact()`` scorer.

Chess Puzzles 2.0.x scores a submitted move with ``inspect_ai.scorer.exact()``. To keep the
verifier free of the (large) Inspect dependency, the normalization and comparison code below
is copied from ``inspect-ai==0.3.273`` (the version pinned by the upstream repository's
``uv.lock``): ``inspect_ai/scorer/_classification.py`` and ``inspect_ai/_util/text.py``.
Inspect AI is distributed under the MIT License; the full notice is at the end of this file.

Only the standard library is used, so this file runs unchanged inside the task container.
"""

from __future__ import annotations

import math
import re
import string
from typing import List


# --- inspect_ai/_util/text.py -------------------------------------------------------------
def is_finite_number(s: str) -> bool:
    try:
        return math.isfinite(float(s))
    except ValueError:
        return False


def strip_punctuation(s: str) -> str:
    return s.strip(string.whitespace + string.punctuation)


# --- inspect_ai/scorer/_classification.py ---------------------------------------------------
def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _normalize_number(text: str) -> str:
    if is_finite_number(text):
        return str(float(text))
    else:
        return text


def _remove_articles(text: str) -> str:
    _ARTICLES = re.compile(r"\b(a|an|the)\b", re.UNICODE)
    return _ARTICLES.sub(" ", text)


def _remove_punc(text: str) -> str:
    if is_finite_number(text):
        return text
    # boundary punctuation around a number (e.g. "(3.14)" or "3.14.") hides it
    # from the finite-number check above — strip the boundary and re-check
    stripped = strip_punctuation(text)
    if is_finite_number(stripped):
        return stripped
    return "".join(ch for ch in text if ch not in string.punctuation)


def _tokenize(text: str) -> List[str]:
    return re.split(" |-", text)


def _normalize_token(token: str) -> str:
    token = _remove_punc(token.casefold())
    token = _normalize_number(token)
    token = _remove_articles(token)
    token = _normalize_whitespace(token)
    return token


def _normalize(text: str) -> str:
    """Normalize text to remove extraneous characters and words."""
    tokens = []
    for token in _tokenize(text):
        tokens.append(_normalize_token(token))
    tokens = [token for token in tokens if token.strip()]
    return " ".join(tokens).strip()


def max_exact_score(answer: str, targets: List[str]) -> float:
    max_exact = 0.0
    answer_norm = _normalize(answer)
    for target in targets:
        if target.strip():
            target_norm = _normalize(target)
            exact_score = 1.0 if target_norm == answer_norm else 0.0
            max_exact = max(max_exact, exact_score)
    return max_exact


def is_correct(answer: str, target: str) -> bool:
    """True when ``answer`` exactly matches ``target`` under Inspect's normalization."""
    return max_exact_score(answer, [target]) == 1.0


# ---------------------------------------------------------------------------------------------
# The functions above other than ``is_correct`` are copied from Inspect AI, which is licensed
# as follows:
#
# MIT License
#
# Copyright (c) 2024 UK AI Security Institute
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
