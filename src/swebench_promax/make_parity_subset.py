#!/usr/bin/env python3
"""Draw the parity subset for SWE-Bench-ProMax, reproducibly.

Rules (fixed in advance, so the subset is not chosen after seeing any score):

1. Drop any task the adapter excludes (currently none).
2. From the rest, take N tasks per language with a fixed seed, sorted by instance id first so
   the draw does not depend on the order of the source file.

Run:  python3 make_parity_subset.py --data-dir /path/with/swe-bench-promax.json
"""
from __future__ import annotations

import argparse
import collections
import json
import random
from pathlib import Path

from swebench_promax.adapter import EXCLUDED, load_records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--per-language", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20261121)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "parity_task_ids.txt")
    ap.add_argument("--drop-languages", nargs="*", default=[])
    a = ap.parse_args()

    recs = load_records(a.data_dir)
    pool = [
        r for r in recs
        if r.instance_id not in EXCLUDED
        and r.language.lower() not in {l.lower() for l in a.drop_languages}
    ]
    by_lang: dict[str, list[str]] = collections.defaultdict(list)
    for r in pool:
        by_lang[r.language.lower()].append(r.instance_id)

    rng = random.Random(a.seed)
    chosen: list[str] = []
    for lang in sorted(by_lang):
        ids = sorted(by_lang[lang])
        if len(ids) < a.per_language:
            raise SystemExit(f"{lang}: only {len(ids)} tasks left, need {a.per_language}")
        chosen += sorted(rng.sample(ids, a.per_language))

    a.out.write_text("\n".join(chosen) + "\n")
    print(f"{len(chosen)} tasks -> {a.out}")
    for lang in sorted(by_lang):
        print(f"  {lang:11s} pool {len(by_lang[lang]):3d}  drawn {a.per_language}")
    print(json.dumps({"seed": a.seed, "per_language": a.per_language,
                      "dropped_languages": a.drop_languages,
                      "dropped_excluded": sorted(EXCLUDED)},
                     indent=2))


if __name__ == "__main__":
    main()
