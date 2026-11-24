"""Pinned upstream source handling for the GDM adapters.

The original benchmark is Google DeepMind's stealth / situational
awareness suite (arXiv:2505.01420). The open-source release used as the
parity side is the UK AISI Inspect Evals port. Adapters must generate
from a pinned commit so task generation is reproducible; pass
``--source-dir`` (or set ``GDM_INSPECT_EVALS_DIR``) to reuse an existing
checkout instead of cloning.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

UPSTREAM_REPO = "https://github.com/UKGovernmentBEIS/inspect_evals.git"
# Commit this adapter was developed and verified against.
UPSTREAM_COMMIT = "a68dade7efb803ef50c8442d3f16264b293d1414"
PAPER_URL = "https://arxiv.org/abs/2505.01420"


def _git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ensure_source(source_dir: Path | None = None) -> Path:
    """Return an inspect_evals checkout at UPSTREAM_COMMIT.

    Resolution order: explicit argument, $GDM_INSPECT_EVALS_DIR, then a
    cache clone under ~/.cache/harbor-adapters/inspect_evals.
    """
    candidate = source_dir or (
        Path(os.environ["GDM_INSPECT_EVALS_DIR"])
        if os.environ.get("GDM_INSPECT_EVALS_DIR")
        else None
    )
    if candidate is not None:
        candidate = Path(candidate).expanduser().resolve()
        head = _git(["rev-parse", "HEAD"], cwd=candidate)
        if head != UPSTREAM_COMMIT:
            raise RuntimeError(
                f"inspect_evals checkout at {candidate} is at {head}, "
                f"expected pinned commit {UPSTREAM_COMMIT}. "
                "Check out the pinned commit or update UPSTREAM_COMMIT."
            )
        return candidate

    cache_dir = (
        Path.home() / ".cache" / "harbor-adapters" / "inspect_evals"
    )
    if not (cache_dir / ".git").exists():
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        _git(
            [
                "clone",
                "--filter=blob:none",
                "--sparse",
                UPSTREAM_REPO,
                str(cache_dir),
            ]
        )
        _git(
            [
                "sparse-checkout",
                "set",
                "src/inspect_evals/gdm_stealth",
                "src/inspect_evals/gdm_self_reasoning",
                "src/inspect_evals/gdm_capabilities",
            ],
            cwd=cache_dir,
        )
    head = _git(["rev-parse", "HEAD"], cwd=cache_dir)
    if head != UPSTREAM_COMMIT:
        _git(["fetch", "origin", UPSTREAM_COMMIT], cwd=cache_dir)
        _git(["checkout", UPSTREAM_COMMIT], cwd=cache_dir)
    return cache_dir
