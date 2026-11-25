"""`uv run 4dcodebench-compare`: compare the original scorer's readings with a Harbor trial's, metric by metric.

    uv run 4dcodebench-compare --original <data>/synthetic/B_01/sanity/results \\
                               --harbor <job>/<trial>/verifier/4dcodebench/results

Both directories hold the scorer's own `reward.json` and `reward.detail.json`: the
first from the upstream harness (e.g. `--sanity`, the reference world scored against
itself), the second from the Harbor verifier on the same world (the synthetic oracle).
Every reward key is listed with both readings and, where both are numbers, their
absolute difference, followed by the gate verdicts and the registration residual
(`alignment.residual`, synthetic cases).

Exits 1 when a key's readings differ in kind (a number on one side, a state on the
other, or two different states), when the gate verdicts differ, or when `--atol` is
given and a numeric difference exceeds it; otherwise 0. No tolerance is applied by
default: the differences are reported for review.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from .rewards import REWARD_KEYS


def load(results: Path) -> tuple[dict, dict]:
    reward_path, detail_path = results / "reward.json", results / "reward.detail.json"
    for path in (reward_path, detail_path):
        if not path.is_file():
            raise FileNotFoundError(f"no {path.name} in {results}")
    return (json.loads(reward_path.read_text(encoding="utf-8")),
            json.loads(detail_path.read_text(encoding="utf-8")))


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def compare(original: tuple[dict, dict], harbor: tuple[dict, dict], atol: float | None = None) -> tuple[list[dict], list[str]]:
    """Return one row per reward key and the list of mismatches."""

    (reward_a, detail_a), (reward_b, detail_b) = original, harbor
    rows, problems = [], []
    for key in sorted(set(REWARD_KEYS) | set(reward_a) | set(reward_b),
                      key=lambda k: (REWARD_KEYS.index(k) if k in REWARD_KEYS else len(REWARD_KEYS), k)):
        a, b = reward_a.get(key, "<missing>"), reward_b.get(key, "<missing>")
        diff = abs(float(a) - float(b)) if is_number(a) and is_number(b) else None
        if diff is None and a != b:
            problems.append(f"{key}: {a!r} vs {b!r}")
        elif diff is not None and atol is not None and diff > atol:
            problems.append(f"{key}: |{a} - {b}| = {diff:.3g} > {atol}")
        rows.append({"key": key, "original": a, "harbor": b, "abs_diff": diff,
                     "cause_original": (detail_a.get("causes") or {}).get(key),
                     "cause_harbor": (detail_b.get("causes") or {}).get(key)})
    for name in ("status", "gate_failure"):
        if detail_a.get(name) != detail_b.get(name):
            problems.append(f"{name}: {detail_a.get(name)!r} vs {detail_b.get(name)!r}")
    return rows, problems


def show(value) -> str:
    return f"{value:.6f}" if is_number(value) else str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="4dcodebench-compare", description=__doc__.splitlines()[0])
    parser.add_argument("--original", type=Path, required=True, help="results/ written by the upstream harness")
    parser.add_argument("--harbor", type=Path, required=True, help="results/ written by the Harbor verifier")
    parser.add_argument("--atol", type=float, default=None, help="fail when a numeric difference exceeds this")
    parser.add_argument("--json", type=Path, default=None, help="also write the comparison here")
    args = parser.parse_args(argv)

    original, harbor = load(args.original), load(args.harbor)
    rows, problems = compare(original, harbor, args.atol)
    print(f"{'metric':<28}{'original':>16}{'harbor':>16}{'|diff|':>12}")
    for row in rows:
        diff = "" if row["abs_diff"] is None else f"{row['abs_diff']:.3g}"
        print(f"{row['key']:<28}{show(row['original']):>16}{show(row['harbor']):>16}{diff:>12}")
    for side, (_, detail) in (("original", original), ("harbor", harbor)):
        alignment = detail.get("alignment") or {}
        print(f"{side}: status={detail.get('status')} registration residual={alignment.get('residual')}"
              f" gate_failure={detail.get('gate_failure')}")
    if args.json:
        args.json.write_text(json.dumps({"rows": rows, "problems": problems}, indent=2) + "\n", encoding="utf-8")
    for problem in problems:
        print("MISMATCH", problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
