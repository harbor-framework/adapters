from __future__ import annotations

import pytest

from contextbench.attribution.types import Claim, Classification


def test_a_projected_claim_credits_at_least_one_file() -> None:
    with pytest.raises(ValueError, match="at least one"):
        Claim.verified({}, "nothing")


def test_only_a_projected_claim_carries_ranges() -> None:
    with pytest.raises(ValueError, match="only a projected claim"):
        Claim(Classification.DISCOVERY_ONLY, "paths only", {"src/a.py": [(1, 1)]})
