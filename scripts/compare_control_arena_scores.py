"""Compare a specified cohort of completed native and Harbor scores, without running agents."""

import argparse
import json
import math
import sys
from functools import lru_cache
from pathlib import Path
from statistics import mean
from zipfile import ZipFile


@lru_cache(maxsize=8)
def native_reductions(path: Path) -> list[dict]:
    # Inspect compresses .eval files with Zstandard. Its pinned environment
    # provides the zipfile backport for Python versions before 3.14.
    if sys.version_info < (3, 14):
        try:
            import zipfile_zstd  # noqa: F401
        except ModuleNotFoundError:
            pass  # Uncompressed/DEFLATE archives do not require the backport.
    with ZipFile(path) as archive:
        header = json.loads(archive.read("header.json"))
        config = header["eval"]["config"]
        if header["status"] != "success" or (config.get("epochs") or 1) != 1:
            raise ValueError(f"Expected a completed single-epoch native evaluation: {path.name}")
        return json.loads(archive.read("reductions.json"))


def numeric(value, origin: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError(f"Missing or non-numeric score in {origin}")
    return value


def compare(manifest: Path, metric: str) -> dict:
    pairs = json.loads(manifest.read_bytes())
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("The manifest must contain at least one pair")
    native_seen = set()
    harbor_seen = set()
    rows = []
    for pair in pairs:
        log = (manifest.parent / pair["native_log"]).resolve()
        trial_dir = (manifest.parent / pair["harbor_trial"]).resolve()
        sample_id = pair["native_sample_id"]
        key = (log, sample_id)
        if key in native_seen or trial_dir in harbor_seen:
            raise ValueError("A native sample or Harbor trial occurs twice in the cohort")
        native_seen.add(key)
        harbor_seen.add(trial_dir)
        matches = [
            sample["value"]
            for reduction in native_reductions(log) if reduction["scorer"] == pair["native_scorer"]
            for sample in reduction["samples"] if sample["sample_id"] == sample_id
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected one native scorer result for {sample_id!r} in {log.name}")
        value = matches[0]
        if isinstance(value, dict):
            value = value.get(metric)
        elif metric != pair["native_scorer"]:
            raise ValueError("A scalar native result must be selected by its scorer name")
        native = numeric(value, log.name)
        trial = json.loads((trial_dir / "result.json").read_bytes())
        if (not trial.get("finished_at") or trial.get("exception_info")
                or trial.get("task_name") != pair["harbor_task"]):
            raise ValueError(f"Unfinished, errored or mismatched Harbor trial: {trial_dir.name}")
        reward = json.loads((trial_dir / "verifier/reward.json").read_bytes())
        harbor = numeric(reward.get(metric), trial_dir.name)
        if trial["verifier_result"]["rewards"].get(metric) != harbor:
            raise ValueError(f"Harbor trial and verifier reward disagree: {trial_dir.name}")
        rows.append({"native_sample_id": sample_id, "harbor_task": pair["harbor_task"],
                     "native": native, "harbor": harbor})
    return {
        "metric": metric, "pairs": len(rows), "matching": sum(r["native"] == r["harbor"] for r in rows),
        "native_mean": mean(r["native"] for r in rows), "harbor_mean": mean(r["harbor"] for r in rows),
        "scores": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSON array of explicit native sample / Harbor trial pairs")
    parser.add_argument("--metric", default="main_task_success")
    parser.add_argument("--require-equal", action="store_true", help="Fail on any differing score (e.g. for fixtures)")
    args = parser.parse_args()
    try:
        result = compare(args.manifest, args.metric)
    except (OSError, NotImplementedError, ValueError, KeyError) as error:
        parser.exit(2, f"Comparison failed: {error}\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    if args.require_equal and result["matching"] != result["pairs"]:
        sys.exit(1)
