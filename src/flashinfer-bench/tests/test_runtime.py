import hashlib
import io
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

RUNTIME = Path(__file__).parents[1] / "src/flashinfer_bench/runtime"
sys.path.insert(0, str(RUNTIME))
import assets
import evaluate


def test_tensor_download_and_cache_fail_on_checksum_mismatch(tmp_path, monkeypatch):
    root, cache = tmp_path / "data", tmp_path / "cache"
    sha = hashlib.sha256(b"tensor").hexdigest()
    manifest = {
        "dataset_revision": "pin",
        "blobs": {"blob/x": {"sha256": sha, "size": 6}},
    }
    monkeypatch.setattr(
        assets.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"tensor")
    )
    assets.prepare(root, manifest, cache)
    assert (root / "blob/x").read_bytes() == b"tensor"

    def unexpected_download(*args, **kwargs):
        pytest.fail("Existing cached tensors must not be downloaded again")

    monkeypatch.setattr(assets.urllib.request, "urlopen", unexpected_download)
    assets.prepare(root, manifest, cache)
    (cache / sha).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        assets.prepare(root, manifest, cache)
    (cache / sha).unlink()
    monkeypatch.setattr(
        assets.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"broken")
    )
    with pytest.raises(ValueError, match="checksum"):
        assets.prepare(root, manifest, cache)
    assert (cache / sha).read_bytes() == b"broken"
    assert (root / "blob/x").read_bytes() == b"tensor"


def test_delegates_scoring_including_baseline_failures_and_rejects_missing_traces():
    candidate = NS(name="candidate", definition="def")
    baseline = NS(name="base")
    rows = [
        NS(solution=name, workload=NS(uuid="w"), evaluation=NS(status="PASSED"))
        for name in ["base", "candidate"]
    ]
    calls = []

    def score(name, baseline_author):
        calls.append((name, baseline_author))
        return NS(avg_speedup=2.75)

    result = NS(traces={"def": rows}, get_solution_score=score)
    assert evaluate.score_result(result, candidate, baseline, ["w"]).avg_speedup == 2.75
    assert calls == [("candidate", "baseline")]
    with pytest.raises(RuntimeError, match="Incomplete"):
        evaluate.score_result(result, candidate, baseline, ["w", "missing"])
    rows[0].evaluation.status = "RUNTIME_ERROR"
    assert evaluate.score_result(result, candidate, baseline, ["w"]).avg_speedup == 2.75
    assert len(calls) == 2
    rows[1].evaluation = None
    with pytest.raises(RuntimeError, match="Missing evaluation"):
        evaluate.score_result(result, candidate, baseline, ["w"])
