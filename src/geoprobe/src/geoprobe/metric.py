# /// script
# dependencies = []
# ///
"""Aggregate GeoProbe native errors by protocol and valid-field denominator."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def aggregate(rows: list[dict | None]) -> dict[str, float]:
    totals = defaultdict(float)
    missing = 0
    for row in rows:
        if row is None:
            missing += 1
            continue
        if not isinstance(row, dict) or not row:
            raise ValueError("Expected nonempty GeoProbe reward objects or null")
        for key, value in row.items():
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"Nonfinite/nonnumeric reward: {key}")
            totals[key] += value
    result = {"recorded_cases": sum(value for key, value in totals.items() if key.endswith("__cases")), "missing_trials": missing}
    for key, value in sorted(totals.items()):
        if key.endswith("__cases"):
            protocol = key.removesuffix("__cases")
            result[key] = value
            result[f"{protocol}__valid_fraction"] = totals[f"{protocol}__valid"] / value
        elif key.endswith("__sum"):
            name = key.removesuffix("__sum")
            count = totals.get(name + "__n", 0)
            if count <= 0:
                raise ValueError(f"Missing denominator for {name}")
            result[name] = value / count
            result[name + "__n"] = count
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-path", type=Path, required=True)
    parser.add_argument("-o", "--output-path", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input_path.read_text().splitlines() if line.strip()]
    args.output_path.write_text(json.dumps(aggregate(rows), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
