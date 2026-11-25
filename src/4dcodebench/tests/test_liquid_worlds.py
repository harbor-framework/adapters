"""Synthetic worlds that hold only an identity-less liquid: `solver/`, no `dynamics/`.

The upstream `scripts/download_data.py` `unpack` writes `dynamics/` only for the
archives a packed world holds, so such a reference world arrives without it. The
adapter takes the world as published: it neither creates an empty `dynamics/` nor
treats the case as incomplete. (Upstream's own world gate still requires `dynamics/`;
that is upstream's behaviour and is left unchanged.)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import add_case, write
from harbor_4dcodebench.adapter import REQUIRED_DATA, AdapterError, Harbor4DCodeBenchAdapter, required_data


def liquid_case(repo: Path, name: str = "LQ_01") -> Path:
    add_case(repo, "synthetic", name)
    world = repo / "data" / "synthetic" / name / "world"
    shutil.rmtree(world / "dynamics")
    write(world / "solver" / "manifest.json", "{}")
    return world


def test_a_liquid_only_world_is_generated_as_published(fake_repo, tmp_path):
    world = liquid_case(fake_repo)
    assert required_data("synthetic", world.parent) == tuple(
        name for name in REQUIRED_DATA["synthetic"] if name != "world/dynamics")

    written = Harbor4DCodeBenchAdapter(tmp_path / "out", repo=fake_repo).run()
    task = tmp_path / "out" / "synthetic-lq-01"
    assert written == [task]
    case = json.loads((task / "tests" / "case.json").read_text(encoding="utf-8"))
    assert "world/dynamics" not in case["required_data"]
    for copy in (task / "tests" / "bench" / "data" / "synthetic" / "LQ_01" / "world", task / "solution" / "world"):
        assert (copy / "solver" / "manifest.json").is_file()
        assert not (copy / "dynamics").exists()      # no placeholder directory


def test_dynamics_is_still_required_without_a_solver(fake_repo, tmp_path):
    add_case(fake_repo, "synthetic", "B_02")
    shutil.rmtree(fake_repo / "data" / "synthetic" / "B_02" / "world" / "dynamics")
    assert required_data("synthetic", fake_repo / "data" / "synthetic" / "B_02") == REQUIRED_DATA["synthetic"]
    with pytest.raises(AdapterError, match=r"synthetic/B_02: \['world/dynamics'\]"):
        Harbor4DCodeBenchAdapter(tmp_path / "out", repo=fake_repo).run()
    # the real split never requires a world
    assert required_data("real", fake_repo / "data" / "real" / "x") == REQUIRED_DATA["real"]
